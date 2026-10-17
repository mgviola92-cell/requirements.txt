"""Persisted two-player inline checkers; no images or countdown edits."""
import json
import logging
import threading
import time
from contextlib import contextmanager
from telebot import types
from core.customization import message_text, setting_value, group_scope
from core.sessions import start_session, end_session
from database.db import get_db_connection
from games import checkers as game

LOG=logging.getLogger(__name__)
READY=False
ACTIVE=set()
LOCK=threading.RLock()
DEFAULTS={'lobby_seconds':300,'turn_seconds':300}
MESSAGES={
 'title':'🐯 ကျားကွက် · လူနှစ်ယောက်',
 'waiting':'{name} က စိန်ခေါ်ထားသည်။\nအောက်က လက်ခံမယ်ကို နှိပ်ပါ။ အနီစေ့က အရင်ရွှေ့မည်။',
 'target':'ဖိတ်ထားသူသာ လက်ခံနိုင်သည်။',
 'playing':'🔴 {red}\n⚪ {white}\n\n{turn} အလှည့် — ကိုယ့်စေ့ကိုနှိပ်၊ ပြီးလျှင် 🟢 အကွက်ကိုနှိပ်ပါ။',
 'capture':'ခုန်စားရန်ရှိသည်။ စားရမည်။',
 'chain':'ရွေးထားသောစေ့ဖြင့် ဆက်ခုန်စားပါ။',
 'crown':'🔴/⚪ သာမန်စေ့ · 🔴👑/⚪👑 ဘုရင်စေ့',
 'join':'🤝 လက်ခံမယ်','cancel':'🛑 ပွဲရပ်မယ်','draw':'🤝 သရေတောင်း',
 'confirm':'ရပ်ရန် အတည်ပြုမလား? ကစားနေသူဆို အရှုံးပေးခြင်းဖြစ်သည်။ Admin က ပွဲဖျက်နိုင်သည်။',
 'yes':'✅ အတည်ပြုမယ်','no':'ဆက်ဆော့မယ်',
 'offer':'သရေတောင်းထားသည်။ ပြိုင်ဘက်က လက်ခံ/ငြင်းနိုင်သည်။',
 'accept':'သရေလက်ခံ','decline':'ငြင်းမယ်',
 'win':'🏁 {name} အနိုင်ရပြီ။ ပြိုင်ဘက် စေ့မရှိတော့ပါ သို့မဟုတ် ရွှေ့မရတော့ပါ။',
 'timeout':'⌛ အလှည့်ချိန်ကုန်သွားပြီ။ {name} အနိုင်ရသည်။',
 'resign':'🏳️ အရှုံးပေးလိုက်ပြီ။ {name} အနိုင်ရသည်။',
 'draw_result':'🤝 သရေပွဲဖြစ်သည်။','cancelled':'ပွဲဖျက်သိမ်းလိုက်ပြီ။',
 'lobby_timeout':'လက်ခံသူမရှိ၍ ဖိတ်ခေါ်မှုသက်တမ်းကုန်ပြီ။',
 'group':'Group ထဲမှာ /checkers သို့မဟုတ် /ကျားကွက် ပို့ပါ။ သူငယ်ချင်းကို reply လုပ်ပြီး စိန်ခေါ်နိုင်သည်။',
 'busy':'ဒီ group မှာ ပွဲရှိနေသည်။ အရင်ပွဲပြီးမှ ပြန်စမ်းပါ။',
 'error':'ခေတ္တမလုပ်နိုင်သေးပါ။ ခဏနေရင် ပြန်စမ်းပါ။',
 'expired':'ခလုတ်ဟောင်းဖြစ်သည်။ လက်ရှိ board ကိုသုံးပါ။',
 'join_denied':'စိန်ခေါ်သူကိုယ်တိုင် သို့မဟုတ် ဖိတ်မထားသူ လက်ခံမရပါ။',
 'players_only':'ပွဲကစားသူ သို့မဟုတ် Group Admin သာ ရပ်နိုင်သည်။',
 'turn_only':'အခု မင်းအလှည့်မဟုတ်ပါ။',
 'illegal':'အဲဒီအကွက်ကို ရွှေ့မရပါ။ စားရန်ရှိလျှင် စားရမည်။',
 'confirm_first':'ရပ်ရန်မေးထားတာကို အရင်အတည်ပြု သို့မဟုတ် ဆက်ဆော့ ရွေးပါ။',
 'offer_pending':'သရေတောင်းထားပြီးပြီ။',
 'opponent_only':'ပြိုင်ဘက်သာ သရေတောင်းဆိုမှုကို ဖြေနိုင်သည်။',
 'member':'Group အဖွဲ့ဝင်သာ အသုံးပြုနိုင်သည်။',
 'ok':'လက်ခံပြီးပြီ။',
 'rules':'🐯 ကျားကွက် ဆော့နည်း\n\n/checkers သို့မဟုတ် /ကျားကွက် — စိန်ခေါ်မယ်။ သူငယ်ချင်းစာကို reply လုပ်လျှင် သူသာလက်ခံနိုင်သည်။\n🔴 အရင်ရွှေ့သည်။ စေ့ကိုနှိပ်ပြီး 🟢 အကွက်ကိုနှိပ်ပါ။\nသာမန်စေ့က အရှေ့ထောင့်ဖြတ် တစ်ကွက်ရွှေ့၊ အရှေ့ဘက် နှစ်ကွက်ခုန်စားသည်။ စားနိုင်လျှင် စားရမည်။ ဆက်စားနိုင်လျှင် ဆက်စားရမည်။\nတစ်ဖက်ဆုံးတန်းရောက်လျှင် 👑 ဘုရင်ဖြစ်ပြီး အလှည့်ဆုံးသည်။ ဘုရင်က အရှေ့/အနောက် တစ်ကွက်ရွှေ့၊ နှစ်ကွက်ခုန်စားနိုင်သည်။ အဝေးပျံဘုရင်မဟုတ်ပါ။\nပြိုင်ဘက် စေ့ကုန် သို့မဟုတ် ရွှေ့မရလျှင် နိုင်သည်။ တူညီသောအနေအထား ၃ ကြိမ် သို့မဟုတ် မစား/ဘုရင်မတင်ဘဲ ရွှေ့ချက် ၈၀ ပြည့်လျှင် သရေ။ သရေတောင်း၍လည်း လက်ခံနိုင်သည်။\nစောင့်ချိန်/တစ်လှည့်ချိန် default ၅ မိနစ်။ စေ့ရွေးရုံဖြင့် အချိန်မတိုးပါ။ /checkersstop ဖြင့် ရပ်ရန်အတည်ပြုနိုင်သည်။ Points မပေးသေးပါ။'}

def text(key,**fields):
    return message_text('msg.features.checkers.'+key,MESSAGES[key],fields)

@contextmanager
def locked(cid):
    with LOCK,get_db_connection() as con,con.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(%s)',(cid,))
        cur.execute('SELECT state FROM checkers_games WHERE chat_id=%s FOR UPDATE',(cid,))
        row=cur.fetchone()
        yield cur,row[0] if row else None

def save(cur,s):
    cur.execute('INSERT INTO checkers_games(chat_id,state) VALUES(%s,%s::jsonb) ON CONFLICT(chat_id) DO UPDATE SET state=EXCLUDED.state',(s['chat_id'],json.dumps(s,ensure_ascii=False)))

def body(s):
    lines=[text('title')]
    if s['phase']=='waiting':
        lines.append(text('waiting',name=s['names'][0]))
        if s['target']:lines.append(text('target'))
        if s['confirm'] is not None:lines.append(text('confirm'))
    elif s['phase']=='playing':
        lines.append(text('playing',red=s['names'][0],white=s['names'][1],turn='🔴' if s['turn']==1 else '⚪'))
        if s['chain'] is not None:lines.append(text('chain'))
        elif any(m[2] is not None for m in game.legal(s)):lines.append(text('capture'))
        if s['confirm'] is not None:lines.append(text('confirm'))
        if s['offer'] is not None:lines.append(text('offer'))
    else:
        key='draw_result' if s['reason']=='draw' else s['reason']
        name=s['names'][0 if s['winner']==1 else 1] if s['winner'] else ''
        lines.append(text(key,name=name))
    return '\n\n'.join(lines)[:3900]

def keyboard(s):
    k=types.InlineKeyboardMarkup(row_width=8)
    prefix=f"ck:{s['id']}:{s['revision']}:"
    def button(label,action):return types.InlineKeyboardButton(label,callback_data=prefix+action)
    if s['phase']=='playing':
        dest={m[1] for m in game.legal(s) if m[0]==s['selected']}
        for r in range(8):
            row=[]
            for c in range(8):
                i=r*8+c;p=s['board'][i]
                label=('🔴' if p>0 else '⚪')+('👑' if abs(p)==2 else '') if p else '🟢' if i in dest else '▪️' if (r+c)%2 else '▫️'
                if i==s['selected']:label='🔻'+label
                row.append(button(label,'s'+str(i)))
            k.row(*row)
    if s['confirm'] is not None:k.row(button(text('yes'),'yes'),button(text('no'),'no'))
    elif s['phase']=='waiting':k.row(button(text('join'),'join'),button(text('cancel'),'cancel'))
    elif s['phase']=='playing':
        k.row(button(text('cancel'),'cancel'),button(text('draw'),'draw'))
        if s['offer'] is not None:k.row(button(text('accept'),'accept'),button(text('decline'),'decline'))
    return k

def render(bot,s):
    try:
        bot.edit_message_text(body(s),s['chat_id'],s['card'],reply_markup=keyboard(s) if s['phase']!='finished' else None,parse_mode=None)
    except Exception:
        LOG.warning('Checkers board edit unavailable; state retained')

def complete(bot,s):
    if s['phase']!='finished':return
    ACTIVE.discard(s['chat_id']);end_session(s['chat_id'],'checkers')
    if s['reason'] in ('cancelled','lobby_timeout'):
        try:bot.delete_message(s['chat_id'],s['card'])
        except Exception:render(bot,s)
    else:render(bot,s)

def register(bot):
    global READY
    try:
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS checkers_games(chat_id BIGINT PRIMARY KEY,state JSONB NOT NULL)')
            cur.execute("SELECT chat_id FROM checkers_games WHERE state->>'phase' IN ('waiting','playing')")
            for cid, in cur.fetchall():
                ACTIVE.add(cid);start_session(cid,'checkers',recover=True)
        READY=True
    except Exception:LOG.exception('Checkers database unavailable')

    @bot.message_handler(commands=['checkers','ကျားကွက်'])
    def command(m):
        cid=m.chat.id
        if m.chat.type not in ('group','supergroup'):bot.reply_to(m,text('group'));return
        if not READY:bot.reply_to(m,text('error'));return
        with group_scope(cid):
            if not setting_value('enabled.features.checkers.command',True,cid):return
            reserved=False
            try:
                with locked(cid) as (cur,old):
                    if old and old['phase'] in ('waiting','playing'):
                        if game.expire(old,time.time()):
                            save(cur,old);complete(bot,old)
                        else:
                            render(bot,old);bot.reply_to(m,text('busy'));return
                    ok,_=start_session(cid,'checkers')
                    if not ok:bot.reply_to(m,text('busy'));return
                    reserved=True
                    target=getattr(getattr(m,'reply_to_message',None),'from_user',None)
                    if target and (target.is_bot or target.id==m.from_user.id):
                        end_session(cid,'checkers');bot.reply_to(m,text('join_denied'));return
                    s=game.new(cid,m.from_user.id,m.from_user.first_name[:60],time.time(),
                      setting_value('cfg.features.checkers.lobby_seconds',300,cid),
                      setting_value('cfg.features.checkers.turn_seconds',300,cid),target.id if target else 0)
                    sent=bot.send_message(cid,body(s),reply_markup=keyboard(s),parse_mode=None)
                    s['card']=sent.message_id;save(cur,s)
                with LOCK:ACTIVE.add(cid)
            except Exception:
                if reserved:end_session(cid,'checkers')
                LOG.exception('Checkers start failed');bot.reply_to(m,text('error'))

    @bot.message_handler(commands=['checkersrules'])
    def rules(m):
        with group_scope(m.chat.id):bot.send_message(m.chat.id,text('rules'),parse_mode=None)

    @bot.message_handler(commands=['checkersstop'])
    def stop(m):
        if m.chat.type not in ('group','supergroup'):bot.reply_to(m,text('group'));return
        try:
            with group_scope(m.chat.id),locked(m.chat.id) as (cur,s):
                if not s:bot.reply_to(m,text('expired'));return
                member=bot.get_chat_member(m.chat.id,m.from_user.id)
                s=game.action(s,m.from_user.id,'cancel',None,time.time(),admin=member.status in ('creator','administrator'))
                save(cur,s);render(bot,s)
        except ValueError as exc:bot.reply_to(m,text(str(exc)))
        except Exception:bot.reply_to(m,text('error'))

    @bot.callback_query_handler(func=lambda c:bool(c.data and c.data.startswith('ck:')))
    def callback(c):
        answer='ok'
        try:
            if not c.message or c.message.chat.type not in ('group','supergroup') or c.from_user.is_bot:raise ValueError('member')
            _,gid,rev,act=c.data.split(':');cid=c.message.chat.id
            with group_scope(cid),locked(cid) as (cur,s):
                if not s or s['id']!=gid or s['card']!=c.message.message_id:raise ValueError('expired')
                if s['revision']!=int(rev):
                    render(bot,s)
                    raise ValueError('expired')
                member=bot.get_chat_member(cid,c.from_user.id)
                if member.status in ('left','kicked') or member.status=='restricted' and not getattr(member,'is_member',False):raise ValueError('member')
                if game.expire(s,time.time()):
                    save(cur,s);complete(bot,s);answer='expired'
                else:
                    s=game.action(s,c.from_user.id,'square' if act.startswith('s') else act,act[1:] if act.startswith('s') else None,time.time(),c.from_user.first_name[:60],member.status in ('creator','administrator'))
                    save(cur,s)
                    if s['phase']=='finished':complete(bot,s)
                    else:render(bot,s)
        except ValueError as exc:answer=str(exc) if str(exc) in MESSAGES else 'expired'
        except Exception:answer='error';LOG.exception('Checkers action failed')
        finally:
            try:bot.answer_callback_query(c.id,text(answer))
            except Exception:pass

    if READY:
        def loop():
            while True:
                with LOCK:chats=list(ACTIVE)
                for cid in chats:
                    try:
                        with group_scope(cid),locked(cid) as (cur,s):
                            if not s or s['phase']=='finished':ACTIVE.discard(cid)
                            elif game.expire(s,time.time()):save(cur,s);complete(bot,s)
                    except Exception:LOG.exception('Checkers timeout unavailable')
                time.sleep(30)
        threading.Thread(target=loop,name='checkers-timeouts',daemon=True).start()
