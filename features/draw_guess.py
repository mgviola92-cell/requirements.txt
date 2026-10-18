from core import db_work
"""Draw & Guess Mini App and Telegram UI with private authenticated drawing tickets."""
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import random
import secrets
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qsl
from PIL import Image
from flask import Blueprint,request,jsonify,Response,send_file
from telebot import types
from telebot.handler_backends import ContinueHandling
from database.db import get_db_connection
from core import telegram_media
from core.customization import message_text,setting_value,group_scope
from core.sessions import start_session,end_session
from games import draw_guess as g

WAKE=db_work.signal('draw_guess_games','draw_guess_outbox')
LOG=logging.getLogger(__name__)
ACTIVE=set();STARTED=False;USERNAME=None
MESSAGES={'title':'🎨 Draw & Guess','lobby':'🎨 Draw & Guess\nလူစုနေသည် — {count}/{maximum}\nPrivate ခလုတ်ဖွင့်ပြီး ပါဝင်မှုအတည်ပြုပါ။ အနည်းဆုံး {minimum} ယောက်။',
 'open':'🎨 ဂိမ်းခန်းဖွင့်မယ်','join':'➕ Join အတည်ပြုမယ်','begin':'▶️ စမယ် (Admin)','stop':'🛑 ရပ်မယ် (Admin)',
 'round':'🎨 Round {round}/{rounds}\nပုံဆွဲသူ — {name}\nပုံရောက်လာလျှင် ဒီ Group ထဲတွင် အဖြေကိုရေးပါ။',
 'drawing':'သင်ပုံဆွဲရမည့်အလှည့်ဖြစ်သည်။ Canvas ခလုတ်ကိုဖွင့်ပါ။ အဖြေကို Group ထဲ မရေးပါနှင့်။',
 'canvas':'🖌️ Canvas ဖွင့်မယ်','waiting':'Group ထဲမှာ ပုံကြည့်ပြီး ခန့်မှန်းပါ။','hint':'စကားလုံးကိုစာနဲ့မရေးဘဲ ပုံနဲ့ပဲရှင်းပြပါ။',
 'correct':'✅ {name} မှန်ပြီ! အဖြေ — {word}','timeout':'⏱️ အချိန်ကုန်ပြီ။ အဖြေ — {word}',
 'result':'🏁 Draw & Guess ပွဲပြီးပြီ\n{scores}','cancelled':'Draw & Guess ကို ဖျက်သိမ်းလိုက်သည်။',
 'saved':'✅ ပုံကို Group ဆီပို့ရန် သိမ်းပြီးပြီ။','joined':'✅ ပါဝင်ပြီးပြီ။','closed':'ဒီအလှည့်ပိတ်သွားပြီ။ Group မှ ဂိမ်းခန်းကိုပြန်ဖွင့်ပါ။',
 'minimum':'လူအနည်းဆုံး မပြည့်သေးပါ။','full':'လူပြည့်သွားပြီ။','admin':'Group Admin သို့မဟုတ် Owner သာစ/ရပ်နိုင်သည်။',
 'group':'/draw ကို Group ထဲတွင်သုံးပါ။','busy':'တခြားဂိမ်းရှိနေသည်။ ပြီးမှစပါ။','auth':'Telegram private chat မှ Canvas ကိုဖွင့်ပါ။',
 'image':'ပုံအရွယ်အစား သို့မဟုတ် format မမှန်ပါ။','rate':'ခဏစောင့်ပြီး ထပ်ပို့ပါ။','error':'ခေတ္တ မသိမ်းနိုင်သေးပါ။ ပြန်စမ်းပါ။',
 'confirm_stop':'ပွဲကိုဖျက်သိမ်းရန် အတည်ပြုမလား?','yes_stop':'ဖျက်သိမ်းမယ်',
 'brush_eraser':'ခဲဖျက်','brush_undo':'နောက်ပြန်','brush_clear':'ရှင်းမယ်','brush_send':'Group ဆီပို့မယ်','brush_loading':'ပို့နေသည်…','brush_clear_confirm':'ပုံကိုရှင်းမလား?','brush_expired':'အချိန်ကုန်ပြီ။ Group ထဲပြန်သွားပါ။',
 'rules':'🎨 Draw & Guess\nGroup တွင် /draw ပို့ → Private ဂိမ်းခန်းဖွင့် → Join အတည်ပြုပါ။ အနည်းဆုံး ၂ ယောက်။ ပုံဆွဲသူ အလှည့်ကျပြောင်းသည်။\nပုံဆွဲသူသာ Canvas တွင် အဖြေမြင်ရသည်။ ပုံပို့ပြီးနောက် ကျန်သူတွေက Group ထဲအဖြေရေးပါ။ ပထမမှန်သူနှင့် ပုံဆွဲသူ reward ရသည်။\nဆက်ဆွဲထားသည့်ပုံကို ၁၀ စက္ကန့်တိုင်း ပြန်ပို့နိုင်သည်။ ပုံတစ်ခုတည်းကိုပြင်သုံးသည်။ စကားလုံးကိုစာနဲ့မရေးရ။ /drawstop ဖြင့် Admin ရပ်နိုင်သည်။'}


def text(k,**fields):return message_text('msg.features.draw_guess.'+k,MESSAGES[k],fields)
def cfg(cid):return {k:setting_value('cfg.features.draw_guess.'+k,v,cid) for k,v in g.DEFAULTS.items()}
def words(cid):
    values=setting_value('cfg.features.draw_guess.words',[w for w,_ in g.WORDS],cid)
    aliases=dict(g.WORDS);return [(w,aliases.get(w,[])) for w in values]
def bank(s):return s.get('words') or words(s['chat_id'])
def callback(s,action):return f"dg:{s['id']}:{s['epoch']}:{action}"
def base_url():return os.getenv('RENDER_EXTERNAL_URL',os.getenv('PUBLIC_URL','https://requirements-txt-2keq.onrender.com')).rstrip('/')


def authenticate(raw,token,now=None):
    pairs=parse_qsl(raw,keep_blank_values=True)
    if len(pairs)!=len({k for k,v in pairs}):raise ValueError('auth')
    data=dict(pairs);supplied=data.pop('hash','')
    key=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
    expected=hmac.new(key,'\n'.join(k+'='+v for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(expected,supplied):raise ValueError('auth')
    try:
        age=(time.time() if now is None else now)-int(data['auth_date']);user=json.loads(data['user'])
        if not -30<=age<=3600 or type(user['id']) is not int or user.get('is_bot'):raise ValueError('auth')
        return user['id']
    except (KeyError,TypeError,ValueError):raise ValueError('auth')


def png(raw):
    if not isinstance(raw,str) or not raw.startswith('data:image/png;base64,') or len(raw)>1500000:raise ValueError('image')
    try:
        data=base64.b64decode(raw.split(',',1)[1],validate=True)
        with Image.open(io.BytesIO(data)) as im:
            if im.format!='PNG' or im.size!=(760,500):raise ValueError('image')
            im.load();out=io.BytesIO();im.convert('RGB').save(out,'PNG');return base64.b64encode(out.getvalue()).decode()
    except Exception:raise ValueError('image')


def init_db():
    telegram_media.initialize()
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('CREATE TABLE IF NOT EXISTS draw_guess_games(chat_id BIGINT PRIMARY KEY,game_id TEXT UNIQUE NOT NULL,state JSONB NOT NULL,updated_at TIMESTAMPTZ DEFAULT NOW())')
        cur.execute('CREATE TABLE IF NOT EXISTS draw_guess_outbox(id BIGSERIAL PRIMARY KEY,game_id TEXT NOT NULL,event JSONB NOT NULL,done BOOLEAN NOT NULL DEFAULT FALSE,attempts INTEGER NOT NULL DEFAULT 0,next_try TIMESTAMPTZ DEFAULT NOW())')
        cur.execute('CREATE INDEX IF NOT EXISTS draw_guess_outbox_due ON draw_guess_outbox(next_try) WHERE NOT done')
        cur.execute('CREATE TABLE IF NOT EXISTS draw_guess_images(game_id TEXT NOT NULL,epoch INTEGER NOT NULL,image TEXT NOT NULL,PRIMARY KEY(game_id,epoch))')
        # Move legacy embedded drawings once; timers will subsequently read only the small state.
        cur.execute("""INSERT INTO draw_guess_images(game_id,epoch,image)
            SELECT game_id,(state->>'epoch')::integer,state->>'image' FROM draw_guess_games
            WHERE state->>'image' IS NOT NULL
            ON CONFLICT(game_id,epoch) DO UPDATE SET image=EXCLUDED.image""")
        cur.execute("""UPDATE draw_guess_games SET state=jsonb_set(jsonb_set(state,'{image_epoch}',state->'epoch'),'{image}','null'::jsonb)
            WHERE state->>'image' IS NOT NULL""")
        cur.execute("""DELETE FROM draw_guess_images i WHERE NOT EXISTS(
            SELECT 1 FROM draw_guess_games g WHERE g.game_id=i.game_id
            AND (g.state->>'epoch')::integer=i.epoch AND g.state->>'phase' NOT IN ('finished','cancelled'))""")



@contextmanager
def tx(cid=None,gid=None):
    with get_db_connection() as con,con.cursor() as cur:
        if gid:
            cur.execute('SELECT chat_id FROM draw_guess_games WHERE game_id=%s',(gid,));row=cur.fetchone()
            if not row:raise ValueError('closed')
            cid=row[0]
        cur.execute('SELECT pg_advisory_xact_lock(%s)',(cid,))
        cur.execute('SELECT state FROM draw_guess_games WHERE chat_id=%s FOR UPDATE',(cid,));row=cur.fetchone();s=row[0] if row else None
        if gid and (not s or s['id']!=gid):raise ValueError('closed')
        yield cur,s,cid


def persist(cur,s,now):
    WAKE.set()
    s['updated']=now
    if s['phase'] in ('finished','cancelled'):
        cur.execute('DELETE FROM draw_guess_images WHERE game_id=%s',(s['id'],))
    elif any(e['kind']=='round' for e in s['events']):
        cur.execute('DELETE FROM draw_guess_images WHERE game_id=%s AND epoch<>%s',(s['id'],s['epoch']))
    stored=dict(s)
    if s.get('image'):
        cur.execute('INSERT INTO draw_guess_images VALUES(%s,%s,%s) ON CONFLICT(game_id,epoch) DO UPDATE SET image=EXCLUDED.image WHERE draw_guess_images.image IS DISTINCT FROM EXCLUDED.image',(s['id'],s['epoch'],s['image']))
        s['image_epoch']=s['epoch'];stored['image_epoch']=s['epoch']
    stored['image']=None
    for e in s['events']:
        if e['kind']=='cancelled':
            e['chat_id']=s['chat_id'];e['messages']=cleanup_targets(s)
        e['epoch']=s['epoch'];e['round']=s['round']
        cur.execute('INSERT INTO draw_guess_outbox(game_id,event) VALUES(%s,%s::jsonb)',(s['id'],json.dumps(e,ensure_ascii=False)))
    s['events']=[];stored['events']=[]
    cur.execute('INSERT INTO draw_guess_games VALUES(%s,%s,%s::jsonb,NOW()) ON CONFLICT(chat_id) DO UPDATE SET game_id=EXCLUDED.game_id,state=EXCLUDED.state,updated_at=NOW()',(s['chat_id'],s['id'],json.dumps(stored,ensure_ascii=False)))
    from features.group_studio import credit
    for a in s['awards']:credit(cur,a['key'],s['chat_id'],int(a['uid']),a['points'])
    s['awards']=[]
    cur.execute("UPDATE draw_guess_games SET state=jsonb_set(state,'{awards}','[]'::jsonb) WHERE game_id=%s",(s['id'],))


def drawing(cur,s):
    if s.get('image'):return s['image']  # compatibility with a transaction started before migration
    if s.get('image_epoch')!=s.get('epoch'):return None
    cur.execute('SELECT image FROM draw_guess_images WHERE game_id=%s AND epoch=%s',(s['id'],s['epoch']))
    row=cur.fetchone()
    return row[0] if row else None


def refresh_points(cid):
    from database.players import player_stats,player_stats_lock
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('SELECT user_id,points,games,wins,losses,draws FROM player_stats WHERE chat_id=%s',(cid,));rows=cur.fetchall()
    with player_stats_lock:
        for row in rows:player_stats[(cid,row[0])]=dict(zip(('points','games','wins','losses','draws'),row[1:]))


def link(bot,s):
    global USERNAME
    if USERNAME is None:USERNAME=bot.get_me().username
    return types.InlineKeyboardButton(text('open'),url=f"https://t.me/{USERNAME}?start=dg_{s['id']}")
def panel(bot,s):
    k=types.InlineKeyboardMarkup();k.add(link(bot,s))
    if s['phase']=='lobby':
        k.add(types.InlineKeyboardButton(text('begin'),callback_data=callback(s,'begin')),types.InlineKeyboardButton(text('stop'),callback_data=callback(s,'stop')))
        body=text('lobby',count=len(s['players']),maximum=s['rules']['max_players'],minimum=s['rules']['min_players'])
    else:body=text('round',round=s['round'],rounds=s['rules']['rounds'],name=g.player(s,s['drawer'])['name'])
    return body,k

def remember(s,cid,message):
    mid=getattr(message,'message_id',None)
    if type(mid) is not int:return
    item={'chat':int(cid),'message':mid}
    records=s.setdefault('messages',[])
    if item not in records:records.append(item)


def cleanup_targets(s):
    result=list(s.get('messages',[]))
    for key in ('lobby_card','card'):
        if type(s.get(key)) is int:
            item={'chat':s['chat_id'],'message':s[key]}
            if item not in result:result.append(item)
    return result


def delete_messages(bot,records):
    for item in records:
        try:bot.delete_message(item['chat'],item['message'])
        except Exception as exc:
            description=str(exc).lower()
            if 'message to delete not found' in description or 'message_id_invalid' in description:continue
            raise


def private(bot,cur,s,uid):
    k=types.InlineKeyboardMarkup()
    if s['phase']=='lobby':
        k.add(types.InlineKeyboardButton(text('join'),callback_data=callback(s,'join')));m=bot.send_message(uid,text('lobby',count=len(s['players']),maximum=s['rules']['max_players'],minimum=s['rules']['min_players']),reply_markup=k);remember(s,uid,m);return
    if s['phase'] in ('finished','cancelled'):raise ValueError('closed')
    if str(uid)!=s['drawer']:m=bot.send_message(uid,text('waiting'));remember(s,uid,m);return
    if not s['ticket']:s['ticket']=secrets.token_urlsafe(32)
    url=base_url()+f"/draw/play?game={s['id']}&ticket={s['ticket']}"
    k.add(types.InlineKeyboardButton(text('canvas'),web_app=types.WebAppInfo(url)))
    m=bot.send_message(uid,text('drawing'),reply_markup=k);remember(s,uid,m)


def drain(bot):
    for _ in range(30):
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute('SELECT id,game_id,event,attempts FROM draw_guess_outbox WHERE NOT done AND next_try<=NOW() ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED');row=cur.fetchone()
            if not row:return
            oid,gid,e,attempts=row
            if e['kind']=='cancelled' and 'messages' in e:
                try:
                    delete_messages(bot,e['messages'])
                    with group_scope(e['chat_id']):m=bot.send_message(e['chat_id'],text('cancelled'))
                    job={'kind':'delete','messages':[{'chat':e['chat_id'],'message':m.message_id}]}
                    cur.execute("INSERT INTO draw_guess_outbox(game_id,event,next_try) VALUES(%s,%s::jsonb,NOW()+INTERVAL '10 seconds')",(gid,json.dumps(job)))
                    cur.execute('UPDATE draw_guess_outbox SET done=TRUE WHERE id=%s',(oid,))
                except Exception as exc:
                    cur.execute("UPDATE draw_guess_outbox SET attempts=attempts+1,done=%s,next_try=NOW()+INTERVAL '10 seconds' WHERE id=%s",(attempts>=8,oid))
                    LOG.warning('Draw cancellation cleanup: %s',type(exc).__name__)
                continue
            if e['kind']=='delete':
                try:
                    delete_messages(bot,e['messages'])
                    cur.execute('UPDATE draw_guess_outbox SET done=TRUE WHERE id=%s',(oid,))
                except Exception as exc:
                    cur.execute("UPDATE draw_guess_outbox SET attempts=attempts+1,done=%s,next_try=NOW()+INTERVAL '10 seconds' WHERE id=%s",(attempts>=8,oid))
                    LOG.warning('Draw cleanup: %s',type(exc).__name__)
                continue
            cur.execute('SELECT MAX(id) FROM draw_guess_outbox WHERE game_id=%s',(gid,));watermark=cur.fetchone()[0]
            # State row lock keeps drawer-ticket creation consistent with callbacks.
            cur.execute('SELECT state FROM draw_guess_games WHERE game_id=%s FOR UPDATE',(gid,));row=cur.fetchone()
            if not row:cur.execute('UPDATE draw_guess_outbox SET done=TRUE WHERE id=%s',(oid,));continue
            s=row[0];cid=s['chat_id'];kind=e['kind']
            if kind in ('round','drawer','image','correct','timeout') and s['phase']=='cancelled':
                cur.execute('UPDATE draw_guess_outbox SET done=TRUE WHERE id=%s',(oid,));continue
            if kind in ('round','drawer','image') and (e['epoch']!=s['epoch'] or e['round']!=s['round']):
                cur.execute('UPDATE draw_guess_outbox SET done=TRUE WHERE id=%s',(oid,));continue
            if kind not in ('drawer','cancelled') and time.time()<s.get('last_send',0)+3.2:
                cur.execute("UPDATE draw_guess_outbox SET next_try=NOW()+INTERVAL '4 seconds' WHERE id=%s",(oid,));continue
            try:
                with group_scope(cid):
                    if kind=='drawer':private(bot,cur,s,int(e['uid']))
                    elif kind=='round':
                        body,k=panel(bot,s)
                        if s.get('lobby_card') and s['phase']=='lobby':bot.edit_message_text(body,cid,s['lobby_card'],reply_markup=k)
                        else:
                            m=bot.send_message(cid,body,reply_markup=k);remember(s,cid,m)
                            if s['phase']=='lobby':s['lobby_card']=m.message_id
                    elif kind=='image':
                        data=io.BytesIO(base64.b64decode(drawing(cur,s)));data.name='drawing.png';body=text('round',round=s['round'],rounds=s['rules']['rounds'],name=g.player(s,s['drawer'])['name'])
                        if s.get('card'):telegram_media.edit_photo(bot,cid,s['card'],data,caption=body)
                        else:
                            m=telegram_media.send_photo(bot,cid,data,caption=body);s['card']=m.message_id;remember(s,cid,m)
                        cur.execute("UPDATE draw_guess_outbox SET done=TRUE WHERE game_id=%s AND event->>'kind'='image' AND id<=%s",(gid,watermark))
                    elif kind=='correct':m=bot.send_message(cid,text('correct',name=g.player(s,e['uid'])['name'],word=e['word']));remember(s,cid,m)
                    elif kind=='timeout':m=bot.send_message(cid,text('timeout',word=e['word']));remember(s,cid,m)
                    elif kind=='result':bot.send_message(cid,text('result',scores='\n'.join(p['name']+' — '+str(p['score']) for p in sorted(s['players'],key=lambda p:-p['score']))))
                    else:
                        delete_messages(bot,cleanup_targets(s))
                        m=bot.send_message(cid,text('cancelled'))
                        job={'kind':'delete','messages':[{'chat':cid,'message':m.message_id}]}
                        cur.execute("INSERT INTO draw_guess_outbox(game_id,event,next_try) VALUES(%s,%s::jsonb,NOW()+INTERVAL '10 seconds')",(gid,json.dumps(job)))
                        s['messages']=[];s['lobby_card']=None;s['card']=None
                if kind!='drawer':s['last_send']=time.time()
                cur.execute('UPDATE draw_guess_games SET state=%s::jsonb WHERE game_id=%s',(json.dumps(s,ensure_ascii=False),gid))
                cur.execute('UPDATE draw_guess_outbox SET done=TRUE WHERE id=%s',(oid,))
            except Exception as exc:
                modified='message is not modified' in str(exc)
                permanent=getattr(exc,'error_code',None) in (400,403)
                cur.execute("UPDATE draw_guess_outbox SET attempts=attempts+1,done=%s,next_try=NOW()+INTERVAL '10 seconds' WHERE id=%s",(modified or permanent or attempts>=6,oid))
                LOG.warning('Draw delivery: %s',type(exc).__name__)


def tick(bot):
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute("SELECT chat_id FROM draw_guess_games WHERE state->>'phase' NOT IN ('finished','cancelled')");chats=[r[0] for r in cur.fetchall()]
    ACTIVE.clear();ACTIVE.update(chats)
    for cid in chats:
        with tx(cid=cid) as (cur,s,_):
            if not s or s['phase'] in ('finished','cancelled'):continue
            start_session(cid,'draw_guess',recover=True);now=time.time()
            from core.startup_safety import abandoned
            if abandoned(s,now):
                # Supersede unsent phase/DM events; keep deletion cleanup jobs.
                cur.execute("UPDATE draw_guess_outbox SET done=TRUE WHERE game_id=%s AND NOT done AND event->>'kind' NOT IN ('delete','cancelled')",(s['id'],))
                s['events']=[]
                g.cancel(s)
            elif now>s['deadline'] and now-s['updated']>30 and s['phase']!='lobby':
                s['deadline']=now+30;g.event(s,'round');g.event(s,'drawer',uid=s['drawer'])
            else:g.advance(s,now,random.SystemRandom(),bank(s))
            if now < s['deadline'] and not s['events']:
                if now-s.get('updated',0)>=10:cur.execute("UPDATE draw_guess_games SET state=jsonb_set(state,'{updated}',%s::jsonb),updated_at=NOW() WHERE chat_id=%s",(str(now),cid))
            else:
                persist(cur,s,now)
        if s['phase'] in ('finished','cancelled'):end_session(cid,'draw_guess');ACTIVE.discard(cid)
    drain(bot)
    if chats:return True
    # Keep scheduled cleanup/retries responsive after the last game has ended.
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('SELECT EXISTS(SELECT 1 FROM draw_guess_outbox WHERE NOT done)')
        pending=cur.fetchone()
    return bool(pending and pending[0])


def register(app,bot):
    global STARTED
    init_db()
    bp=Blueprint('draw_guess',__name__,url_prefix='/draw')
    @bp.get('/play')
    def play():
        resp=Response((Path(__file__).resolve().parent.parent/'templates/draw_guess.html').read_text(),mimetype='text/html')
        resp.headers['Cache-Control']='no-store';resp.headers['Referrer-Policy']='no-referrer';return resp
    @bp.get('/font')
    def font():return send_file(Path(__file__).resolve().parent.parent/'assets/fonts/myanmar.ttf',mimetype='font/ttf',max_age=86400)
    @bp.post('/api')
    def api():
        if request.content_length and request.content_length>1600000:return jsonify(error=text('image')),413
        try:
            data=request.get_json();uid=authenticate(data.get('init_data',''),os.environ['BOT_TOKEN'])
            with tx(gid=data.get('game')) as (cur,s,cid),group_scope(cid):
                if str(uid)!=s['drawer'] or not s['ticket'] or not hmac.compare_digest(s['ticket'],str(data.get('ticket',''))) or s['phase'] not in ('draw','guess') or time.time()>s['deadline']:raise ValueError('closed')
                if data.get('action')=='image':
                    if time.time()<s.get('last_image',0)+4:raise ValueError('rate')
                    s['image']=png(data.get('image'));g.submit(s,uid,time.time());s['last_image']=time.time();persist(cur,s,time.time())
                elif data.get('action')!='state':raise ValueError('closed')
                image=drawing(cur,s)
                result=dict(labels={k:text('brush_'+k) for k in ('eraser','undo','clear','send','loading','clear_confirm','expired')},word=s['word'],title=text('title'),hint=text('hint'),deadline=s['deadline'],saved=text('saved'),image='data:image/png;base64,'+image if image else None)
            return jsonify(result)
        except Exception as exc:
            key=str(exc) if isinstance(exc,ValueError) and str(exc) in MESSAGES else 'error'
            if key=='error':LOG.warning('Draw API: %s',type(exc).__name__)
            return jsonify(error=text(key)),403 if key in ('auth','closed') else 400
    app.register_blueprint(bp)
    from features.group_studio import is_admin

    def command_impl(m):
        if m.chat.type not in ('group','supergroup'):return bot.reply_to(m,text('group'))
        cmd=m.text.split()[0].split('@')[0].lstrip('/');cid=m.chat.id;reserved=False
        if cmd=='drawrules':return bot.reply_to(m,text('rules'))
        try:
            with tx(cid=cid) as (cur,s,_):
                if cmd=='drawstop':
                    if not s or s['phase'] in ('finished','cancelled'):raise ValueError('closed')
                    if not is_admin(bot,cid,m.from_user.id):raise ValueError('admin')
                    k=types.InlineKeyboardMarkup();k.add(types.InlineKeyboardButton(text('yes_stop'),callback_data=callback(s,'confirmedstop')));msg=bot.reply_to(m,text('confirm_stop'),reply_markup=k);remember(s,cid,msg);persist(cur,s,time.time());return
                if s and s['phase'] not in ('finished','cancelled'):g.event(s,'round')
                else:
                    if not start_session(cid,'draw_guess')[0]:raise ValueError('busy')
                    reserved=True;s=g.create(uuid.uuid4().hex[:12],cid,m.from_user.id,cfg(cid),time.time());s['words']=words(cid);g.event(s,'round');ACTIVE.add(cid)
                persist(cur,s,time.time())
        except Exception as exc:
            if reserved:end_session(cid,'draw_guess')
            bot.reply_to(m,text(str(exc) if str(exc) in MESSAGES else 'error'))

    @bot.message_handler(commands=['draw','drawguess'])
    def command(m):return command_impl(m)

    @bot.message_handler(commands=['drawrules'])
    def rules_command(m):return command_impl(m)

    @bot.message_handler(commands=['drawstop'])
    def stop_command(m):return command_impl(m)

    @bot.message_handler(commands=['start'])
    def private_start(m):
        args=m.text.split()
        if m.chat.type!='private' or len(args)!=2 or not args[1].startswith('dg_'):return ContinueHandling()
        try:
            with tx(gid=args[1][3:]) as (cur,s,cid),group_scope(cid):private(bot,cur,s,m.from_user.id);persist(cur,s,time.time())
        except Exception as exc:bot.reply_to(m,text(str(exc) if str(exc) in MESSAGES else 'error'))

    @bot.callback_query_handler(func=lambda q:(q.data or '').startswith('dg:'))
    def action(q):
        try:
            _,gid,epoch,kind=q.data.split(':');uid=q.from_user.id
            with tx(gid=gid) as (cur,s,cid),group_scope(cid):
                if int(epoch)!=s['epoch'] or s['phase'] in ('finished','cancelled') or time.time()>s['deadline']:raise ValueError('closed')
                if kind=='join':
                    if q.message.chat.type!='private' or q.message.chat.id!=uid or bot.get_chat_member(cid,uid).status in ('left','kicked'):raise ValueError('auth')
                    g.join(s,uid,q.from_user.first_name);g.event(s,'round')
                else:
                    if q.message.chat.id!=cid or not is_admin(bot,cid,uid):raise ValueError('admin')
                    if kind=='begin':g.begin(s,time.time(),random.SystemRandom(),bank(s))
                    elif kind in ('stop','confirmedstop'):
                        if kind=='stop':
                            k=types.InlineKeyboardMarkup();k.add(types.InlineKeyboardButton(text('yes_stop'),callback_data=callback(s,'confirmedstop')));msg=bot.send_message(cid,text('confirm_stop'),reply_markup=k);remember(s,cid,msg)
                        else:
                            remember(s,cid,q.message);g.cancel(s)
                    else:raise ValueError('closed')
                persist(cur,s,time.time())
            if s['phase'] in ('finished','cancelled'):end_session(cid,'draw_guess');ACTIVE.discard(cid)
            bot.answer_callback_query(q.id,text('joined'))
        except Exception as exc:
            try:bot.answer_callback_query(q.id,text(str(exc) if str(exc) in MESSAGES else 'error'),show_alert=True)
            except Exception:pass

    @bot.message_handler(func=lambda m:bool(m.chat.id in ACTIVE and m.text and not m.text.startswith('/')),content_types=['text'])
    def capture_guess(m):
        if not m.from_user or m.from_user.is_bot:return ContinueHandling()
        try:
            matched=False
            with tx(cid=m.chat.id) as (cur,s,cid):
                if s and s.get('card'):matched=g.guess(s,m.from_user.id,m.text,time.time(),random.SystemRandom(),bank(s))
                if matched:persist(cur,s,time.time())
            if matched:
                refresh_points(m.chat.id)
                if s['phase']=='finished':end_session(m.chat.id,'draw_guess');ACTIVE.discard(m.chat.id)
        except Exception as exc:LOG.warning('Draw guess: %s',type(exc).__name__)
        return ContinueHandling()

    @bot.message_handler(content_types=['left_chat_member'])
    def member_left(m):
        if m.chat.id not in ACTIVE:return ContinueHandling()
        try:
            with tx(cid=m.chat.id) as (cur,s,cid):
                p=g.player(s,m.left_chat_member.id) if s else None
                if p:
                    if s['phase']=='lobby':s['players'].remove(p);g.event(s,'round')
                    else:
                        p['active']=False
                        if p['id']==s['drawer']:g.next_round(s,time.time(),random.SystemRandom(),bank(s))
                        elif sum(p['active'] for p in s['players'])<2:g.finish(s)
                    persist(cur,s,time.time())
            if s and s['phase'] in ('finished','cancelled'):end_session(m.chat.id,'draw_guess');ACTIVE.discard(m.chat.id)
        except Exception as exc:LOG.warning('Draw departure: %s',type(exc).__name__)
        return ContinueHandling()
    if not STARTED:
        STARTED=True
        def loop():
            while True:
                WAKE.clear();active=True
                try:active=tick(bot)
                except Exception as exc:LOG.warning('Draw worker: %s',type(exc).__name__)
                WAKE.wait(3 if active else db_work.delay())
        # Restore group guards before polling.
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute("SELECT chat_id FROM draw_guess_games WHERE state->>'phase' NOT IN ('finished','cancelled')")
            for r in cur.fetchall():ACTIVE.add(r[0]);start_session(r[0],'draw_guess',recover=True)
        threading.Thread(target=loop,name='draw-guess',daemon=True).start()
