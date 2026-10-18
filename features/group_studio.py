from core import db_work
"""Group capsule, soundboard, memories and safe custom-command chains."""
import html
import base64
import io
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from flask import Blueprint,request,abort
from telebot.handler_backends import ContinueHandling
from database.db import get_db_connection
from core.customization import message_text,setting_value,group_scope
from core.group_content import capture,deliver,validate,substitute,NAME

LOG=logging.getLogger(__name__)
MMT=ZoneInfo('Asia/Yangon')
STARTED=False
WORK_WAKE=db_work.signal('group_studio_jobs')
MESSAGES={
 'help':'🗂️ Group Studio\n\n⏳ /capsule YYYY-MM-DD HH:MM — စာ/ပုံ/အသံကို reply ပြီး အနာဂတ်တွင်ဖွင့်ရန် (မြန်မာအချိန်)\n/capsules — ကိုယ့် capsule စာရင်း\n/capsulecancel ID — မဖွင့်ရသေးတာပယ်ဖျက်\n\n🎙️ /soundadd name — voice/audio ကို reply ပြီးသိမ်း (Admin)\n/sound name — ပြန်ဖွင့်\n/sounds — အသံစာရင်း\n/sounddel name — ဖျက် (Admin)\n\n📖 /memorysave ခေါင်းစဉ် — message ကို reply ပြီး အမှတ်တရသိမ်း\n/memories — စာရင်း\n/memory ID — ပြန်ကြည့်\n/memorybook [YYYY-MM] — အမှတ်တရစာအုပ် HTML ဖိုင်\n/memorydel ID — ကိုယ့်အမှတ်တရဖျက်\n\n🪄 /commandadd name — စာ/မီဒီယာကို reply ပြီး command ဖန်တီး (Admin)\n/commandappend name — နောက်တစ်ဆင့်ထည့်\n/commanddel name — ဖျက်\n/commands — စာရင်း\n/name args — ကိုယ်ပိုင် command သုံး\nစာတွင် {name}, {user}, {group}, {args} သုံးနိုင်သည်။\n\nOwner private chat မှ အသံ/command သိမ်းလျှင် Group အားလုံးအတွက် default ဖြစ်သည်။',
 'saved':'✅ သိမ်းပြီးပြီ။','deleted':'✅ ဖျက်ပြီးပြီ။ ',
 'capsule_saved':'⏳ Capsule #{id} သိမ်းပြီးပြီ။ {date} (မြန်မာအချိန်) တွင် ဖွင့်မယ်။',
 'capsule_open':'🕰️ အချိန် Capsule #{id} ကို ဖွင့်လိုက်ပြီ။',
 'memory_saved':'📖 အမှတ်တရ #{id} သိမ်းပြီးပြီ။ /memory {id} ဖြင့် ပြန်ကြည့်နိုင်သည်။',
 'empty':'မရှိသေးပါ။','admin':'ဒီလုပ်ဆောင်ချက်ကို Group Admin သို့မဟုတ် Owner သာလုပ်နိုင်သည်။',
 'group':'ဒီ command ကို Group ထဲတွင် သုံးပါ။','reply':'သိမ်းချင်သော စာ/ပုံ/မီဒီယာကို reply ပြီး command ပို့ပါ။',
 'unsupported':'ဒီမီဒီယာအမျိုးအစားကို မသိမ်းနိုင်ပါ။','sound_only':'Voice သို့မဟုတ် Audio ကို reply လုပ်ပါ။',
 'not_found':'မတွေ့ပါ။','date':'ရက်စွဲကို YYYY-MM-DD HH:MM ပုံစံနဲ့ရေးပါ။ မြန်မာအချိန်ဖြစ်သည်။ အနာဂတ်ရက်ဖြစ်ရမည်။',
 'name':'နာမည်ကို အင်္ဂလိပ်စာလုံးဖြင့်စပြီး စာလုံး/နံပါတ်/underscore ၂–၃၂ လုံးသုံးပါ။',
 'reserved':'ရှိပြီးသား bot command နာမည်ကို အစားထိုးမရပါ။','exists':'ရှိပြီးသားပါ။ နောက်အဆင့်ထည့်ရန် /commandappend သုံးပါ။',
 'limit':'သတ်မှတ်ထားသော အရေအတွက်ပြည့်သွားပြီ။','cooldown':'ခဏစောင့်ပြီးမှ ထပ်သုံးပါ။',
 'too_long':'စာ သို့မဟုတ် caption အရမ်းရှည်သည်။','empty_payload':'စာမပါပါ။',
 'error':'⚠️ မသိမ်းနိုင်သေးပါ။ ပြန်စမ်းပါ။','book':'Group အမှတ်တရစာအုပ်','owner_link':'🗂️ Group Studio Web','disabled':'Owner က ဒီ function ကို ပိတ်ထားသည်။',
}
DEFAULTS={'capsules_enabled':True,'sounds_enabled':True,'memories_enabled':True,'commands_enabled':True,
 'capsule_limit':10,'command_steps':5,'command_cooldown':15,'sound_cooldown':5,'memory_limit':500,'book_limit':100}
BUILTINS=set()
STATUS={'pending':'စောင့်နေသည်','sent':'ပို့ပြီးပြီ','cancelled':'ပယ်ဖျက်ပြီး','failed':'ပို့မရပါ'}


def text(key,**fields):return message_text('msg.features.group_studio.'+key,MESSAGES[key],fields)
def cfg(key,cid):return setting_value('cfg.features.group_studio.'+key,DEFAULTS[key],cid)
def esc(v):return html.escape(str(v),quote=True)


def initialize():
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('CREATE TABLE IF NOT EXISTS group_studio_assets(scope BIGINT NOT NULL,kind TEXT NOT NULL,name TEXT NOT NULL,data JSONB NOT NULL,creator BIGINT NOT NULL,updated_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(scope,kind,name))')
        cur.execute('CREATE TABLE IF NOT EXISTS group_studio_memories(id BIGSERIAL PRIMARY KEY,scope BIGINT NOT NULL,creator BIGINT NOT NULL,title TEXT NOT NULL,payload JSONB NOT NULL,request_key TEXT UNIQUE,created_at TIMESTAMPTZ DEFAULT NOW())')
        cur.execute('ALTER TABLE group_studio_memories ADD COLUMN IF NOT EXISTS request_key TEXT UNIQUE')
        cur.execute("CREATE TABLE IF NOT EXISTS group_studio_jobs(id BIGSERIAL PRIMARY KEY,request_key TEXT UNIQUE NOT NULL,scope BIGINT NOT NULL,creator BIGINT NOT NULL,payload JSONB NOT NULL,due_at TIMESTAMPTZ NOT NULL,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '',kind TEXT NOT NULL DEFAULT 'send')")
        cur.execute("CREATE INDEX IF NOT EXISTS group_studio_jobs_due ON group_studio_jobs(due_at) WHERE status='pending'")
        cur.execute('CREATE TABLE IF NOT EXISTS group_studio_cooldowns(scope BIGINT NOT NULL,uid BIGINT NOT NULL,kind TEXT NOT NULL,until_at TIMESTAMPTZ NOT NULL,PRIMARY KEY(scope,uid,kind))')
        cur.execute('CREATE TABLE IF NOT EXISTS group_studio_rewards(key TEXT NOT NULL,uid BIGINT NOT NULL,PRIMARY KEY(key,uid))')


def scope(m,manage=False):
    if m.chat.type in ('group','supergroup'):return m.chat.id
    from features.owner_operations import is_owner
    if manage and is_owner(m.from_user.id):return 0
    raise ValueError('group')


def is_admin(bot,cid,uid):
    from features.owner_operations import is_owner
    return is_owner(uid) or cid<0 and bot.get_chat_member(cid,uid).status in ('creator','administrator')


def name(value):
    value=value.casefold()
    if not NAME.fullmatch(value):raise ValueError('name')
    return value


def when(value,now=None):
    now=time.time() if now is None else now
    try:dt=datetime.strptime(value,'%Y-%m-%d %H:%M').replace(tzinfo=MMT)
    except ValueError:raise ValueError('date')
    if not now+30<dt.timestamp()<now+366*86400:raise ValueError('date')
    return dt


def enqueue(cur,key,cid,uid,payload,due=None,kind='send'):
    cur.execute('INSERT INTO group_studio_jobs(request_key,scope,creator,payload,due_at,kind) VALUES(%s,%s,%s,%s::jsonb,%s,%s) ON CONFLICT(request_key) DO NOTHING RETURNING id',
                (key,cid,uid,json.dumps(payload,ensure_ascii=False),due or datetime.now(timezone.utc),kind))
    row=cur.fetchone();return row[0] if row else None


def throttle(cur,cid,uid,kind,seconds):
    cur.execute("INSERT INTO group_studio_cooldowns VALUES(%s,%s,%s,NOW()+(%s*INTERVAL '1 second')) ON CONFLICT(scope,uid,kind) DO UPDATE SET until_at=EXCLUDED.until_at WHERE group_studio_cooldowns.until_at<=NOW() RETURNING uid",(cid,uid,kind,seconds))
    if not cur.fetchone():raise ValueError('cooldown')


def asset(cur,cid,kind,key):
    cur.execute('SELECT data FROM group_studio_assets WHERE scope IN (0,%s) AND kind=%s AND name=%s ORDER BY scope ASC LIMIT 1',(cid,kind,key))
    row=cur.fetchone();return row[0] if row else None


def asset_save(cur,cid,kind,key,data,uid,append=False):
    if kind=='command' and key in BUILTINS:raise ValueError('reserved')
    cur.execute('SELECT pg_advisory_xact_lock(759012352)')
    cur.execute('SELECT data FROM group_studio_assets WHERE scope=%s AND kind=%s AND name=%s',(cid,kind,key));old=cur.fetchone()
    if kind=='command':
        for p in data:validate(p)
        if append:
            if not old:raise ValueError('not_found')
            data=old[0]+data
        elif old:raise ValueError('exists')
        if not 1<=len(data)<=cfg('command_steps',cid):raise ValueError('limit')
    else:validate(data)
    cur.execute('INSERT INTO group_studio_assets(scope,kind,name,data,creator) VALUES(%s,%s,%s,%s::jsonb,%s) ON CONFLICT(scope,kind,name) DO UPDATE SET data=EXCLUDED.data,creator=EXCLUDED.creator,updated_at=NOW()',(cid,kind,key,json.dumps(data,ensure_ascii=False),uid))


def book(rows,title,images=None):
    images=images or {}
    parts=['<!doctype html><html lang="my"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>body{font:16px/1.8 sans-serif;max-width:800px;margin:30px auto;padding:16px;background:#f5f2eb}article{background:white;padding:20px;margin:18px 0;border-radius:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>'+esc(title)+'</h1>']
    for mid,label,payload,created in rows:
        # Escape the stored rich text; downloaded books never run user HTML.
        from html.parser import HTMLParser
        class Plain(HTMLParser):
            def __init__(self):super().__init__();self.parts=[]
            def handle_data(self,data):self.parts.append(data)
        parser=Plain();parser.feed(payload.get('text',payload.get('caption','')))
        stamp=created.astimezone(MMT).strftime('%Y-%m-%d %H:%M')
        picture='<img style="max-width:100%;border-radius:12px" alt="အမှတ်တရပုံ" src="data:image/jpeg;base64,'+images[mid]+'">' if mid in images else ''
        parts.append('<article>'+picture+'<h2>#'+str(mid)+' '+esc(label)+'</h2><small>'+stamp+'</small><pre>'+esc(''.join(parser.parts))+'</pre><p>'+esc(payload['kind'])+' · Telegram တွင် /memory '+str(mid)+' ဖြင့် မူရင်းမီဒီယာကိုကြည့်ပါ။</p></article>')
    parts.append('</html>');return '\n'.join(parts).encode()


def credit(cur,key,cid,uid,points):
    cur.execute('INSERT INTO group_studio_rewards VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING uid',(key,uid))
    if not cur.fetchone():return
    cur.execute('INSERT INTO player_stats(chat_id,user_id,points,games,wins,losses,draws) VALUES(%s,%s,%s,0,0,0,0) ON CONFLICT(chat_id,user_id) DO UPDATE SET points=GREATEST(0,player_stats.points+EXCLUDED.points) RETURNING points,games,wins,losses,draws',(cid,uid,points))
    row=cur.fetchone()
    cur.execute('INSERT INTO reward_transactions(chat_id,user_id,points,reason) VALUES(%s,%s,%s,%s)',(cid,uid,points,'draw_guess:'+key))
    return row


def run_jobs(bot):
    for _ in range(20):
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute("SELECT id,scope,payload,kind,attempts FROM group_studio_jobs WHERE status='pending' AND due_at<=NOW() ORDER BY due_at,id LIMIT 1 FOR UPDATE SKIP LOCKED")
            row=cur.fetchone()
            if not row:return
            jid,cid,payload,kind,attempts=row
            # Chain steps wait for earlier steps to complete, including retries.
            if kind=='chain':
                cur.execute("SELECT status FROM group_studio_jobs WHERE request_key LIKE %s AND id<%s AND status IN ('pending','failed','cancelled') LIMIT 1",(payload['chain']+':%',jid))
                blocked=cur.fetchone()
                if blocked:
                    if blocked[0]=='pending':cur.execute("UPDATE group_studio_jobs SET due_at=NOW()+INTERVAL '3 seconds' WHERE id=%s",(jid,))
                    else:cur.execute("UPDATE group_studio_jobs SET status='cancelled' WHERE id=%s",(jid,))
                    continue
            try:
                with group_scope(cid):
                    if kind=='capsule':
                        deliver(bot,cid,{'kind':'text','text':html.escape(text('capsule_open',id=jid))})
                    deliver(bot,cid,payload['content'] if kind=='chain' else payload)
                cur.execute("UPDATE group_studio_jobs SET status='sent' WHERE id=%s",(jid,))
            except Exception as exc:
                permanent=getattr(exc,'error_code',None) in (400,403)
                cur.execute("UPDATE group_studio_jobs SET attempts=attempts+1,status=%s,error=%s,due_at=NOW()+(%s*INTERVAL '1 second') WHERE id=%s",('failed' if permanent or attempts>=7 else 'pending',type(exc).__name__,min(120,2**(attempts+2)),jid))
                LOG.warning('Studio delivery %s: %s',jid,type(exc).__name__)


def form_payloads(form,kind):
    if 'data' in form:
        value=json.loads(form['data'])
        return value
    steps=[]
    for i in range(5):
        media=form.get('kind'+str(i),'text');body=form.get('body'+str(i),'')
        file_id=form.get('file'+str(i),'')
        if media=='text':
            if not body.strip():continue
            steps.append({'kind':'text','text':body})
        else:
            if not file_id:continue
            payload={'kind':media,'file_id':file_id}
            if media not in ('sticker','video_note'):payload['caption']=body
            steps.append(payload)
    if kind=='sound':
        if len(steps)!=1:raise ValueError('sound_only')
        return steps[0]
    return steps


def asset_form(cid,kind,key,data,csrf):
    steps=data if kind=='command' else [data]
    result=f"<form method='post'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='scope' value='{cid}'><input type='hidden' name='kind' value='{kind}'><label>နာမည်</label><input name='name' value='{esc(key)}' required>"
    for i in range(5 if kind=='command' else 1):
        payload=steps[i] if i<len(steps) else {'kind':'text','text':''}
        result+=f"<label>အဆင့် {i+1} · {esc(payload['kind'])}</label><input type='hidden' name='kind{i}' value='{esc(payload['kind'])}'><input type='hidden' name='file{i}' value='{esc(payload.get('file_id',''))}'><textarea name='body{i}'>{esc(payload.get('text',payload.get('caption','')))}</textarea>"
    return result+"<button name='action' value='save'>သိမ်းမယ်</button><button name='action' value='delete'>ဖျက်မယ်</button></form>"


def register(app,bot):
    global STARTED
    initialize()
    from features.owner_dashboard import _protect,_shell,_csrf,_verify_csrf
    bp=Blueprint('group_studio',__name__,url_prefix='/owner/studio')
    @bp.route('/',methods=['GET','POST'])
    @_protect
    def web():
        notice='';cid=0
        try:
            cid=int((request.form if request.method=='POST' else request.args).get('scope',0))
            from features.owner_controls import check_scope
            check_scope(cid)
            if request.method=='POST':
                _verify_csrf();action=request.form.get('action','save')
                uid=int(os.getenv('OWNER_TELEGRAM_ID','0'))
                with get_db_connection() as con,con.cursor() as cur:
                    if action.startswith('capsule_'):
                        mid=int(request.form.get('id','0'))
                        if action=='capsule_cancel':
                            cur.execute("UPDATE group_studio_jobs SET status='cancelled' WHERE id=%s AND scope=%s AND kind='capsule' AND status='pending' RETURNING id",(mid,cid))
                        elif action=='capsule_date':
                            date=when(request.form.get('date','').replace('T',' '))
                            cur.execute("UPDATE group_studio_jobs SET due_at=%s WHERE id=%s AND scope=%s AND kind='capsule' AND status='pending' RETURNING id",(date,mid,cid))
                        else:abort(400)
                        if not cur.fetchone():raise ValueError('not_found')
                    elif action.startswith('memory_'):
                        mid=int(request.form.get('id','0'))
                        if action=='memory_delete':cur.execute('DELETE FROM group_studio_memories WHERE id=%s AND scope=%s RETURNING id',(mid,cid))
                        elif action=='memory_save':cur.execute('UPDATE group_studio_memories SET title=%s WHERE id=%s AND scope=%s RETURNING id',(request.form.get('title','')[:120],mid,cid))
                        else:abort(400)
                        if not cur.fetchone():raise ValueError('not_found')
                    else:
                        kind=request.form.get('kind');key=name(request.form.get('name',''))
                        if kind not in ('command','sound'):abort(400)
                        if action=='delete':cur.execute('DELETE FROM group_studio_assets WHERE scope=%s AND kind=%s AND name=%s',(cid,kind,key))
                        elif action=='save':
                            data=form_payloads(request.form,kind)
                            if kind=='command':
                                if key in BUILTINS:raise ValueError('reserved')
                                if not isinstance(data,list) or not 1<=len(data)<=cfg('command_steps',cid):raise ValueError('limit')
                                for p in data:validate(p)
                                cur.execute('DELETE FROM group_studio_assets WHERE scope=%s AND kind=%s AND name=%s',(cid,kind,key))
                            elif data.get('kind') not in ('voice','audio'):raise ValueError('sound_only')
                            asset_save(cur,cid,kind,key,data,uid)
                        else:abort(400)
                notice=text('saved')
        except (ValueError,TypeError,KeyError) as exc:notice=text(str(exc)) if str(exc) in MESSAGES else text('error')
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute('SELECT chat_id,title FROM owner_groups WHERE active ORDER BY title');groups=cur.fetchall()
            cur.execute('SELECT kind,name,data FROM group_studio_assets WHERE scope=%s ORDER BY kind,name',(cid,));assets=cur.fetchall()
            cur.execute("SELECT id,due_at,status FROM group_studio_jobs WHERE scope=%s AND kind='capsule' ORDER BY id DESC LIMIT 30",(cid,));caps=cur.fetchall()
            cur.execute('SELECT id,title FROM group_studio_memories WHERE scope=%s ORDER BY id DESC LIMIT 30',(cid,));mems=cur.fetchall()
        options="<option value='0'>Group အားလုံးအတွက် default</option>"+''.join(f"<option value='{gid}' {'selected' if gid==cid else ''}>{esc(title)}</option>" for gid,title in groups)
        body=f"<h1>Group Studio</h1><p>{esc(notice)}</p><form method='get'><select name='scope'>{options}</select><button>ရွေးမယ်</button></form><p><a href='/owner/control?category=Group%20Studio'>စာသားနှင့် Settings ပြင်ရန်</a></p><pre>{esc(text('help'))}</pre>"
        body+="<section class='panel'><h2>Command အသစ်ဖန်တီးမယ်</h2><p>စာသားအဆင့်တွေဖြည့်ပါ။ မလိုသောအဆင့်ကို အလွတ်ထားပါ။ Sticker/voice ပါချင်လျှင် Telegram မှ reply နဲ့သိမ်းပြီး ဒီနေရာက ပြန်ပြင်နိုင်သည်။ {name}, {user}, {group}, {args} အသုံးပြုနိုင်သည်။</p>"+asset_form(cid,'command','',[],_csrf())+'</section>'
        for kind,key,data in assets:
            body+=f"<section class='panel'><h2>{esc(kind)} · {esc(key)}</h2>"+asset_form(cid,kind,key,data,_csrf())+'</section>'
        body+='<h2>အချိန် Capsules</h2>'
        for mid,date,status in caps:
            body+=f"<div class='panel'><p>#{mid} · {esc(STATUS.get(status,status))}</p>"
            if status=='pending':
                body+=f"<form method='post'><input type='hidden' name='csrf' value='{esc(_csrf())}'><input type='hidden' name='scope' value='{cid}'><input type='hidden' name='id' value='{mid}'><label>မြန်မာအချိန်</label><input type='datetime-local' name='date' value='{date.astimezone(MMT):%Y-%m-%dT%H:%M}'><button name='action' value='capsule_date'>အချိန်ပြင်မယ်</button><button name='action' value='capsule_cancel'>ပယ်ဖျက်မယ်</button></form>"
            body+='</div>'
        body+='<h2>အမှတ်တရ</h2>'
        for mid,label in mems:
            body+=f"<form class='panel' method='post'><input type='hidden' name='csrf' value='{esc(_csrf())}'><input type='hidden' name='scope' value='{cid}'><input type='hidden' name='id' value='{mid}'><label>#{mid}</label><input name='title' value='{esc(label)}'><button name='action' value='memory_save'>ခေါင်းစဉ်ပြင်မယ်</button><button name='action' value='memory_delete'>ဖျက်မယ်</button></form>"
        return _shell(body)
    app.register_blueprint(bp)

    @bot.message_handler(commands=['studio','capsule','capsules','capsulecancel','soundadd','sounddel','sounds','sound','memorysave','memories','memory','memorybook','memorydel','commandadd','commandappend','commanddel','commands'])
    def studio_command(m):
        try:
            cmd=m.text.split()[0].split('@')[0].lstrip('/');args=m.text.split(maxsplit=1)[1] if len(m.text.split(maxsplit=1))>1 else ''
            if cmd=='studio':return bot.reply_to(m,text('help'))
            managing=cmd in ('soundadd','sounddel','commandadd','commandappend','commanddel','sounds','commands')
            cid=scope(m,manage=managing);uid=m.from_user.id
            section='capsules' if cmd.startswith('capsule') else 'sounds' if cmd.startswith('sound') else 'memories' if cmd.startswith('memor') else 'commands'
            if not cfg(section+'_enabled',cid):raise ValueError('disabled')
            admin=is_admin(bot,cid,uid) if cmd in ('soundadd','sounddel','commandadd','commandappend','commanddel','capsulecancel','memorydel') else False
            if cmd in ('soundadd','sounddel','commandadd','commandappend','commanddel') and not admin:raise ValueError('admin')
            with get_db_connection() as con,con.cursor() as cur:
                if cmd=='capsule':
                    if not m.reply_to_message:raise ValueError('reply')
                    date=when(args);payload=capture(m.reply_to_message)
                    cur.execute('SELECT pg_advisory_xact_lock(759012353)')
                    cur.execute("SELECT COUNT(*) FROM group_studio_jobs WHERE scope=%s AND creator=%s AND kind='capsule' AND status='pending'",(cid,uid))
                    if cur.fetchone()[0]>=cfg('capsule_limit',cid):raise ValueError('limit')
                    jid=enqueue(cur,f'capsule:{cid}:{m.message_id}',cid,uid,payload,date,'capsule')
                    result=text('capsule_saved',id=jid or 'ရှိပြီးသား',date=date.strftime('%Y-%m-%d %H:%M'))
                elif cmd=='capsules':
                    cur.execute("SELECT id,due_at,status FROM group_studio_jobs WHERE scope=%s AND creator=%s AND kind='capsule' ORDER BY id DESC LIMIT 30",(cid,uid))
                    result='\n'.join(f'#{i} · {d.astimezone(MMT):%Y-%m-%d %H:%M} · {STATUS.get(status,status)}' for i,d,status in cur.fetchall()) or text('empty')
                elif cmd=='capsulecancel':
                    cur.execute("UPDATE group_studio_jobs SET status='cancelled' WHERE id=%s AND scope=%s AND kind='capsule' AND status='pending' AND (creator=%s OR %s) RETURNING id",(int(args),cid,uid,admin))
                    if not cur.fetchone():raise ValueError('not_found')
                    result=text('deleted')
                elif cmd in ('soundadd','commandadd','commandappend'):
                    key=name(args)
                    if not m.reply_to_message:raise ValueError('reply')
                    payload=capture(m.reply_to_message)
                    if cmd=='soundadd' and payload['kind'] not in ('voice','audio'):raise ValueError('sound_only')
                    asset_save(cur,cid,'sound' if cmd=='soundadd' else 'command',key,payload if cmd=='soundadd' else [payload],uid,cmd=='commandappend');result=text('saved')
                elif cmd in ('sounddel','commanddel'):
                    cur.execute('DELETE FROM group_studio_assets WHERE scope=%s AND kind=%s AND name=%s RETURNING name',(cid,'sound' if cmd=='sounddel' else 'command',name(args)))
                    if not cur.fetchone():raise ValueError('not_found')
                    result=text('deleted')
                elif cmd in ('sounds','commands'):
                    cur.execute('SELECT DISTINCT name FROM group_studio_assets WHERE scope IN (0,%s) AND kind=%s ORDER BY name LIMIT 100',(cid,'sound' if cmd=='sounds' else 'command'))
                    result='\n'.join(('/sound ' if cmd=='sounds' else '/')+r[0] for r in cur.fetchall()) or text('empty')
                elif cmd=='sound':
                    payload=asset(cur,cid,'sound',name(args))
                    if not payload:raise ValueError('not_found')
                    throttle(cur,cid,uid,'sound',cfg('sound_cooldown',cid));enqueue(cur,f'sound:{cid}:{m.message_id}',cid,uid,payload);result=text('saved')
                elif cmd=='memorysave':
                    if not m.reply_to_message:raise ValueError('reply')
                    cur.execute('SELECT pg_advisory_xact_lock(759012354)')
                    cur.execute('SELECT COUNT(*) FROM group_studio_memories WHERE scope=%s',(cid,))
                    if cur.fetchone()[0]>=cfg('memory_limit',cid):raise ValueError('limit')
                    cur.execute('INSERT INTO group_studio_memories(scope,creator,title,payload,request_key) VALUES(%s,%s,%s,%s::jsonb,%s) ON CONFLICT(request_key) DO UPDATE SET title=group_studio_memories.title RETURNING id',(cid,uid,args[:120] or getattr(m.reply_to_message.from_user,'first_name',None) or 'အမှတ်တရ',json.dumps(capture(m.reply_to_message),ensure_ascii=False),f'memory:{cid}:{m.message_id}'))
                    result=text('memory_saved',id=cur.fetchone()[0])
                elif cmd=='memories':
                    cur.execute('SELECT id,title FROM group_studio_memories WHERE scope=%s ORDER BY id DESC LIMIT 40',(cid,));result='\n'.join(f'#{i} · {label}' for i,label in cur.fetchall()) or text('empty')
                elif cmd=='memory':
                    cur.execute('SELECT payload FROM group_studio_memories WHERE scope=%s AND id=%s',(cid,int(args)));row=cur.fetchone()
                    if not row:raise ValueError('not_found')
                    enqueue(cur,f'memory:{cid}:{m.message_id}',cid,uid,row[0]);result=text('saved')
                elif cmd=='memorydel':
                    cur.execute('DELETE FROM group_studio_memories WHERE scope=%s AND id=%s AND (creator=%s OR %s) RETURNING id',(cid,int(args),uid,admin))
                    if not cur.fetchone():raise ValueError('not_found')
                    result=text('deleted')
                else:
                    if args and not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',args):raise ValueError('date')
                    cur.execute("SELECT id,title,payload,created_at FROM group_studio_memories WHERE scope=%s AND (%s='' OR to_char(created_at AT TIME ZONE 'Asia/Yangon','YYYY-MM')=%s) ORDER BY id DESC LIMIT %s",(cid,args,args,cfg('book_limit',cid)))
                    rows=list(reversed(cur.fetchall()))
                    if not rows:raise ValueError('empty')
                    images={}
                    from PIL import Image
                    for mid,label,payload,created in rows[-20:]:
                        if payload['kind']!='photo':continue
                        try:
                            file=bot.get_file(payload['file_id'])
                            if getattr(file,'file_size',0)>8000000:continue
                            raw=bot.download_file(file.file_path)
                            with Image.open(io.BytesIO(raw)) as photo:
                                if photo.width*photo.height>20000000:continue
                                photo.thumbnail((720,720));out=io.BytesIO();photo.convert('RGB').save(out,'JPEG',quality=75)
                                images[mid]=base64.b64encode(out.getvalue()).decode()
                        except Exception as exc:LOG.warning('Memory thumbnail: %s',type(exc).__name__)
                    data=io.BytesIO(book(rows,text('book'),images));data.name='group_memories.html';bot.send_document(cid,data,caption=text('book'));return
            bot.reply_to(m,result)
        except Exception as exc:
            code=str(exc)
            if code not in MESSAGES:LOG.warning('Studio command: %s',type(exc).__name__);code='error'
            bot.reply_to(m,text(code))

    # Register after built-in bot handlers with register_custom_handler().
    def custom_command(m):
        if not m.from_user or m.from_user.is_bot:return ContinueHandling()
        first=m.text.split()[0];parts=first[1:].split('@',1)
        if len(parts)>1 and parts[1].casefold()!=bot.get_me().username.casefold():return ContinueHandling()
        key=parts[0].casefold()
        if key in BUILTINS or not NAME.fullmatch(key):return ContinueHandling()
        cid=m.chat.id if m.chat.type in ('group','supergroup') else 0
        if not cfg('commands_enabled',cid):return ContinueHandling()
        try:
            with get_db_connection() as con,con.cursor() as cur:
                data=asset(cur,cid,'command',key)
                if not data:return ContinueHandling()
                from features.owner_operations import feature_allowed
                if not feature_allowed('enabled.features.group_studio.custom_command',cid):raise ValueError('disabled')
                throttle(cur,cid,m.from_user.id,'command',cfg('command_cooldown',cid))
                fields=dict(name=m.from_user.first_name,user=m.from_user.first_name,group=getattr(m.chat,'title',None) or 'Private',args=m.text.split(maxsplit=1)[1] if len(m.text.split(maxsplit=1))>1 else '')
                chain=f'custom:{m.chat.id}:{m.message_id}'
                for i,payload in enumerate(data):enqueue(cur,chain+':'+str(i),m.chat.id,m.from_user.id,{'chain':chain,'content':substitute(payload,fields)},datetime.fromtimestamp(time.time()+i*3,timezone.utc),'chain')
        except Exception as exc:bot.reply_to(m,text(str(exc) if str(exc) in MESSAGES else 'error'))
        return ContinueHandling()
    bot._studio_custom_handler=custom_command
    if not STARTED:
        STARTED=True
        def loop():
            while True:
                WORK_WAKE.clear();wait=60
                try:
                    run_jobs(bot)
                    due=db_work.next_due("SELECT MIN(due_at) FROM group_studio_jobs WHERE status='pending'")
                    wait=db_work.delay(due)
                except Exception as exc:LOG.warning('Studio worker: %s',type(exc).__name__)
                WORK_WAKE.wait(wait)
        threading.Thread(target=loop,name='group-studio',daemon=True).start()


def register_custom_handler(bot):
    # Imposter secret guesses are registered through a predicate rather than commands.
    BUILTINS.update({"secret", "ဖြေမယ်"})
    for h in bot.message_handlers:
        BUILTINS.update(h.get('filters',{}).get('commands',[]))
    bot.message_handler(func=lambda m:bool(m.text and m.text.startswith('/')),content_types=['text'])(bot._studio_custom_handler)
    # Built-ins are excluded by the registry. Run before broad legacy text filters.
    if isinstance(bot.message_handlers,list):bot.message_handlers.insert(0,bot.message_handlers.pop())
