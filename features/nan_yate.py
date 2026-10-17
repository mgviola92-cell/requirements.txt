"""Telegram Nan Yate adapter: transactional state, durable outbox, restart recovery."""
import html
import json
import logging
import random
import threading
import time
import uuid
from contextlib import contextmanager

from telebot import types
from telebot.handler_backends import ContinueHandling
from database.db import get_db_connection
from core.customization import message_text,setting_value,group_scope
from core.sessions import start_session,end_session
from games import nan_yate as game

WAKE=threading.Event()
LOG=logging.getLogger(__name__)
MESSAGES={
 'title':'🏯 နန်းရိပ် — လုပ်ကြံမှုနှင့် သက်သေ',
 'lobby':'လူစုနေပြီ။ ပါဝင်ရန် Private Chat ကိုဖွင့်ပြီး အတည်ပြုပါ။\nလူဦးရေ {count}/{maximum} · အနည်းဆုံး {minimum}\nအချိန်ကျန် {seconds} စက္ကန့်',
 'phase':'ရက် {day} · {phase}\nအသက်ရှင် {count} ယောက် · အချိန်ကျန် {seconds} စက္ကန့်\nဒီညဖြစ်ရပ် — {event}',
 'night':'🌙 ညဉ့်နက်ပြီ။ နန်းတံခါးများ ပိတ်လိုက်သည်။',
 'day':'☀️ မနက်လင်းပြီ။ သက်သေများဖော်၍ ဆွေးနွေးကြပါ။',
 'vote':'⚖️ ထုတ်ပယ်မဲပေးချိန်။ မဲအရေအတွက်ကို ပြီးမှပြမည်။',
 'runoff':'⚖️ မဲတူနေသည်။ သတ်မှတ်ထားသူများကို ထပ်မဲပေးပါ။',
 'open':'🔐 ကိုယ့်ဂိမ်းခန်းဖွင့်မယ်','confirm_join':'➕ ပါဝင်မှုအတည်ပြုမယ်','withdraw':'လူစုစာရင်းမှ ထွက်မယ်',
 'start':'▶️ လူပြည့်လျှင် စမယ် (Admin)','stop':'🛑 ရပ်မယ် (Admin)',
 'confirm_stop':'⚠️ ပွဲဖျက်သိမ်းမယ်။ Reward မရပါ။','yes_stop':'ပွဲဖျက်သိမ်းရန် အတည်ပြု',
 'back':'← ပြန်သွားမယ်','next':'နောက် →','previous':'← ရှေ့',
 'select_location':'🗺️ သက်သေရှာမယ့်နေရာ','ability':'✨ Role အစွမ်းသုံးမယ်',
 'skip_action':'⏭️ ညလုပ်ဆောင်ချက် Skip','attack':'🗡️ အဖွဲ့တိုက်ခိုက်ပစ်မှတ်',
 'skip_vote':'⏭️ မထုတ်ပယ်ဘူး','vote_button':'⚖️ မဲပေးမယ်',
 'public':'📜 အများသိသက်သေစာရင်း','publish':'📜 သက်သေဖော်မယ်','quest':'🧩 လျှို့ဝှက်မစ်ရှင်','shop':'🛍️ ပစ္စည်းဝယ်မယ်',
 'seal':'တံဆိပ်စစ်စာ · {cost} coin','armor':'ချပ်ဝတ် · {cost} coin (တစ်ပွဲတစ်ကြိမ်)',
 'ghost':'👻 ဝိညာဉ်သက်သေရှာမယ်','escape':'💎 ရတနာနဲ့ထွက်ခွာမယ်',
 'traitor':'🔀 လျှို့ဝှက်ဘက်ပြောင်းကမ်းလှမ်းချက်','accept':'လက်ခံမယ်','decline':'ငြင်းမယ်',
 'panel':'မျက်နှာဖုံး {number} · {role}\nဘက် — {side}\n{description}\nအစွမ်းအသုံးကျန် — {uses}\nပွဲအတွင်း coin — {coins}\n{selection}',
 'objective':'လျှို့ဝှက်ပစ်မှတ် — မျက်နှာဖုံး {number}',
 'selection':'လက်ရှိရွေးထားမှု — {selection}',
 'allies':'လုပ်ကြံအဖွဲ့ — {names}\n/nychat စာသား ဖြင့် အဖွဲ့ထံပြောနိုင်သည်။',
 'quest_question':'မစ်ရှင် — {a} + {b} = ?\nမှန်လျှင် ပွဲအတွင်း coin {coins}။ တစ်ညတစ်ကြိမ်။',
 'shop_help':'ပွဲအတွင်း coin သာသုံးသည်။ တစ်နေ့ပစ္စည်းတစ်ခုသာဝယ်နိုင်သည်။\nတံဆိပ်စစ်စာသည် နောက်ဆုံးရသက်သေ အတု/အစစ်ကိုပြသည်။\nချပ်ဝတ်သည် ညတိုက်ခိုက်မှုတစ်ကြိမ်ကာသည်၊ အဆိပ်မကာပါ။',
 'traitor_help':'ဒုတိယညသာ။ လက်ခံလျှင် လုပ်ကြံဘက်သို့ အပြီးပြောင်းမည်။\nအဖွဲ့ဝင်စာရင်းကို ညကုန်မှရမည်။ Coin လောင်းကြေးမရှိပါ။',
 'death':'🕯️ မျက်နှာဖုံး {number} — {name} သည် {cause} ကြောင့် ပွဲမှထွက်ခဲ့သည်။ ဘက် — {side}',
 'evidence':'📜 သက်သေ #{eid} · ရက် {day}\n{location} တွင် မျက်နှာဖုံး {number} သွားလာခဲ့သည့် ခြေရာရှိသည်။\nဒါသည် Role အတည်ပြုချက်မဟုတ်ပါ။ အတုလည်းဖြစ်နိုင်သည်။',
 'result':'🏁 နန်းရိပ်ပွဲပြီးပြီ။\nပင်မရလဒ် — {winner}\nတစ်ဦးချင်းအနိုင် — {individual}\nRole စာရင်းကို အောက်တွင်ပြထားသည်။',
 'cancelled':'🏯 နန်းရိပ်ပွဲကို ဖျက်သိမ်းလိုက်သည်။ လူမပြည့်ခြင်း သို့မဟုတ် Admin ရပ်ခြင်းဖြစ်သည်။ Reward မပေးပါ။',
 'no_execution':'⚖️ ဒီနေ့ ဘယ်သူမှ မထုတ်ပယ်ပါ။',
 'votes':'မဲရလဒ်\n{votes}','escaped':'💎 မျက်နှာဖုံး {number} သည် ရတနာမစ်ရှင်အောင်မြင်ပြီး ထွက်ခွာသွားသည်။',
 'pardon':'📯 မျက်နှာဖုံး {number} သည် အမိန့်ပြန်အမတ်ဖြစ်သည်။ မျက်နှာဖုံး {target} ၏ ထုတ်ပယ်မှုကို တားလိုက်သည်။',
 'judge':'⚖️ မျက်နှာဖုံး {number} သည် တော်ဝင်တရားသူကြီး၏ ဆုံးဖြတ်ခွင့်ကို သုံးလိုက်သည်။',
 'blocked':'🚪 ဒီည Role အစွမ်း ပိတ်ခံရသည်။','poisoned':'☠️ အဆိပ်မိနေသည်။ နောက်ညကုန်မတိုင်မီ ဆေးမြစ်ဆရာက ကုမှလွတ်မည်။',
 'protected':'🛡️ တိုက်ခိုက်မှုမှ လွတ်မြောက်ခဲ့သည်။ ကာကွယ်သူကို မဖော်ပါ။',
 'verified':'သက်သေ #{eid} — {verdict}','side':'မျက်နှာဖုံး {number} ၏ စစ်တွေ့ဘက် — {side}။ မျက်နှာဖုံးအစွမ်းက လှည့်စားနိုင်သည်။',
 'location':'မျက်နှာဖုံး {number} ၏ ခြေရာ — {location}',
 'visitors':'{location} သို့ လာခဲ့သူ — {names}။ အများဆုံးသုံးဦးသာပြသည်။',
 'used':'မျက်နှာဖုံး {number} ၏ အစွမ်းသုံးခြင်း — {verdict}',
 'role_group':'မျက်နှာဖုံး {number} ၏ အစွမ်းအုပ်စု — {action}',
 'found':'📜 သက်သေ #{eid} ရခဲ့သည်။ ကိုယ့်ဂိမ်းခန်းတွင် ကြည့်နိုင်သည်။',
 'empty':'ဒီနေရာမှ သက်သေအသစ် မရခဲ့ပါ။ ဒါက တခြားသူအပြစ်ကင်းကြောင်း မဆိုလိုပါ။',
 'gift':'🎁 ပစ္စည်းစစ်ဖို့ coin ၂ ရခဲ့သည်။','copied':'အစွမ်းကူးရပြီ — {action}။ နောက်ညတစ်ကြိမ်သုံးနိုင်သည်။',
 'turned':'လုပ်ကြံဘက်သို့ ပြောင်းပြီးပြီ။ မိမိအနိုင်ရည်မှန်းချက်လည်း ပြောင်းသွားပြီ။',
 'afk':'⚠️ တစ်ရက်စက်ဝန်းတွင် မပါဝင်ခဲ့ပါ။ နောက်တစ်ရက်လည်း မပါဝင်လျှင် ပွဲမှဖယ်မည်။',
 'dead_panel':'👻 သင်သေဆုံးပြီးဖြစ်သည်။ Role သတင်းကို Group တွင် မဖော်ပါနှင့်။ ညဘက်ဝိညာဉ်မဲပေးနိုင်သည်။',
 'inactive_panel':'ဒီပွဲတွင် သင်မပါဝင်ပါ။','saved':'✅ ရွေးထားမှုကို သိမ်းပြီးပြီ။ အချိန်မကုန်မီ ပြောင်းနိုင်သည်။',
 'closed':'အဲ့ဒီရွေးချယ်မှုက ပိတ်သွားပြီ။ နောက်ဆုံးဂိမ်းခန်းကို ပြန်ဖွင့်ပါ။',
 'full':'လူပြည့်သွားပြီ။','not_enough':'အနည်းဆုံးလူဦးရေ မပြည့်သေးပါ။',
 'not_player':'ဒီပွဲမှာ သင်မပါဝင်ပါ။','unavailable':'အခုအချိန်မှာ ဒီလုပ်ဆောင်ချက် မရပါ။',
 'dead':'အသက်ရှင်သူသာ လုပ်နိုင်သည်။','target':'ဒီပစ်မှတ်ကို ရွေးမရပါ။',
 'publish_limit':'ဒီနေ့သက်သေဖော်ပြခွင့် ပြည့်သွားပြီ။','wrong':'အဖြေမမှန်သေးပါ။','coins':'ပွဲအတွင်း coin မလုံလောက်ပါ။',
 'admin':'Group Admin သို့မဟုတ် Owner သာ လုပ်နိုင်သည်။','busy':'တခြားဂိမ်းတစ်ပွဲ ရှိနေသည်။ ပြီးမှစပါ။',
 'private_required':'ဒီ command ကို Group ထဲမှာ သုံးပါ။','error':'ခေတ္တ မသိမ်းနိုင်ပါ။ ရွေးထားမှုကို အတည်မပြုရသေးပါ။ ပြန်စမ်းပါ။',
 'chat_help':'/nychat <ပွဲ ID> <စာသား> — လုပ်ကြံအဖွဲ့/Anonymous ဆွေးနွေးရန်\n/nywhisper <ပွဲ ID> <မျက်နှာဖုံးနံပါတ်> <စာသား> — သံတမန်ခွင့်ရသူနှင့်ပြောရန်',
 'chat_sent':'✅ စာပို့ရန် သိမ်းပြီးပြီ။','anonymous_limit':'ဒီနေ့နာမည်ဝှက်စာ ၂ စောင် ပြည့်သွားပြီ။ တစ်စောင်ကို စာတိုအများကြီးအစား စုရေးပါ။','chat_relay':'မျက်နှာဖုံး {number} — {text}',
 'rules':'🏯 နန်းရိပ် စည်းမျဉ်း\n\nလူ ၈–၄၀။ Private chat မှ Join အတည်ပြုရသည်။\nညတွင် သက်သေရှာမည့်နေရာ သို့မဟုတ် Role အစွမ်းရွေးပါ။ Role အစွမ်းက သွားရမည့်နေရာကို သတ်မှတ်ပေးသည်။ လုပ်ကြံဘက်က အဖွဲ့တိုက်ခိုက်မဲ ထပ်ပေးနိုင်သည်။\nနေ့တွင် ဆွေးနွေး၊ သက်သေဖော်၊ ပစ္စည်းဝယ်နိုင်သည်။ မဲချိန်တွင် တစ်ဦးတစ်မဲ၊ ကိုယ့်ကိုမဲပေးမရ။ မဲပြောင်းနိုင်သည်။\nSkip နှင့် မဲတူလျှင် မထုတ်ပယ်။ လူချင်းမဲတူလျှင် တစ်ကြိမ်ထပ်မဲပေးသည်။\nသေသူ၏ဘက်သာ ချက်ချင်းပေါ်၊ Role အပြည့်အစုံကို ပွဲဆုံးမှပြသည်။ သေသူက Role သတင်းမဖော်ရ။\nလုပ်ကြံသူမရှိတော့လျှင် နန်းတော်နိုင်။ လုပ်ကြံသူက ကျန်သူအားလုံးနှင့်အရေအတွက်တူ/ပိုလျှင် လုပ်ကြံဘက်နိုင်။ အများဆုံးရက်ပြည့်လျှင် Draw။\nတစ်ရက်စက်ဝန်း နှစ်ခါဆက်မပါဝင်လျှင် ပွဲမှဖယ်သည်။ Rank Points ဖြင့်ပစ္စည်းမဝယ်ရ။\nRole screenshot မဖော်ရ။ Private game ခလုတ်များသာ အစွမ်းအတည်ယူသည်။',
 'mode_help':'Mode ကို lobby မဖွင့်မီ command တွင်ရွေးပါ။\n/nanyate — ပုံမှန်\n/nanyate anonymous — နာမည်ဝှက်ဆွေးနွေး\n/nanyate advanced — သစ္စာဖောက်ခွင့်ပါ\n/nanyate anonymous advanced — နှစ်မျိုးလုံး\n/nanyaterules — စည်းမျဉ်း\n/nanyatestop — Admin ရပ်ရန်',
 'rain':'🌧️ မိုးသည်းည — နေရာသက်သေရနိုင်ခြေ လျော့သည်။',
 'festival':'🏮 နန်းတွင်းပွဲတော် — မနက်တွင် ပါဝင်သူတိုင်း coin ၁ ရသည်။',
 'lantern':'🪔 မီးအိမ်ထွန်းည — နေရာတွင်သက်သေရှိလျှင် ရမည်။',
 'normal':'🌙 သာမန်ည — အထူးစည်းမျဉ်းမရှိ။',
}
PHASES={'night':'ညလုပ်ဆောင်ချက်','day':'နေ့ဆွေးနွေး','vote':'မဲပေး','runoff':'ထပ်မဲပေး'}
ACTION_NAMES={'search':'သက်သေရှာ','seer':'ဘက်စစ်','verify':'သက်သေစစ်','track':'ခြေရာခံ','watch':'နေရာစောင့်',
 'listen':'အစွမ်းသုံးမှုစစ်','protect':'ကာကွယ်','guard':'ကိုယ်စားခံ','heal':'အဆိပ်ကု','cleanse':'ကျိန်စာဖြေ',
 'block':'အစွမ်းပိတ်','armor':'ချပ်ဝတ်ပေး','recover':'သေသူသက်သေရယူ','link':'လျှို့ဝှက်ဆွေးနွေးခွင့်',
 'pardon':'ထုတ်ပယ်မှုတား','illuminate':'သက်သေဖော်','judge':'မဲတူဆုံးဖြတ်','poison':'အဆိပ်ခတ်',
 'hide':'ခြေရာဖျောက်','forge':'သက်သေအတု','mask':'ဘက်ဖုံး','spy':'အစွမ်းအုပ်စုစစ်','curse':'ကျိန်စာ',
 'copy':'အစွမ်းကူး','gift':'ပစ္စည်းစစ် coin ပေး'}
BOOT_LOCK=threading.Lock()
WORKER_STARTED=False
BOT_NAME=None


def text(key,**fields):
    return message_text('msg.features.nan_yate.'+key,MESSAGES.get(key,key),fields)

def role_name(role):return message_text('msg.features.nan_yate.role.'+role,game.ROLES[role]['name'])
def action_name(action):return message_text('msg.features.nan_yate.action.'+action,ACTION_NAMES.get(action,action))
def phase_name(phase):return message_text('msg.features.nan_yate.phase.'+phase,PHASES.get(phase,phase))
def description(role):return message_text('msg.features.nan_yate.role_description.'+role,game.ROLES[role]['description'])
def location(i):return message_text('msg.features.nan_yate.location.'+str(i),game.LOCATIONS[i]) if i is not None else 'ခြေရာမတွေ့'
def label(p):return 'မျက်နှာဖုံး '+str(p['number'])
def safe(value):return html.escape(str(value))


def init_db():
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('CREATE TABLE IF NOT EXISTS nan_yate_games (chat_id BIGINT PRIMARY KEY,game_id TEXT UNIQUE NOT NULL,state JSONB NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())')
        cur.execute('CREATE TABLE IF NOT EXISTS nan_yate_outbox (id BIGSERIAL PRIMARY KEY,game_id TEXT NOT NULL,destination BIGINT NOT NULL,event JSONB NOT NULL,done BOOLEAN NOT NULL DEFAULT FALSE,attempts INTEGER NOT NULL DEFAULT 0,next_try TIMESTAMPTZ NOT NULL DEFAULT NOW())')
        cur.execute('CREATE INDEX IF NOT EXISTS nan_yate_outbox_pending ON nan_yate_outbox(next_try) WHERE NOT done')
        cur.execute("DELETE FROM nan_yate_outbox WHERE done AND id < COALESCE((SELECT MAX(id) FROM nan_yate_outbox),0)-10000")
        cur.execute('CREATE TABLE IF NOT EXISTS nan_yate_rewards (game_id TEXT NOT NULL,user_id BIGINT NOT NULL,points INTEGER NOT NULL,PRIMARY KEY(game_id,user_id))')


@contextmanager
def transaction(cid=None,gid=None):
    with get_db_connection() as con,con.cursor() as cur:
        if gid:
            cur.execute('SELECT chat_id FROM nan_yate_games WHERE game_id=%s',(gid,));row=cur.fetchone()
            if not row:raise ValueError('closed')
            cid=row[0]
        cur.execute('SELECT pg_advisory_xact_lock(%s)',(cid,))
        cur.execute('SELECT state FROM nan_yate_games WHERE chat_id=%s FOR UPDATE',(cid,));row=cur.fetchone()
        s=row[0] if row else None
        if s is not None and gid and s['id']!=gid:raise ValueError('closed')
        yield cur,s,cid


def persist(cur,s,now):
    WAKE.set()
    s['updated']=now
    for e in s['events']:
        # Delivery has the immutable event + version. Stale phase panels are skipped.
        e['epoch']=s['epoch']
        cur.execute('INSERT INTO nan_yate_outbox(game_id,destination,event) VALUES(%s,%s,%s::jsonb)',
                    (s['id'],int(e['dest']),json.dumps(e,ensure_ascii=False)))
    s['events']=[]
    cur.execute('INSERT INTO nan_yate_games(chat_id,game_id,state) VALUES(%s,%s,%s::jsonb) ON CONFLICT(chat_id) DO UPDATE SET game_id=EXCLUDED.game_id,state=EXCLUDED.state,updated_at=NOW()',
                (s['chat_id'],s['id'],json.dumps(s,ensure_ascii=False)))
    # The reward marker and actual points are committed in the same transaction.
    for a in s['awardees']:
        cur.execute('INSERT INTO nan_yate_rewards VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING user_id',(s['id'],int(a['uid']),a['points']))
        if cur.fetchone():
            cur.execute('INSERT INTO player_stats(chat_id,user_id,points,games,wins,losses,draws) VALUES(%s,%s,%s,0,0,0,0) ON CONFLICT(chat_id,user_id) DO UPDATE SET points=GREATEST(0,player_stats.points+EXCLUDED.points)',(s['chat_id'],int(a['uid']),a['points']))
            cur.execute('INSERT INTO reward_transactions(chat_id,user_id,points,reason) VALUES(%s,%s,%s,%s)',(s['chat_id'],int(a['uid']),a['points'],'nan_yate:'+s['id']))


def invalidate_rewards(s):
    if s['awardees']:
        from database.players import player_stats,player_stats_lock
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute('SELECT user_id,points,games,wins,losses,draws FROM player_stats WHERE chat_id=%s AND user_id=ANY(%s)',(s['chat_id'],[int(a['uid']) for a in s['awardees']]))
            rows=cur.fetchall()
        with player_stats_lock:
            for row in rows:player_stats[(s['chat_id'],row[0])]=dict(zip(('points','games','wins','losses','draws'),row[1:]))


def snapshot(cid):
    return {k:setting_value('cfg.features.nan_yate.'+k,v,cid) for k,v in game.DEFAULTS.items()}


def callback(s,kind,value='0'):return f"ny:{s['id']}:{s['epoch']}:{kind}:{value}"
def button(s,key,kind,value='0',**fields):return types.InlineKeyboardButton(text(key,**fields),callback_data=callback(s,kind,value))
def keyboard():return types.InlineKeyboardMarkup(row_width=2)
def url_button(bot,s):
    global BOT_NAME
    if BOT_NAME is None:BOT_NAME=bot.get_me().username
    return types.InlineKeyboardButton(text('open'),url=f"https://t.me/{BOT_NAME}?start=ny_{s['id']}")


def private_panel(s,uid):
    p=game.player(s,uid);k=keyboard()
    if s['phase']=='lobby':
        k.add(button(s,'confirm_join','join'))
        if p:k.add(button(s,'withdraw','withdraw'))
        return text('title')+'\n'+text('lobby',count=len(s['players']),maximum=s['rules']['max_players'],minimum=s['rules']['min_players'],seconds=max(0,int(s['deadline']-time.time()))),k
    if not p:return text('inactive_panel'),None
    if s['phase']=='cancelled':return text('cancelled'),None
    if s['phase']=='finished':return result(s),None
    a=s['actions'].get(p['id'],{})
    selected=action_name(a['action']) if a.get('action') else 'မရွေးရသေး'
    if a.get('target'):
        q=game.player(s,a['target']);selected+=' → '+(label(q) if q else a['target'])
    elif a.get('loc') is not None:selected+=' → '+location(a['loc'])
    body=text('panel',number=p['number'],role=role_name(p['role']),side=game.SIDES[p['side']],
              description=description(p['role']),uses='အကန့်အသတ်မရှိ' if p['uses']<0 else p['uses'],coins=p['coins'],selection=text('selection',selection=selected))
    body+='\n'+text('phase',day=s['day'],phase=phase_name(s['phase']),count=len(game.alive(s)),seconds=max(0,int(s['deadline']-time.time())),event=text(s['event']))
    if p.get('objective'):body+='\n'+text('objective',number=game.player(s,p['objective'])['number'])
    if p['side']=='plot' and s['phase']=='night':
        target=game.player(s,s['attack'].get(p['id']))
        body+='\nအဖွဲ့ပစ်မှတ် — '+(label(target) if target else 'Skip / မရွေးရသေး')
    body+='\nပွဲ ID: '+s['id']+'\n'+text('chat_help')
    if p['side']=='plot' and not p.get('turned'):
        body+='\n'+text('allies',names=', '.join(label(q) for q in s['players'] if q['side']=='plot' and not q.get('turned')))
    if not p['alive']:
        body+='\n'+text('dead_panel')
        if s['phase']=='night' and s['rules']['ghosts'] and not p['departed']:k.add(button(s,'ghost','menu','ghost.0'))
    elif s['phase']=='night':
        k.add(button(s,'select_location','menu','loc.0'),button(s,'skip_action','skip'))
        if game.role_action(p) not in game.DAY_ACTIONS and game.role_action(p)!='search' and p['uses']!=0:
            k.add(button(s,'ability','menu','ability.0'))
        if p['side']=='plot':k.add(button(s,'attack','menu','attack.0'))
        if s['rules']['quests'] and not p['quest_done']:k.add(button(s,'quest','questmenu'))
        if s['traitor_offer']==p['id']:k.add(button(s,'traitor','traitormenu'))
    elif s['phase']=='day':
        if p['bag']:k.add(button(s,'publish','menu','publish.0'))
        if s['rules']['shop']:k.add(button(s,'shop','shopmenu'))
        if game.role_action(p) in game.DAY_ACTIONS and p['uses']:k.add(button(s,'ability','menu',game.role_action(p)+'.0'))
        if p['role']=='treasure' and len(p['relics'])>=3:k.add(button(s,'escape','escape'))
    elif s['phase'] in ('vote','runoff'):k.add(button(s,'vote_button','menu','vote.0'))
    if s.get('public_evidence'):k.add(button(s,'public','publicmenu','0'))
    if p['bag']:
        es=[e for e in s['evidence'] if e['id'] in p['bag'][-5:]]
        body+='\n\n'+'\n'.join(evidence_text(s,e) for e in es)
    return body[:3800],k


def evidence_text(s,e):
    p=game.player(s,e['subject'])
    return text('evidence',eid=e['id'],day=e['day'],location=location(e['loc']),number=p['number'])


def result(s):
    individual=', '.join(label(p) for p in s['players'] if p['side']=='neutral' and p['wins']) or 'မရှိ'
    return text('result',winner=game.SIDES.get(s['winner'],'သရေ'),individual=individual)


def render_event(bot,s,e):
    kind=e['kind'];k=None
    if kind=='phase':
        k=keyboard();k.add(url_button(bot,s))
        if s['phase']=='lobby':
            body=text('title')+'\n'+text('lobby',count=len(s['players']),maximum=s['rules']['max_players'],minimum=s['rules']['min_players'],seconds=max(0,int(s['deadline']-time.time())))
            k.add(button(s,'start','begin'),button(s,'stop','stop'))
        else:
            body=text('title')+'\n'+text(s['phase'])+'\n'+text('phase',day=s['day'],phase=phase_name(s['phase']),count=len(game.alive(s)),seconds=max(0,int(s['deadline']-time.time())),event=text(s['event']))
            if s['rules']['anonymous']:body+='\nAnonymous mode: /nychat '+s['id']+' စာသား ကို Private တွင်သုံးပါ။'
            body+='\n\n'+'\n'.join(label(p)+' — '+('ဖုံးကွယ်ထားသည်' if s['rules']['anonymous'] else p['name']) for p in game.alive(s))
    elif kind=='panel':return private_panel(s,int(e['dest']))
    elif kind=='evidence':
        public=s.get('public_evidence',[e['eid']])
        body=text('public')+' · '+str(len(public))+' ခု\n'+ '\n\n'.join(evidence_text(s,v) for v in s['evidence'] if v['id'] in public[-6:])
        k=keyboard();k.add(url_button(bot,s))
    elif kind=='death':
        p=game.player(s,e['uid']);cause={'vote':'မဲဖြင့်ထုတ်ပယ်မှု','attack':'လုပ်ကြံမှု','guard':'ကိုယ်စားခံမှု','poison':'အဆိပ်','afk':'မပါဝင်မှု','leave':'Group ထွက်ခြင်း'}.get(e['cause'],e['cause'])
        body=text('death',number=p['number'],name='ဖုံးကွယ်ထားသည်' if s['rules']['anonymous'] else p['name'],cause=cause,side=game.SIDES[e['side']])
    elif kind=='result':
        body=result(s)+'\n\n'+'\n'.join(label(p)+' — '+p['name']+' — '+role_name(p['role'])+' ('+game.SIDES[p['side']]+')'+(' ✅' if p['wins'] else '') for p in s['players'])
    elif kind=='votes':
        body=text('votes',votes='\n'.join(label(game.player(s,u))+' → '+(label(game.player(s,t)) if t!='skip' else 'Skip') for u,t in e['votes'].items()) or 'မဲမရှိ')
    elif kind=='notice':
        code=e['code'];f={k:v for k,v in e.items() if k not in ('dest','kind','code','epoch')}
        if 'uid' in f:f['number']=game.player(s,f.pop('uid'))['number']
        if 'side' in f:f['side']=game.SIDES[f['side']]
        if 'fake' in f:f['verdict']='အတု' if f.pop('fake') else 'အစစ်'
        if 'used' in f:f['verdict']='သုံးခဲ့သည်' if f.pop('used') else 'မတွေ့ရ'
        if 'loc' in f:f['location']=location(f.pop('loc'))
        if 'uids' in f:f['names']=', '.join(label(game.player(s,u)) for u in f.pop('uids')) or 'မတွေ့ရ'
        if 'action' in f:f['action']=action_name(f['action'])
        if code=='allies':f['names']=', '.join(label(p) for p in s['players'] if p['side']=='plot')
        body=text(code,**f)
    elif kind in ('pardon','judge','escaped'):
        f={'number':game.player(s,e['uid'])['number']}
        if 'target' in e:f['target']=game.player(s,e['target'])['number']
        body=text(kind,**f)
    elif kind=='relay':body=text('chat_relay',number=e['number'],text=e['text'])
    else:body=text(kind)
    return body,k


def menu(s,uid,kind,page):
    p=game.player(s,uid)
    if not p:raise ValueError('not_player')
    if kind in ('loc','ghost'):values=[str(i) for i in range(len(game.LOCATIONS))]
    elif kind=='publish':values=p['bag']
    elif kind=='vote':values=[q['id'] for q in game.alive(s) if q is not p and (s['phase']!='runoff' or q['id'] in s['runoff'])]
    elif kind=='attack':values=[q['id'] for q in game.alive(s) if q['side']!='plot']
    else:values=game.available_targets(s,p,game.role_action(p) if kind=='ability' else kind)
    page=max(0,min(page,max(0,(len(values)-1)//8)));k=keyboard()
    for v in values[page*8:page*8+8]:
        action=game.role_action(p) if kind=='ability' else kind
        if kind in ('loc','ghost') or action in ('watch','illuminate'):name=location(int(v))
        elif kind=='publish' or action=='verify':name='📜 #'+v
        else:name=label(game.player(s,v))
        k.add(types.InlineKeyboardButton(name,callback_data=callback(s,kind,v)))
    if page:k.add(button(s,'previous','menu',kind+'.'+str(page-1)))
    if (page+1)*8<len(values):k.add(button(s,'next','menu',kind+'.'+str(page+1)))
    if kind in ('vote','attack'):k.add(button(s,'skip_vote',kind,'skip'))
    k.add(button(s,'back','panel'))
    return text('title')+'\n'+action_name(game.role_action(p))+'\n'+text('selection',selection='ပစ်မှတ်ရွေးပါ'),k


def send_plain(bot,cid,body,k=None):
    # Plain text avoids untrusted names/relays becoming Telegram HTML.
    return bot.send_message(int(cid),body[:4000],reply_markup=k,parse_mode=None)


def drain(bot):
    for _ in range(60):
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute('SELECT id,game_id,destination,event,attempts FROM nan_yate_outbox WHERE NOT done AND next_try<=NOW() ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED')
            row=cur.fetchone()
            if not row:return
            oid,gid,dest,e,attempts=row
            cur.execute('SELECT MAX(id) FROM nan_yate_outbox WHERE game_id=%s',(gid,));watermark=cur.fetchone()[0]
            cur.execute('SELECT state FROM nan_yate_games WHERE game_id=%s',(gid,));state=cur.fetchone()
            if not state or (e['kind'] in ('phase','panel') and e['epoch']!=state[0]['epoch']):
                cur.execute('UPDATE nan_yate_outbox SET done=TRUE WHERE id=%s',(oid,));continue
            s=state[0]
            if dest<0:
                wait=s.get('group_delivery_at',0)+3.2-time.time()
                if wait>0:
                    cur.execute("UPDATE nan_yate_outbox SET next_try=NOW()+(%s * INTERVAL '1 second') WHERE id=%s",(wait,oid));continue
            try:
                with group_scope(s['chat_id']):body,k=render_event(bot,s,e)
                # One main phase card per group, edited in place when possible.
                card_field='evidence_card' if e['kind']=='evidence' else 'card'
                recipient=game.player(s,dest) if e['kind']=='panel' else None
                panel_id=recipient.get('panel_id') if recipient else None
                card_id=panel_id if e['kind']=='panel' else s.get(card_field)
                if e['kind'] in ('phase','evidence','result','cancelled','panel') and card_id:
                    try:bot.edit_message_text(body[:4000],dest,card_id,reply_markup=k,parse_mode=None)
                    except Exception as exc:
                        if 'message is not modified' not in str(exc):raise
                else:
                    msg=send_plain(bot,dest,body,k)
                    if e['kind']=='panel' and recipient:
                        index=s['players'].index(recipient)
                        cur.execute("UPDATE nan_yate_games SET state=jsonb_set(state,%s,%s::jsonb) WHERE game_id=%s",('{players,'+str(index)+',panel_id}',str(msg.message_id),gid))
                    if e['kind'] in ('phase','evidence'):
                        # Do not overwrite concurrent state: update only the card JSON field.
                        cur.execute("UPDATE nan_yate_games SET state=jsonb_set(state,%s,%s::jsonb) WHERE game_id=%s",('{'+card_field+'}',str(msg.message_id),gid))
                if e['kind']=='result' and len(body)>4000:
                    for offset in range(4000,len(body),4000):send_plain(bot,dest,body[offset:offset+4000])
                if e['kind']=='panel':cur.execute("UPDATE nan_yate_outbox SET done=TRUE WHERE game_id=%s AND destination=%s AND event->>'kind'='panel' AND NOT done AND id<=%s",(gid,dest,watermark))
                if dest<0:cur.execute("UPDATE nan_yate_games SET state=jsonb_set(state,'{group_delivery_at}',%s::jsonb) WHERE game_id=%s",(str(time.time()),gid))
                if e['kind']=='evidence':
                    cur.execute("UPDATE nan_yate_outbox SET done=TRUE WHERE game_id=%s AND event->>'kind'='evidence' AND NOT done AND id<=%s",(gid,watermark))
                cur.execute('UPDATE nan_yate_outbox SET done=TRUE WHERE id=%s',(oid,))
            except Exception as exc:
                permanent=getattr(exc,'error_code',None) in (400,403)
                cur.execute("UPDATE nan_yate_outbox SET attempts=attempts+1,done=%s,next_try=NOW()+(%s * INTERVAL '1 second') WHERE id=%s",(permanent or attempts>=8,min(120,2**min(attempts,6)),oid))
                LOG.warning('Nan Yate delivery %s: %s',oid,type(exc).__name__)
                if e['kind']=='panel' and permanent and recipient:
                    index=s['players'].index(recipient)
                    cur.execute("UPDATE nan_yate_games SET state=state #- %s WHERE game_id=%s",('{players,'+str(index)+',panel_id}',gid))
                if e['kind'] in ('phase','evidence') and permanent:
                    cur.execute("UPDATE nan_yate_games SET state=state-%s WHERE game_id=%s",('evidence_card' if e['kind']=='evidence' else 'card',gid))


def tick(bot):
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute("SELECT chat_id FROM nan_yate_games WHERE state->>'phase' NOT IN ('finished','cancelled')")
        chats=[r[0] for r in cur.fetchall()]
    for cid in chats:
        with transaction(cid=cid) as (cur,s,_):
            if not s or s['phase'] in ('finished','cancelled'):continue
            start_session(cid,'nan_yate',recover=True)
            now=time.time()
            from core.startup_safety import abandoned
            if abandoned(s,now):
                # Supersede unsent phase/DM events; keep deletion cleanup jobs.
                cur.execute("UPDATE nan_yate_outbox SET done=TRUE WHERE game_id=%s AND NOT done AND event->>'kind' NOT IN ('delete','cancelled')",(s['id'],))
                s['events']=[]
                game.cancel(s)
            elif now>s['deadline'] and now-s['updated']>30 and s['phase']!='lobby':
                # A real process outage: preserve selections and give everyone another chance.
                s['deadline']=now+30;game.emit(s,cid,'phase')
                for p in s['players']:game.emit(s,p['id'],'panel')
            else:game.advance(s,now,random.SystemRandom())
            if now < s['deadline'] and not s['events']:
                if now-s.get('updated',0)>=10:cur.execute("UPDATE nan_yate_games SET state=jsonb_set(state,'{updated}',%s::jsonb),updated_at=NOW() WHERE chat_id=%s",(str(now),cid))
            else:
                persist(cur,s,now)
        invalidate_rewards(s)
        if s['phase'] in ('finished','cancelled'):end_session(cid,'nan_yate')
    drain(bot)
    if chats:return True
    # Keep scheduled cleanup/retries responsive after the last game has ended.
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('SELECT EXISTS(SELECT 1 FROM nan_yate_outbox WHERE NOT done)')
        pending=cur.fetchone()
    return bool(pending and pending[0])


def admin(bot,cid,uid):
    from features.owner_operations import is_owner
    return is_owner(uid) or bot.get_chat_member(cid,uid).status in ('creator','administrator')


def register(bot):
    global WORKER_STARTED
    init_db()
    # Restore locks before registering new group games.
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute("SELECT chat_id FROM nan_yate_games WHERE state->>'phase' NOT IN ('finished','cancelled')")
        for row in cur.fetchall():start_session(row[0],'nan_yate',recover=True)

    @bot.message_handler(commands=['nanyate','နန်းရိပ်'])
    def command(m):
        if m.chat.type not in ('group','supergroup'):return bot.reply_to(m,text('private_required'))
        cid=m.chat.id;reserved=False
        try:
            with transaction(cid=cid) as (cur,old,_):
                if old and old['phase'] not in ('finished','cancelled'):
                    game.emit(old,cid,'phase');persist(cur,old,time.time());return
                settings=snapshot(cid)
                args=m.text.split()[1:]
                if any(a not in ('anonymous','advanced') for a in args):return bot.reply_to(m,text('mode_help'))
                if 'anonymous' in args:settings['anonymous']=True
                if 'advanced' in args:settings['traitor']=True
                ok,_=start_session(cid,'nan_yate')
                if not ok:return bot.reply_to(m,text('busy'))
                reserved=True
                s=game.create(uuid.uuid4().hex[:12],cid,m.from_user.id,settings,time.time())
                game.emit(s,cid,'phase');persist(cur,s,time.time())
        except Exception as exc:
            if reserved:end_session(cid,'nan_yate')
            LOG.warning('Nan Yate create: %s',type(exc).__name__);bot.reply_to(m,text('error'))

    @bot.message_handler(commands=['nanyaterules','နန်းရိပ်စည်းမျဉ်း'])
    def rules(m):bot.reply_to(m,text('rules')+'\n\n'+text('mode_help'))

    @bot.message_handler(commands=['nanyatestop'])
    def stop_command(m):
        if m.chat.type not in ('group','supergroup'):return bot.reply_to(m,text('private_required'))
        try:
            if not admin(bot,m.chat.id,m.from_user.id):return bot.reply_to(m,text('admin'))
            with transaction(cid=m.chat.id) as (cur,s,_):
                if not s or s['phase'] in ('finished','cancelled'):return bot.reply_to(m,text('closed'))
                k=keyboard();k.add(button(s,'yes_stop','stopconfirmed'))
                send_plain(bot,m.chat.id,text('confirm_stop'),k)
        except Exception:bot.reply_to(m,text('error'))

    @bot.message_handler(commands=['start'])
    def private_start(m):
        args=(m.text or '').split()
        if m.chat.type!='private' or len(args)!=2 or not args[1].startswith('ny_'):return ContinueHandling()
        gid=args[1][3:]
        try:
            with transaction(gid=gid) as (cur,s,cid):
                with group_scope(cid):body,k=private_panel(s,m.from_user.id)
                send_plain(bot,m.chat.id,body,k)
        except Exception as exc:bot.reply_to(m,text(str(exc) if isinstance(exc,ValueError) else 'error'))

    @bot.callback_query_handler(func=lambda q:(q.data or '').startswith('ny:'))
    def callback_handler(q):
        try:
            _,gid,epoch,kind,value=q.data.split(':',4)
            uid=q.from_user.id
            with transaction(gid=gid) as (cur,s,cid),group_scope(cid):
                if int(epoch)!=s['epoch'] or s['phase'] in ('finished','cancelled') or time.time()>s['deadline']:raise ValueError('closed')
                private=q.message.chat.type=='private'
                if kind in ('begin','stop','stopconfirmed'):
                    if q.message.chat.id!=cid or not admin(bot,cid,uid):raise ValueError('admin')
                    if kind=='begin':game.begin(s,time.time(),random.SystemRandom())
                    elif kind=='stop':
                        k=keyboard();k.add(button(s,'yes_stop','stopconfirmed'));send_plain(bot,cid,text('confirm_stop'),k)
                    else:game.cancel(s)
                else:
                    if not private or q.message.chat.id!=uid:raise ValueError('unavailable')
                    if kind=='join':
                        if bot.get_chat_member(cid,uid).status in ('left','kicked'):raise ValueError('not_player')
                        game.join(s,uid,q.from_user.first_name or 'Player');game.emit(s,cid,'phase')
                    elif kind=='withdraw':
                        p=game.player(s,uid)
                        if s['phase']!='lobby' or not p:raise ValueError('unavailable')
                        s['players'].remove(p);game.emit(s,cid,'phase')
                    elif kind=='panel':pass
                    elif kind=='menu':
                        mk,page=value.split('.');body,k=menu(s,uid,mk,int(page));send_plain(bot,uid,body,k)
                    elif kind=='publicmenu':
                        p=game.player(s,uid)
                        if not p:raise ValueError('not_player')
                        public=s.get('public_evidence',[]);page=max(0,min(int(value),max(0,(len(public)-1)//6)))
                        chosen=public[page*6:page*6+6];body='\n\n'.join(evidence_text(s,e) for e in s['evidence'] if e['id'] in chosen) or text('empty')
                        k=keyboard()
                        if page:k.add(button(s,'previous','publicmenu',str(page-1)))
                        if (page+1)*6<len(public):k.add(button(s,'next','publicmenu',str(page+1)))
                        k.add(button(s,'back','panel'));send_plain(bot,uid,body,k)
                    elif kind=='questmenu':
                        p=game.player(s,uid)
                        if not p or not p['alive'] or s['phase']!='night' or not s['rules']['quests'] or p['quest_done']:raise ValueError('unavailable')
                        total=sum(p['quest']);options=[total,total+3,total-2,total+7];random.shuffle(options);k=keyboard()
                        for v in options:k.add(types.InlineKeyboardButton(str(v),callback_data=callback(s,'quest',str(v))))
                        send_plain(bot,uid,text('quest_question',a=p['quest'][0],b=p['quest'][1],coins=s['rules']['quest_coins']),k)
                    elif kind=='shopmenu':
                        p=game.player(s,uid)
                        if not p or not p['alive'] or s['phase']!='day' or not s['rules']['shop']:raise ValueError('unavailable')
                        k=keyboard();k.add(button(s,'seal','buy','seal',cost=s['rules']['seal_cost']),button(s,'armor','buy','armor',cost=s['rules']['armor_cost']));send_plain(bot,uid,text('shop_help'),k)
                    elif kind=='traitormenu':
                        if s['traitor_offer']!=str(uid):raise ValueError('unavailable')
                        k=keyboard();k.add(button(s,'accept','traitor','yes'),button(s,'decline','traitor','no'));send_plain(bot,uid,text('traitor_help'),k)
                    else:game.act(s,uid,kind,value)
                    if kind not in ('menu','publicmenu','questmenu','shopmenu','traitormenu'):
                        game.emit(s,uid,'panel')
                if kind in ('escape','traitor'):game.check_win(s)
                persist(cur,s,time.time())
            invalidate_rewards(s)
            if s['phase'] in ('finished','cancelled'):end_session(cid,'nan_yate')
            bot.answer_callback_query(q.id,text('saved'))
        except Exception as exc:
            if not isinstance(exc,ValueError):LOG.warning('Nan Yate callback: %s',type(exc).__name__)
            try:bot.answer_callback_query(q.id,text(str(exc) if isinstance(exc,ValueError) else 'error'),show_alert=True)
            except Exception:pass

    @bot.message_handler(commands=['nychat','nywhisper'])
    def chat_command(m):
        if m.chat.type!='private':return bot.reply_to(m,text('chat_help'))
        try:
            parts=m.text.split(maxsplit=3 if m.text.split()[0].split('@')[0]=='/nywhisper' else 2)
            whisper=parts[0].split('@')[0]=='/nywhisper'
            if len(parts)!=(4 if whisper else 3):return bot.reply_to(m,text('chat_help'))
            gid=parts[1];body=parts[-1].strip()
            if not body or len(body)>350:raise ValueError('unavailable')
            with transaction(gid=gid) as (cur,s,cid),group_scope(cid):
                p=game.player(s,m.from_user.id)
                if not p or not p['alive'] or s['phase'] not in ('night','day') or time.time()>s['deadline']:raise ValueError('unavailable')
                now=time.time()
                if now-p.get('last_chat',0)<4 or p.get('chat_count_day')==s['day'] and p.get('chat_count',0)>=15:raise ValueError('unavailable')
                if p.get('chat_count_day')!=s['day']:p['chat_count']=0
                p['last_chat']=now;p['chat_count_day']=s['day'];p['chat_count']=p.get('chat_count',0)+1
                if whisper:
                    target=next((v for v in game.alive(s) if str(v['number'])==parts[2]),None)
                    if not target or not any(set(link)=={p['id'],target['id']} for link in s['links']):raise ValueError('unavailable')
                    dests=[target['id']]
                elif s['phase']=='night' and p['side']=='plot' and not p.get('turned'):
                    dests=[v['id'] for v in game.alive(s) if v['side']=='plot' and v is not p and not v.get('turned')]
                elif s['phase']=='day' and s['rules']['anonymous']:
                    if p.get('anonymous_day')==s['day'] and p.get('anonymous_count',0)>=2:raise ValueError('anonymous_limit')
                    if p.get('anonymous_day')!=s['day']:p['anonymous_count']=0
                    p['anonymous_day']=s['day'];p['anonymous_count']=p.get('anonymous_count',0)+1;dests=[cid]
                else:raise ValueError('unavailable')
                for dest in dests:game.emit(s,dest,'relay',number=p['number'],text=body)
                p['active']=True;p['participated']=True;persist(cur,s,now)
            bot.reply_to(m,text('chat_sent'))
        except Exception as exc:bot.reply_to(m,text(str(exc) if isinstance(exc,ValueError) else 'error'))

    @bot.message_handler(content_types=['left_chat_member'])
    def member_left(m):
        try:
            with transaction(cid=m.chat.id) as (cur,s,_):
                if not s or s['phase'] in ('finished','cancelled'):return ContinueHandling()
                p=game.player(s,m.left_chat_member.id)
                if p:
                    if s['phase']=='lobby':s['players'].remove(p);game.emit(s,m.chat.id,'phase')
                    elif p['alive']:
                        p['forfeit']=True;p['departed']=True;game.die(s,p,'leave');game.check_win(s)
                    persist(cur,s,time.time())
            if s and s['phase'] in ('finished','cancelled'):invalidate_rewards(s);end_session(m.chat.id,'nan_yate')
        except Exception as exc:LOG.warning('Nan Yate departure: %s',type(exc).__name__)
        return ContinueHandling()

    with BOOT_LOCK:
        if not WORKER_STARTED:
            WORKER_STARTED=True
            def loop():
                while True:
                    WAKE.clear();active=True
                    try:active=tick(bot)
                    except Exception as exc:LOG.warning('Nan Yate worker: %s',type(exc).__name__)
                    WAKE.wait(3 if active else 30)
            threading.Thread(target=loop,name='nan-yate',daemon=True).start()
