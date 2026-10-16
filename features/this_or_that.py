"""Durable This or That matches: local visuals, 5 rounds, safe votes and recovery."""
import json,logging,random,threading,time
from contextlib import contextmanager
from telebot import types
from telebot.handler_backends import ContinueHandling
from database.db import get_db_connection
from core.customization import message_text,setting_value,group_scope
from core.sessions import start_session,end_session,can_start_session
from features.activity_spawn import ActivitySpawner
from games import this_or_that as game
from data.this_or_that import CAPACITY
LOG=logging.getLogger(__name__)
MESSAGES={
 'round':'⚖️ This or That — {round}/{rounds}\nဒီနှစ်ခုထဲက ပိုကြိုက်တာကို ရွေးပါ။\n\nA · {a}\n{av} မဲ · {ap}%\nB · {b}\n{bv} မဲ · {bp}%\n\nမဲတစ်ယောက်တစ်ကြိမ်။ {seconds} စက္ကန့်။',
 'results':'🏁 This or That ပြီးပြီ\n\n{results}\n\nပါဝင်သူ {count} ယောက်။ ပါဝင်ဆု +{reward} points။',
 'a':'🅰️ A ရွေးမယ်','b':'🅱️ B ရွေးမယ်','stop':'🛑 ရပ်မယ် (Admin)',
 'confirm':'ပွဲကိုဖျက်သိမ်းမလား? ဆုမပေးပါ။','yes':'ဖျက်သိမ်းမယ်','no':'ဆက်ဆော့မယ်',
 'cancelled':'This or That ပွဲကို ဖျက်သိမ်းလိုက်ပြီ။','expired':'ဒီ round ပြီးသွားပြီ။ လက်ရှိခလုတ်ကိုသုံးပါ။',
 'voted':'ဒီ round မှာ မဲပေးပြီးပြီ။','accepted':'မဲလက်ခံပြီးပြီ။','admin':'Group Admin သာ ရပ်နိုင်သည်။',
 'group':'Group ထဲမှာ /tot ပို့ပါ။','busy':'အခြားပွဲရှိနေသည်။ ပြီးမှ ပြန်စမ်းပါ။','error':'ခေတ္တမစနိုင်သေးပါ။ ခဏနေရင် ပြန်စမ်းပါ။',
 'missing':'ရပ်ရန်ပွဲမရှိပါ။','member':'Group အဖွဲ့ဝင်သာ မဲပေးနိုင်သည်။',
 'rules':'⚖️ /tot သို့မဟုတ် /thisorthat\nရွေးချယ်မှုမဲပေး ၅ round။ တစ် round လျှင် ၃၀ စက္ကန့် default။ မှန်/မှားမရှိပါ။ တစ်ယောက်တစ် round တစ်မဲ။ ပါဝင်သူကို ပွဲဆုံးလျှင် +3 points default။ Admin /totstop ဖြင့်ရပ်နိုင်သည်။\nစာကတ်နှင့် ရွေးချယ်ရန်ခလုတ်များဖြင့် ကစားသည်။ ပွဲအတွင်းမေးခွန်းမထပ်ပါ။'}
DEFAULTS=dict(game.DEFAULTS)
READY=False

def text(key,**fields):return message_text('msg.features.this_or_that.'+key,MESSAGES[key],fields)
def cfg(key,cid):return setting_value('cfg.features.this_or_that.'+key,DEFAULTS[key],cid)

@contextmanager
def locked(cid):
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(%s)',(cid,))
        cur.execute('SELECT state FROM this_that_games WHERE chat_id=%s FOR UPDATE',(cid,));row=cur.fetchone()
        yield cur,row[0] if row else None

def save(cur,s):
    cur.execute('INSERT INTO this_that_games(chat_id,state) VALUES(%s,%s::jsonb) ON CONFLICT(chat_id) DO UPDATE SET state=EXCLUDED.state',(s['chat_id'],json.dumps(s,ensure_ascii=False)))

def choose(cur,s):
    cur.execute('SELECT question_id FROM this_that_history WHERE chat_id=%s',(s['chat_id'],));used={r[0] for r in cur.fetchall()}
    available=[i for i in range(CAPACITY) if i not in used and i not in s['used']]
    if not available:
        cur.execute('DELETE FROM this_that_history WHERE chat_id=%s',(s['chat_id'],))
        available=[i for i in range(CAPACITY) if i not in s['used']]
    from data.this_or_that import PAIRS
    recent=set(s.get('recent_options',[]))
    fresh=[i for i in available if not recent.intersection(PAIRS[i])]
    index=random.choice(fresh or available)
    s['recent_options']=(s.get('recent_options',[])+list(PAIRS[index]))[-8:]
    styles=s.get('styles',[])
    s['style']=random.choice([i for i in range(4) if i not in styles[-2:]])
    s['styles']=(styles+[s['style']])[-2:]
    cur.execute('INSERT INTO this_that_history VALUES(%s,%s) ON CONFLICT DO NOTHING',(s['chat_id'],index))
    return index

def keyboard(s,confirm=False):
    k=types.InlineKeyboardMarkup();prefix=f"tot:{s['id']}:{s['round']}:"
    if confirm:k.row(types.InlineKeyboardButton(text('yes')[:55],callback_data=prefix+'yes'),types.InlineKeyboardButton(text('no')[:55],callback_data=prefix+'no'))
    else:
        k.row(types.InlineKeyboardButton(text('a')[:55],callback_data=prefix+'a'),types.InlineKeyboardButton(text('b')[:55],callback_data=prefix+'b'))
        k.row(types.InlineKeyboardButton(text('stop')[:55],callback_data=prefix+'stop'))
    return k

def body(s):
    a,b,ap,bp=game.counts(s)
    return text('round',round=s['round'],rounds=s['rules']['rounds'],a=s['question']['a']['label'],b=s['question']['b']['label'],av=a,bv=b,ap=ap,bp=bp,seconds=max(0,int(s['deadline']-time.time())))[:1000]

def delete(bot,cid,mid):
    if mid:
        try:bot.delete_message(cid,mid)
        except Exception:pass

def publish(bot,s):
    old=s.get('card');s['deadline']=time.time()+s['rules']['round_seconds']
    sent=bot.send_message(s['chat_id'],body(s),reply_markup=keyboard(s),parse_mode=None);photo=False
    s['card']=sent.message_id;s['photo']=photo;s['edited']=time.time();s['dirty']=False
    delete(bot,s['chat_id'],old)

def edit(bot,s,confirm=False):
    value=text('confirm') if confirm else body(s)
    try:
        if s['photo']:bot.edit_message_caption(value,s['chat_id'],s['card'],reply_markup=keyboard(s,confirm),parse_mode=None)
        else:bot.edit_message_text(value,s['chat_id'],s['card'],reply_markup=keyboard(s,confirm),parse_mode=None)
    except Exception as exc:
        if 'message is not modified' not in str(exc).lower():LOG.debug('This or That card edit unavailable')
    s['edited']=time.time();s['dirty']=False

def is_admin(bot,cid,uid):return bot.get_chat_member(cid,uid).status in ('creator','administrator')

def finish(bot,cur,s):
    awarded=[];points=s['rules']['participation_reward']
    for uid in s['participants']:
        cur.execute('INSERT INTO this_that_rewards VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING user_id',(s['id'],int(uid)))
        if not cur.fetchone():continue
        cur.execute('INSERT INTO player_stats(chat_id,user_id,points,games,wins,losses,draws) VALUES(%s,%s,%s,0,0,0,0) ON CONFLICT(chat_id,user_id) DO UPDATE SET points=GREATEST(0,player_stats.points+EXCLUDED.points)',(s['chat_id'],int(uid),points))
        cur.execute('INSERT INTO reward_transactions(chat_id,user_id,points,reason) VALUES(%s,%s,%s,%s)',(s['chat_id'],int(uid),points,'this_or_that_participation:'+s['id']))
        awarded.append((int(uid),points))
    rows=['%s. A %s — %s မဲ | B %s — %s မဲ'%(r['round'],r['a'],r['av'],r['b'],r['bv']) for r in s['results']]
    sent=bot.send_message(s['chat_id'],text('results',results='\n'.join(rows),count=len(s['participants']),reward=points)[:3900],parse_mode=None)
    delete(bot,s['chat_id'],s['card']);s['card']=sent.message_id
    end_session(s['chat_id'],'this_or_that');return awarded

def start(bot,cid,uid):
    if not READY:return False
    from features.owner_operations import feature_allowed
    if not feature_allowed('game:this_or_that',cid) or not setting_value('enabled.features.this_or_that.command',True,cid):return False
    ok,_=start_session(cid,'this_or_that')
    if not ok:return False
    try:
        with group_scope(cid),locked(cid) as (cur,current):
            if current and current['phase']=='playing':return False
            s=game.new(cid,uid,{k:cfg(k,cid) for k in game.DEFAULTS})
            if current:
                s['recent_options']=current.get('recent_options',[])
                s['styles']=current.get('styles',[])
            game.open_round(s,choose(cur,s),time.time());publish(bot,s);save(cur,s)
        return True
    except Exception:
        end_session(cid,'this_or_that');LOG.exception('This or That start failed');return False

def tick(bot,cid):
    awarded=[]
    with group_scope(cid),locked(cid) as (cur,s):
        if not s or s['phase']!='playing':return
        if time.time()>=s['deadline']:
            game.close_round(s)
            if s['phase']=='finished':awarded=finish(bot,cur,s)
            else:game.open_round(s,choose(cur,s),time.time());publish(bot,s)
            save(cur,s)
        elif s['dirty'] and time.time()-s['edited']>=2:edit(bot,s);save(cur,s)
    if awarded:
        from features.draw_guess import refresh_points
        refresh_points(cid)

def register(bot):
    global READY
    try:
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS this_that_games(chat_id BIGINT PRIMARY KEY,state JSONB NOT NULL)')
            cur.execute('CREATE TABLE IF NOT EXISTS this_that_history(chat_id BIGINT NOT NULL,question_id INTEGER NOT NULL,PRIMARY KEY(chat_id,question_id))')
            cur.execute('CREATE TABLE IF NOT EXISTS this_that_rewards(game_id TEXT NOT NULL,user_id BIGINT NOT NULL,PRIMARY KEY(game_id,user_id))')
            cur.execute("SELECT chat_id FROM this_that_games WHERE state->>'phase'='playing'")
            for row in cur.fetchall():start_session(row[0],'this_or_that',recover=True)
        READY=True
    except Exception:LOG.warning('This or That database unavailable')
    spawner=ActivitySpawner(lambda cid:start(bot,cid,0),threshold=(55,90),chance=.35,quiet=(900,1800),can_spawn=lambda cid:can_start_session(cid,'this_or_that')[0],config_key='tot_auto')

    @bot.message_handler(commands=['tot','thisorthat'])
    def command(m):
        if m.chat.type not in ('group','supergroup'):bot.reply_to(m,text('group'));return
        if not start(bot,m.chat.id,m.from_user.id):bot.reply_to(m,text('busy') if READY else text('error'))
        else:spawner.note_spawn(m.chat.id)

    @bot.message_handler(commands=['totrules'])
    def rules(m):bot.send_message(m.chat.id,text('rules'),parse_mode=None)

    @bot.message_handler(commands=['totstop'])
    def stop(m):
        if m.chat.type not in ('group','supergroup'):bot.reply_to(m,text('group'));return
        try:
            if not is_admin(bot,m.chat.id,m.from_user.id):bot.reply_to(m,text('admin'));return
            with locked(m.chat.id) as (cur,s):
                if not s or s['phase']!='playing':bot.reply_to(m,text('missing'));return
                edit(bot,s,True);save(cur,s)
        except Exception:bot.reply_to(m,text('error'))

    @bot.callback_query_handler(func=lambda c:bool(c.data and c.data.startswith('tot:')))
    def vote(c):
        answer='accepted'
        try:
            if not c.message or c.message.chat.type not in ('group','supergroup'):raise ValueError('expired')
            _,gid,rnd,side=c.data.split(':');cid=c.message.chat.id;uid=c.from_user.id
            if c.from_user.is_bot:raise ValueError('member')
            member=bot.get_chat_member(cid,uid)
            if member.status in ('left','kicked') or member.status=='restricted' and not getattr(member,'is_member',False):raise ValueError('member')
            with group_scope(cid),locked(cid) as (cur,s):
                if not s or s['id']!=gid or s['round']!=int(rnd) or s['phase']!='playing' or s['card']!=c.message.message_id or time.time()>=s['deadline']:raise ValueError('expired')
                if side in ('stop','yes','no'):
                    if member.status not in ('creator','administrator'):raise ValueError('admin')
                    if side=='yes':
                        game.cancel(s);delete(bot,cid,s['card']);end_session(cid,'this_or_that')
                        notice=bot.send_message(cid,text('cancelled'),parse_mode=None)
                        timer=threading.Timer(10,delete,args=(bot,cid,notice.message_id));timer.daemon=True;timer.start()
                    else:edit(bot,s,side=='stop')
                else:game.vote(s,gid,int(rnd),uid,side,time.time())
                save(cur,s)
        except ValueError as exc:answer=str(exc) if str(exc) in MESSAGES else 'expired'
        except Exception:answer='error';LOG.exception('This or That callback failed')
        finally:
            try:bot.answer_callback_query(c.id,text(answer))
            except Exception:pass

    @bot.message_handler(func=lambda m:True,content_types=['text'])
    def activity(m):
        if READY and m.chat.type in ('group','supergroup') and m.from_user and not m.from_user.is_bot and m.text and not m.text.lstrip().startswith('/'):
            try:spawner.record(m.chat.id,m.from_user.id)
            except Exception:LOG.warning('This or That auto spawn unavailable')
        return ContinueHandling()

    if READY:
        def loop():
            while True:
                try:
                    with get_db_connection() as con,con.cursor() as cur:
                        cur.execute("SELECT chat_id FROM this_that_games WHERE state->>'phase'='playing'");chats=[r[0] for r in cur.fetchall()]
                    for cid in chats:
                        try:tick(bot,cid)
                        except Exception:LOG.exception('This or That tick failed')
                except Exception:LOG.warning('This or That recovery unavailable')
                time.sleep(2)
        threading.Thread(target=loop,name='this-or-that',daemon=True).start()
