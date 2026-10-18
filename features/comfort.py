"""Bounded owner-started comfort series, target-controlled stop, no catch-up spam."""
import logging
import os
import random
import secrets
import threading
import time
from contextlib import contextmanager
from telebot import types
from telebot.handler_backends import ContinueHandling
from database.db import get_db_connection
from core.customization import message_text,setting_value,group_scope
from core.comfort_content import choose_line,emoji_pair,render_line
from data.comfort_lines import LINES

LOG=logging.getLogger(__name__)
LOCK=threading.RLock()
ACTIVE={}
READY=False
RNG=random.SystemRandom()
DEFAULTS={'target_id':0,'nickname':'ကလေး','emojis':'','count':6,'interval':5,'cooldown':600}
MESSAGES={
 'group':'Group ထဲမှာ /ချော့ပေး ပို့ပါ။ ရပ်ရန် /ရပြီ။',
 'owner':'ဒီ command ကို Owner သာ စနိုင်သည်။',
 'setup':'Owner Tools → ချော့စာ → Target User ID ကို အရင်ထည့်ပါ။',
 'member':'သတ်မှတ်ထားသူ ဒီ group မှာ ရှိမရှိ စစ်မရပါ။ User ID နှင့် bot permission ကိုစစ်ပါ။',
 'busy':'ချော့စာအစီအစဉ် ရှိနေပြီ။ အရင်ပွဲပြီးမှ ပြန်စပါ။',
 'cooldown':'ခဏနားထားပါ။ ထပ်မံပို့ရန် cooldown မပြည့်သေးပါ။',
 'declined':'သူက ရပ်ထားပါသည်။ သူကိုယ်တိုင် ပြန်လက်ခံမှ ထပ်စနိုင်မည်။',
 'started':'ချော့စာ {count} ကြောင်းကို {interval} စက္ကန့်ခြား ပို့မည်။ Owner နှင့် သတ်မှတ်ထားသူက /ရပြီ ဖြင့်ရပ်နိုင်သည်။',
 'stopped':'ချော့စာပို့မှု ရပ်ပြီးပြီ။',
 'none':'ရပ်ရန် ချော့စာအစီအစဉ် မရှိပါ။',
 'permission':'Owner နှင့် သတ်မှတ်ထားသူသာ /ရပြီ သုံးနိုင်သည်။',
 'blocked':'ထပ်မပို့ရန် မှတ်ထားပြီးပြီ။ ပြန်လက်ခံချင်မှ အောက်ကခလုတ်နှိပ်ပါ။',
 'allow':'ချော့စာ ပြန်လက်ခံမယ်','allowed':'ပြန်လက်ခံထားပြီးပြီ။ Owner က ပြန်စနိုင်သည်။',
 'target_only':'သတ်မှတ်ထားသူသာ ဒီခလုတ်ကို နှိပ်နိုင်သည်။',
 'error':'ခေတ္တ မလုပ်နိုင်သေးပါ။ ခဏနေ ပြန်စမ်းပါ။'}


def text(key,**fields):return message_text('msg.features.comfort.'+key,MESSAGES[key],fields)
def cfg(key,cid):return setting_value('cfg.features.comfort.'+key,DEFAULTS[key],cid)
def owner(uid):return str(uid)==os.getenv('OWNER_TELEGRAM_ID','').strip()


@contextmanager
def transaction():
    with LOCK,get_db_connection() as con,con.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(759012349)')
        yield cur


def stop_run(cid,run_id,reason):
    with transaction() as cur:
        cur.execute("UPDATE comfort_runs SET status=%s WHERE chat_id=%s AND run_id=%s AND status='active'",(reason,cid,run_id))
    with LOCK:
        run=ACTIVE.get(cid)
        if run and run['id']==run_id:run['event'].set();ACTIVE.pop(cid,None)


def next_line(cur,target,cid,name):
    lines=[(str(i),message_text('msg.comfort.line.'+str(i),line,scope=cid)) for i,line in enumerate(LINES)]
    # Hash the actual rendered text, so editing nicknames or duplicate templates stays coherent.
    lines=[(key,line.replace('{name}',name)) for key,line in lines]
    cur.execute('SELECT body_hash FROM comfort_used WHERE target_id=%s',(target,))
    used={row[0] for row in cur.fetchall()}
    choice=choose_line(lines,used,RNG)
    if choice is None:
        # Exhaust the whole pool first; retain the latest 30 to avoid a cycle-boundary repeat.
        cur.execute('DELETE FROM comfort_used WHERE target_id=%s AND body_hash NOT IN (SELECT body_hash FROM comfort_used WHERE target_id=%s ORDER BY sent_at DESC LIMIT 30)',(target,target))
        cur.execute('SELECT body_hash FROM comfort_used WHERE target_id=%s',(target,));recent={r[0] for r in cur.fetchall()}
        choice=choose_line(lines,recent,RNG)
        if choice is None:return None
    _,line,digest=choice
    # Claim before Telegram: ambiguous failures are never retried or repeated.
    cur.execute('INSERT INTO comfort_used(target_id,body_hash) VALUES(%s,%s) ON CONFLICT DO NOTHING',(target,digest))
    return line


def run_worker(bot,run):
    cid=run['chat'];target=run['target']
    try:
        for index in range(run['count']):
            if index and run['event'].wait(run['interval']):break
            if run['event'].is_set() or time.time()>=run['expires']:break
            with group_scope(cid):
                with transaction() as cur:
                    cur.execute("SELECT status FROM comfort_runs WHERE chat_id=%s AND run_id=%s",(cid,run['id']))
                    row=cur.fetchone()
                    cur.execute('SELECT blocked FROM comfort_targets WHERE target_id=%s',(target,));policy=cur.fetchone()
                    if not row or row[0]!='active' or policy and policy[0]:break
                    line=next_line(cur,target,cid,run['name'])
                    if line is None:break
                # Stop wins before the next send; at most one in-flight API request can already exist.
                if run['event'].is_set():break
                with LOCK:
                    reply=run.get('reply')
                    if reply and time.time()-reply[1]>120:reply=None
                    run['reply']=None
                tokens=cfg('emojis',cid).split()
                styled,plain=emoji_pair(RNG.choice(tokens)) if tokens else ('','')
                kwargs={'parse_mode':'HTML'}
                if reply:kwargs['reply_parameters']=types.ReplyParameters(message_id=reply[0],allow_sending_without_reply=True)
                value=render_line(target,run['name'],line,styled)
                try:bot.send_message(cid,value,**kwargs)
                except Exception as exc:
                    if styled!=plain and getattr(exc,'error_code',None)==400 and 'emoji' in str(exc).lower():
                        bot.send_message(cid,render_line(target,run['name'],line,plain),**kwargs)
                    else:raise
    except Exception:LOG.warning('Comfort series stopped after delivery failure')
    finally:
        try:stop_run(cid,run['id'],'ended')
        except Exception:LOG.warning('Comfort series completion could not be saved')


def register(bot):
    global READY
    try:
        with transaction() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS comfort_targets(target_id BIGINT PRIMARY KEY,blocked BOOLEAN NOT NULL DEFAULT FALSE,last_started DOUBLE PRECISION NOT NULL DEFAULT 0)')
            cur.execute('CREATE TABLE IF NOT EXISTS comfort_runs(chat_id BIGINT PRIMARY KEY,run_id TEXT NOT NULL,target_id BIGINT NOT NULL,status TEXT NOT NULL)')
            cur.execute('CREATE TABLE IF NOT EXISTS comfort_used(target_id BIGINT NOT NULL,body_hash TEXT NOT NULL,sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(target_id,body_hash))')
            # Never replay missed romantic mentions after a restart/outage.
            cur.execute("UPDATE comfort_runs SET status='interrupted' WHERE status='active'")
        READY=True
    except Exception:LOG.warning('Comfort database unavailable')

    @bot.message_handler(commands=['ချော့ပေး'])
    def start(m):
        if not owner(m.from_user.id):bot.reply_to(m,text('owner'));return
        if m.chat.type not in ('group','supergroup'):bot.reply_to(m,text('group'));return
        cid=m.chat.id
        if not READY:bot.reply_to(m,text('error'));return
        if not setting_value('enabled.features.comfort.start',True,cid):return
        target=cfg('target_id',cid)
        if not target or target==m.from_user.id:bot.reply_to(m,text('setup'));return
        try:
            member=bot.get_chat_member(cid,target)
            if member.user.is_bot or member.status in ('left','kicked') or member.status=='restricted' and not getattr(member,'is_member',False):
                bot.reply_to(m,text('member'));return
            with transaction() as cur:
                cur.execute('INSERT INTO comfort_targets(target_id) VALUES(%s) ON CONFLICT DO NOTHING',(target,))
                cur.execute('SELECT blocked,last_started FROM comfort_targets WHERE target_id=%s FOR UPDATE',(target,));blocked,last=cur.fetchone()
                if blocked:bot.reply_to(m,text('declined'));return
                cur.execute("SELECT 1 FROM comfort_runs WHERE status='active' AND (chat_id=%s OR target_id=%s)",(cid,target))
                if cur.fetchone():bot.reply_to(m,text('busy'));return
                now=time.time()
                if now-last<cfg('cooldown',cid):bot.reply_to(m,text('cooldown'));return
                run={'id':secrets.token_hex(6),'chat':cid,'target':target,'name':(cfg('nickname',cid).strip() or 'ကလေး')[:40],
                     'count':min(12,max(1,cfg('count',cid))),'interval':min(300,max(5,cfg('interval',cid))),
                     'expires':now+900,'event':threading.Event(),'reply':None}
                cur.execute("INSERT INTO comfort_runs(chat_id,run_id,target_id,status) VALUES(%s,%s,%s,'active') ON CONFLICT(chat_id) DO UPDATE SET run_id=EXCLUDED.run_id,target_id=EXCLUDED.target_id,status='active'",(cid,run['id'],target))
                cur.execute('UPDATE comfort_targets SET last_started=%s WHERE target_id=%s',(now,target))
            with LOCK:ACTIVE[cid]=run
            try:
                bot.reply_to(m,text('started',count=run['count'],interval=run['interval']))
                threading.Thread(target=run_worker,args=(bot,run),name='comfort-series',daemon=True).start()
            except Exception:
                stop_run(cid,run['id'],'error');raise
        except Exception:LOG.warning('Comfort start unavailable');bot.reply_to(m,text('error'))

    @bot.message_handler(commands=['ရပြီ'])
    def stop(m):
        if m.chat.type not in ('group','supergroup'):return
        cid=m.chat.id;uid=m.from_user.id
        if not READY:return
        try:
            with transaction() as cur:
                cur.execute('SELECT run_id,target_id,status FROM comfort_runs WHERE chat_id=%s',(cid,));row=cur.fetchone()
                target=row[1] if row else cfg('target_id',cid)
                if not owner(uid) and uid!=target:bot.reply_to(m,text('permission'));return
                if uid==target:
                    cur.execute('INSERT INTO comfort_targets(target_id,blocked) VALUES(%s,TRUE) ON CONFLICT(target_id) DO UPDATE SET blocked=TRUE',(uid,))
                    cur.execute("UPDATE comfort_runs SET status='stopped' WHERE target_id=%s AND status='active'",(uid,))
                elif row:cur.execute("UPDATE comfort_runs SET status='stopped' WHERE chat_id=%s",(cid,))
            with LOCK:
                for group,run in list(ACTIVE.items()):
                    if group==cid or uid==target and run['target']==uid:run['event'].set();ACTIVE.pop(group,None)
            keyboard=None
            if uid==target:
                keyboard=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(text('allow'),callback_data='comfort:allow:'+str(uid)))
            bot.reply_to(m,text('blocked') if uid==target else text('stopped') if row and row[2]=='active' else text('none'),reply_markup=keyboard)
        except Exception:LOG.warning('Comfort stop unavailable');bot.reply_to(m,text('error'))

    @bot.callback_query_handler(func=lambda q:bool(q.data and q.data.startswith('comfort:allow:')))
    def allow(q):
        try:
            target=int(q.data.rsplit(':',1)[1])
            if q.from_user.id!=target:bot.answer_callback_query(q.id,text('target_only'),show_alert=True);return
            with transaction() as cur:cur.execute('UPDATE comfort_targets SET blocked=FALSE WHERE target_id=%s',(target,))
            bot.answer_callback_query(q.id,text('allowed'),show_alert=True)
            try:bot.edit_message_reply_markup(q.message.chat.id,q.message.message_id,reply_markup=None)
            except Exception:pass
        except Exception:LOG.warning('Comfort consent update unavailable')

    @bot.message_handler(func=lambda m:bool(m.chat.id in ACTIVE and m.from_user and not (m.text or '').startswith('/')),content_types=['text'])
    def activity(m):
        with LOCK:
            run=ACTIVE.get(m.chat.id)
            if run and m.from_user.id==run['target']:run['reply']=(m.message_id,time.time())
        return ContinueHandling()
