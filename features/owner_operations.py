"""Owner operations, durable schedules, narrowly scoped assistants and staged releases."""
import html
import functools
import json
import os
import secrets
import threading
import time
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from flask import Blueprint,request,abort
from telebot import types
from telebot.handler_backends import ContinueHandling
from database.db import get_db_connection

MMT=ZoneInfo('Asia/Yangon')
PERMISSIONS={'edit','announce','stats'}
COMMAND_GAMES={'boss':'boss_raid','bossraid':'boss_raid','raid':'boss_raid','teambattle':'team_battle','pair':'pair_challenge','mathbattle':'math_battle','math':'math_battle','wordchain':'word_chain','wc':'word_chain','emoji':'emoji_guess','emojiguess':'emoji_guess','speedtap':'speed_tap','wyr':'would_you_rather','wouldyourather':'would_you_rather','imposter':'imposter','နန်းရိပ်':'nan_yate'}
# Append newly implemented games here; the private menu reverses this creation order.
GAME_LABELS={
    'coin':'🪙 Coin Flip','trivia':'🧠 Trivia','guess':'🎯 Number Guess',
    'dice':'🎲 Dice','slot':'🎰 Slot','eight_ball':'🎱 Magic 8 Ball',
    'love':'❤️ Love Calculator','random':'🎲 Random Number',
    'emoji_guess':'😀 Emoji Guess','speed_tap':'⚡ Speed Tap','word_chain':'🔗 Word Chain',
    'math_battle':'🧮 Math Battle','daily_challenge':'📅 Daily Challenge','boss_raid':'👹 Boss Raid',
    'team_battle':'⚔️ Team Battle','pair_challenge':'👥 Pair Challenge',
    'would_you_rather':'🤔 Would You Rather','imposter':'🎭 Imposter','nan_yate':'🏯 နန်းရိပ်','draw_guess':'🎨 Draw & Guess','this_or_that':'🖼️ This or That'}
GAME_COMMANDS={'coin':'/coin','trivia':'/trivia','guess':'/guess','dice':'/dice','slot':'/slot',
    'eight_ball':'/8ball','love':'/love','random':'/random','daily_challenge':'/daily',
    'boss_raid':'/boss','team_battle':'/teambattle','math_battle':'/mathbattle',
    'pair_challenge':'/pair','imposter':'/imposter','word_chain':'/wordchain',
    'emoji_guess':'/emoji','speed_tap':'/speedtap','would_you_rather':'/wyr','nan_yate':'/nanyate','draw_guess':'/draw','this_or_that':'/tot'}
GAME_HANDLERS={k:'enabled.bot.'+fn for k,fn in {
    'coin':'coin_command','trivia':'trivia_command','guess':'guess_command','dice':'roll_dice',
    'slot':'roll_slot','eight_ball':'eight_ball_command','love':'love_calculator','random':'random_command',
    'boss_raid':'boss_raid_command','team_battle':'team_battle_command','math_battle':'math_battle_command',
    'pair_challenge':'pair_challenge_command','word_chain':'word_chain_command',
    'emoji_guess':'emoji_guess_command','speed_tap':'speed_tap_command'}.items()}
GAME_HANDLERS.update(this_or_that='enabled.features.this_or_that.command',draw_guess='enabled.features.draw_guess.command',nan_yate='enabled.features.nan_yate.command',imposter='enabled.features.imposter.command',would_you_rather='enabled.features.would_you_rather.wyr_command',daily_challenge='enabled.features.daily_challenge.daily_command')
COMMAND_GAMES.update({command.lstrip('/'):kind for kind,command in GAME_COMMANDS.items()})
COMMAND_GAMES['drawguess']='draw_guess'
COMMAND_GAMES['thisorthat']='this_or_that'


def ordered_games():
    return list(reversed(list(GAME_LABELS.items())))


_ready=False
_lock=threading.RLock()
_cache={'groups':set(),'releases':{}}
_loaded=0


def initialize(cur):
    global _ready
    cur.execute('CREATE TABLE IF NOT EXISTS owner_assistants (user_id BIGINT PRIMARY KEY, permissions JSONB NOT NULL, updated_at TIMESTAMPTZ DEFAULT NOW())')
    cur.execute('CREATE TABLE IF NOT EXISTS owner_test_groups (chat_id BIGINT PRIMARY KEY REFERENCES owner_groups(chat_id))')
    cur.execute("CREATE TABLE IF NOT EXISTS owner_feature_releases (feature TEXT PRIMARY KEY, rollout TEXT NOT NULL CHECK (rollout IN ('test','all')))")
    cur.execute('''CREATE TABLE IF NOT EXISTS owner_schedules (id BIGSERIAL PRIMARY KEY,creator BIGINT NOT NULL,
      target TEXT NOT NULL,message TEXT NOT NULL DEFAULT '',source_chat BIGINT,source_msg BIGINT,
      due_at TIMESTAMPTZ NOT NULL,status TEXT NOT NULL DEFAULT 'pending',request_id TEXT UNIQUE NOT NULL,
      job_id BIGINT REFERENCES owner_broadcasts(id),error TEXT NOT NULL DEFAULT '',created_at TIMESTAMPTZ DEFAULT NOW())''')
    cur.execute('''CREATE TABLE IF NOT EXISTS owner_operation_drafts (user_id BIGINT PRIMARY KEY,
      data JSONB NOT NULL,expires_at TIMESTAMPTZ NOT NULL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS owner_usage_events (id BIGSERIAL PRIMARY KEY,
      chat_id BIGINT NOT NULL,kind TEXT NOT NULL,label TEXT NOT NULL DEFAULT '',
      event_key TEXT UNIQUE,created_at TIMESTAMPTZ DEFAULT NOW())''')
    cur.execute('CREATE INDEX IF NOT EXISTS owner_usage_date ON owner_usage_events(created_at,chat_id)')
    cur.execute("CREATE INDEX IF NOT EXISTS owner_schedule_due ON owner_schedules(due_at) WHERE status='pending'")
    _ready=True


def is_owner(uid):return str(uid)==os.getenv('OWNER_TELEGRAM_ID','').strip()


def can(uid,permission):
    if is_owner(uid):return True
    if not _ready or permission not in PERMISSIONS:return False
    try:
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute('SELECT permissions FROM owner_assistants WHERE user_id=%s',(uid,))
            row=cur.fetchone()
        return bool(row and permission in row[0])
    except Exception:return False


def set_assistant(actor,uid,permissions):
    if not is_owner(actor):raise ValueError('Owner only')
    uid=int(uid);permissions=sorted(set(permissions))
    if uid<=0 or not set(permissions)<=PERMISSIONS or is_owner(uid):raise ValueError('Invalid assistant ID or permissions')
    with get_db_connection() as conn,conn.cursor() as cur:
        if not permissions:cur.execute('DELETE FROM owner_assistants WHERE user_id=%s',(uid,))
        else:cur.execute('''INSERT INTO owner_assistants(user_id,permissions) VALUES(%s,%s::jsonb)
          ON CONFLICT(user_id) DO UPDATE SET permissions=EXCLUDED.permissions,updated_at=NOW()''',(uid,json.dumps(permissions)))


def refresh():
    global _loaded,_cache
    with _lock:
        if not _ready or time.monotonic()-_loaded<10:return
        try:
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute('SELECT chat_id FROM owner_test_groups');groups={r[0] for r in cur.fetchall()}
                cur.execute('SELECT feature,rollout FROM owner_feature_releases');releases=dict(cur.fetchall())
            _cache={'groups':groups,'releases':releases};_loaded=time.monotonic()
        except Exception:
            _loaded=time.monotonic() # Keep the last valid rollout during a transient DB outage.


def feature_allowed(feature,chat_id):
    if not _ready or chat_id>=0:return True
    refresh()
    with _lock:return _cache['releases'].get(feature,'all')!='test' or chat_id in _cache['groups']


def release_features():
    from core.customization import CATALOG
    return {**{k:e['label'] for k,e in CATALOG.items() if k.startswith('enabled.')},
            **{'game:'+k:label for k,label in ordered_games()}}


def change_release(actor,feature,rollout):
    global _loaded
    if not is_owner(actor):raise ValueError('Owner only')
    if feature not in release_features() or rollout not in ('test','all'):raise ValueError('Invalid feature or rollout')
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(759012351)")
        if rollout=='test':
            cur.execute('SELECT 1 FROM owner_test_groups LIMIT 1')
            if not cur.fetchone():raise ValueError('ရွေးထားတဲ့ Test Group အရင်လိုပါတယ်။')
        keys=[feature]
        if feature.startswith('game:'):
            handler=GAME_HANDLERS.get(feature[5:])
            if handler in release_features():keys.append(handler)
        for key in keys:
            cur.execute('INSERT INTO owner_feature_releases(feature,rollout) VALUES(%s,%s) ON CONFLICT(feature) DO UPDATE SET rollout=EXCLUDED.rollout',(key,rollout))
    with _lock:
        for key in keys:_cache['releases'][key]=rollout
        _loaded=0


def test_group(actor,cid,enabled):
    global _loaded
    if not is_owner(actor):raise ValueError('Owner only')
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT 1 FROM owner_groups WHERE chat_id=%s AND active',(cid,))
        if not cur.fetchone():raise ValueError('Active group မရှိပါ။')
        if enabled:cur.execute('INSERT INTO owner_test_groups(chat_id) VALUES(%s) ON CONFLICT DO NOTHING',(cid,))
        else:cur.execute('DELETE FROM owner_test_groups WHERE chat_id=%s',(cid,))
    with _lock:
        if enabled:_cache['groups'].add(cid)
        else:_cache['groups'].discard(cid)
        _loaded=0


def game_launch(kind):
    """Cover engines without core sessions, including their automatic launches."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapped(chat_id,*args,**kwargs):
            if not feature_allowed('game:'+kind,chat_id):return False,None
            result=fn(chat_id,*args,**kwargs)
            if result[0]:usage(chat_id,'game',kind)
            return result
        return wrapped
    return decorator


def usage(chat_id,kind,label='',event_key=None):
    if not _ready or chat_id>=0:return
    try:
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute('INSERT INTO owner_usage_events(chat_id,kind,label,event_key) VALUES(%s,%s,%s,%s) ON CONFLICT(event_key) DO NOTHING',(chat_id,kind,label[:160],event_key))
    except Exception as exc:print('Usage record:',type(exc).__name__)


def stats():
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('''SELECT g.title,e.chat_id,
          COUNT(*) FILTER(WHERE e.kind='message'),COUNT(*) FILTER(WHERE e.kind='command'),
          COUNT(*) FILTER(WHERE e.kind='game') FROM owner_usage_events e
          LEFT JOIN owner_groups g ON g.chat_id=e.chat_id
          WHERE e.created_at>=NOW()-INTERVAL '30 days' GROUP BY g.title,e.chat_id
          ORDER BY COUNT(*) FILTER(WHERE e.kind='game') DESC,COUNT(*) FILTER(WHERE e.kind='message') DESC LIMIT 20''');groups=cur.fetchall()
        cur.execute("SELECT label,COUNT(*) FROM owner_usage_events WHERE kind='game' AND created_at>=NOW()-INTERVAL '30 days' GROUP BY label ORDER BY COUNT(*) DESC LIMIT 20");games=cur.fetchall()
        cur.execute("SELECT COALESCE(g.title,''),e.chat_id,e.created_at FROM owner_usage_events e LEFT JOIN owner_groups g ON g.chat_id=e.chat_id WHERE kind='left' ORDER BY e.created_at DESC LIMIT 20");left=cur.fetchall()
    return groups,games,left


def parse_when(text,now=None):
    now=now or datetime.now(timezone.utc)
    try:when=datetime.strptime(text.strip().replace('T',' '),'%Y-%m-%d %H:%M').replace(tzinfo=MMT).astimezone(timezone.utc)
    except ValueError:raise ValueError('Myanmar time: YYYY-MM-DD HH:MM ဥပမာ 2026-10-12 09:00')
    if not now+timedelta(seconds=30)<when<=now+timedelta(days=366):raise ValueError('အနာဂတ်အချိန်ကို ၁ နှစ်အတွင်း ရွေးပါ။')
    return when


def destinations(target):
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT chat_id FROM owner_groups WHERE active ORDER BY chat_id');ids=[r[0] for r in cur.fetchall()]
    if target=='all':return ids
    try:cid=int(target)
    except (ValueError,TypeError):raise ValueError('Invalid group')
    if cid not in ids:raise ValueError('Active group မရှိပါ။')
    return [cid]


def create_schedule(actor,target,when,message='',source_chat=None,source_msg=None,request_id=None):
    if not can(actor,'announce'):raise ValueError('Announcement permission မရှိပါ။')
    if not destinations(target):raise ValueError('Active group မရှိပါ။')
    if when.tzinfo is None or when<=datetime.now(timezone.utc):raise ValueError('အနာဂတ်အချိန် ရွေးပါ။')
    if source_chat is None:
        if not isinstance(message,str) or not 1<=len(message.strip())<=4000:raise ValueError('စာ 1–4000 characters လိုပါတယ်။')
    elif source_msg is None:raise ValueError('Message source မရှိပါ။')
    token=request_id or secrets.token_hex(20)
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('''INSERT INTO owner_schedules(creator,target,message,source_chat,source_msg,due_at,request_id)
          VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(request_id) DO NOTHING RETURNING id''',
          (actor,str(target),message,source_chat,source_msg,when,token))
        row=cur.fetchone()
        if not row:raise ValueError('ဒီ request ကို သိမ်းပြီးသားပါ။')
    return row[0]


def cancel_schedule(actor,sid):
    if not can(actor,'announce'):raise ValueError('Permission မရှိပါ။')
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(759012350)')
        cur.execute("UPDATE owner_schedules SET status='cancelled' WHERE id=%s AND status='pending' AND (creator=%s OR %s) RETURNING id",(int(sid),actor,is_owner(actor)))
        if not cur.fetchone():raise ValueError('Pending schedule ကိုပဲ cancel လုပ်နိုင်ပါတယ်။')


def due_schedules():
    """Serialize due-job creation. Broadcast request IDs recover the crash gap safely."""
    from features.owner_dashboard import _queue_broadcast,_send_broadcast
    queued=[]
    with get_db_connection() as lock_conn,lock_conn.cursor() as lock_cur:
        lock_cur.execute('SELECT pg_try_advisory_xact_lock(759012350)')
        if not lock_cur.fetchone()[0]:return
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute("SELECT id,creator,target,message,source_chat,source_msg,request_id FROM owner_schedules WHERE status='pending' AND due_at<=NOW() ORDER BY due_at LIMIT 20")
            jobs=cur.fetchall()
        for sid,actor,target,message,source_chat,source_msg,token in jobs:
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute('SELECT id FROM owner_broadcasts WHERE request_id=%s',(token,));existing=cur.fetchone()
                if existing:jid=existing[0]
                elif not can(actor,'announce'):
                    cur.execute("UPDATE owner_schedules SET status='cancelled',error='Creator permission revoked' WHERE id=%s AND status='pending'",(sid,));continue
                else:jid=None
            if jid is None:
                try:jid=_queue_broadcast(message,destinations(target),source_chat,source_msg,token)
                except ValueError as exc:
                    if 'already running' in str(exc):break
                    with get_db_connection() as conn,conn.cursor() as cur:cur.execute("UPDATE owner_schedules SET status='failed',error=%s WHERE id=%s",(str(exc)[:300],sid))
                    continue
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute("UPDATE owner_schedules SET status='queued',job_id=%s WHERE id=%s AND status='pending'",(jid,sid))
            queued.append(jid)
    for jid in queued:threading.Thread(target=_send_broadcast,args=(jid,),daemon=True).start()


def supervisor():
    while True:
        try:
            due_schedules()
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute("DELETE FROM owner_usage_events WHERE created_at<NOW()-INTERVAL '90 days'")
                cur.execute('DELETE FROM owner_operation_drafts WHERE expires_at<NOW()')
                cur.execute("UPDATE owner_schedules s SET status=b.status FROM owner_broadcasts b WHERE s.job_id=b.id AND s.status='queued' AND b.status!='running'")
        except Exception as exc:print('Owner schedule:',type(exc).__name__)
        time.sleep(20)


def leave_group(actor,cid,bot):
    if not is_owner(actor):raise ValueError('Owner only')
    destinations(str(cid))
    if not bot.leave_chat(cid):raise ValueError('Telegram က leave ကို လက်မခံပါ။')
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('UPDATE owner_groups SET active=FALSE WHERE chat_id=%s',(cid,))
        cur.execute('DELETE FROM owner_test_groups WHERE chat_id=%s',(cid,))
    usage(cid,'left','Owner requested')


def schedule_rows(actor):
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT id,target,due_at,status FROM owner_schedules WHERE creator=%s OR %s ORDER BY id DESC LIMIT 20',(actor,is_owner(actor)))
        return cur.fetchall()


def draft(uid,data=None):
    with get_db_connection() as conn,conn.cursor() as cur:
        if data is not None:
            if not data:cur.execute('DELETE FROM owner_operation_drafts WHERE user_id=%s',(uid,))
            else:cur.execute("INSERT INTO owner_operation_drafts(user_id,data,expires_at) VALUES(%s,%s::jsonb,NOW()+INTERVAL '10 minutes') ON CONFLICT(user_id) DO UPDATE SET data=EXCLUDED.data,expires_at=EXCLUDED.expires_at",(uid,json.dumps(data)))
            return data
        cur.execute('SELECT data FROM owner_operation_drafts WHERE user_id=%s AND expires_at>NOW()',(uid,));row=cur.fetchone()
        return row[0] if row else None


def register(app,bot,replace_card,clear_broadcast):
    from features import owner_dashboard
    from features.owner_dashboard import _protect,_verify_csrf,_csrf,_shell
    bp=Blueprint('owner_operations',__name__,url_prefix='/owner/tools')
    def groups():
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute('SELECT chat_id,title FROM owner_groups WHERE active ORDER BY title');return cur.fetchall()
    def choices():return "<option value='all'>All Groups</option>"+''.join(f"<option value='{cid}'>{html.escape(title or str(cid))}</option>" for cid,title in groups())
    @bp.route('/',methods=['GET','POST'])
    @_protect
    def tools_page():
        actor=int(os.getenv('OWNER_TELEGRAM_ID','0'));notice=''
        if request.method=='POST':
            _verify_csrf()
            try:
                action=request.form.get('action','')
                if action=='schedule':
                    if request.form.get('confirm')!='yes':raise ValueError('Confirm လိုပါတယ်။')
                    sid=create_schedule(actor,request.form.get('target'),parse_when(request.form.get('when','')),request.form.get('message',''),request_id=request.form.get('request_id'))
                    notice=f'Schedule #{sid} saved.'
                elif action=='cancel':cancel_schedule(actor,request.form.get('id'));notice='Cancelled.'
                elif action=='assistant':set_assistant(actor,request.form.get('uid'),request.form.getlist('permission'));notice='Assistant permissions saved.'
                elif action=='test':test_group(actor,int(request.form.get('group')),request.form.get('enabled')=='yes');notice='Test Group updated.'
                elif action=='release':change_release(actor,request.form.get('feature'),request.form.get('rollout'));notice='Feature rollout updated.'
                elif action=='leave':
                    if request.form.get('confirm')!='yes':raise ValueError('Confirm leave လိုပါတယ်။')
                    leave_group(actor,int(request.form.get('group')),bot);notice='Bot left the group.'
                else:raise ValueError('Unknown action')
            except (ValueError,TypeError) as exc:notice=str(exc)
        csrf=html.escape(_csrf(),quote=True)
        def form(action):return f"<form method='post'><input type='hidden' name='csrf' value='{csrf}'><input type='hidden' name='action' value='{action}'>"
        refresh()
        body=f"<h1>Owner Tools</h1><p>{html.escape(notice)}</p><div class='panel'><h2>Scheduled Announcement</h2><p>Myanmar time · original media can be scheduled from /ownertools in Telegram.</p>"+form('schedule')+f"<input type='hidden' name='request_id' value='{secrets.token_hex(20)}'><select name='target'>{choices()}</select><input type='datetime-local' name='when' required><textarea name='message' maxlength='4000' required></textarea><label><input type='checkbox' style='width:auto' name='confirm' value='yes' required> Confirm schedule</label><button>Schedule</button></form></div>"
        # datetime-local uses T; accept it in the shared parser.
        body+="<div class='panel'><h2>Schedules</h2>"
        for sid,target,when,status in schedule_rows(actor):
            body+=f"<p>#{sid} · {html.escape(target)} · {when.astimezone(MMT):%Y-%m-%d %H:%M} MMT · {html.escape(status)}</p>"
            if status=='pending':body+=form('cancel')+f"<input type='hidden' name='id' value='{sid}'><button>Cancel #{sid}</button></form>"
        body+='</div><div class="panel"><h2>Test Groups</h2><p>Existing features stay available to all groups until you select Test only. Ongoing games can finish.</p>'
        for cid,title in groups():
            selected=cid in _cache['groups'];body+=form('test')+f"<input type='hidden' name='group' value='{cid}'><input type='hidden' name='enabled' value='{'no' if selected else 'yes'}'><button>{'Remove test: ' if selected else 'Use for test: '}{html.escape(title or str(cid))}</button></form>"
        body+=form('release')+"<select name='feature'>"+''.join(f"<option value='{html.escape(k,quote=True)}'>{html.escape(v)} · {_cache['releases'].get(k,'all')}</option>" for k,v in release_features().items())+"</select><select name='rollout'><option value='test'>Test groups only</option><option value='all'>All groups / Publish</option></select><button>Apply rollout</button></form></div>"
        with get_db_connection() as conn,conn.cursor() as cur:cur.execute('SELECT user_id,permissions FROM owner_assistants ORDER BY user_id');assistants=cur.fetchall()
        body+="<div class='panel'><h2>Owner Assistants</h2><p>Assistants use /staff in private chat. They cannot change roles, leave groups or publish test features.</p>"+form('assistant')+"<input name='uid' type='number' min='1' required placeholder='Telegram user ID'>"+''.join(f"<label><input style='width:auto' type='checkbox' name='permission' value='{p}'> {p}</label>" for p in sorted(PERMISSIONS))+"<p>No permissions = revoke access.</p><button>Save permissions</button></form>"
        body+=''.join(f"<p>{uid}: {html.escape(', '.join(perms))}</p>" for uid,perms in assistants)+'</div>'
        body+="<div class='panel'><h2>Leave Group</h2>"+form('leave')+"<select name='group'>"+''.join(f"<option value='{cid}'>{html.escape(title or str(cid))}</option>" for cid,title in groups())+"</select><label><input style='width:auto' type='checkbox' name='confirm' value='yes' required> Confirm: bot will leave this group.</label><button>Leave group</button></form></div>"
        body+="<div class='panel'><h2>Usage · Last 30 days</h2><p>Counts start when this feature is deployed. Game starts count sessions; commands count command messages.</p>"
        activity,games,left=stats()
        body+='<table><tr><th>Group</th><th>Messages</th><th>Commands</th><th>Game starts</th></tr>'+''.join(f'<tr><td>{html.escape(title or str(cid))}</td><td>{m}</td><td>{c}</td><td>{g}</td></tr>' for title,cid,m,c,g in activity)+'</table><h3>Games</h3>'+''.join(f'<p>{html.escape(name)}: {count}</p>' for name,count in games)+'<h3>Left groups</h3>'+''.join(f'<p>{html.escape(title or str(cid))} · {when.astimezone(MMT):%Y-%m-%d %H:%M}</p>' for title,cid,when in left)+'</div>'
        return _shell(body)
    app.register_blueprint(bp)
    threading.Thread(target=supervisor,daemon=True).start()

    def private(m):
        chat=getattr(m,'chat',None) or getattr(getattr(m,'message',None),'chat',None)
        return bool(chat and chat.type=='private' and m.from_user)
    def kb(rows):
        markup=types.InlineKeyboardMarkup(row_width=1)
        for text,data in rows:markup.add(types.InlineKeyboardButton(text,callback_data=data))
        return markup
    def card(uid,text,rows):replace_card(uid,uid,text,kb(rows))
    def permitted(q,permission=None):return private(q) and (is_owner(q.from_user.id) if permission is None else can(q.from_user.id,permission))
    def home(uid):
        rows=[]
        if is_owner(uid):rows+=[('🧪 Game စမ်းသပ်ရန်','ops:tests:0'),('🚪 Leave Group','ops:leavegroups:0'),('👥 Assistants','ops:assistants')]
        if can(uid,'announce'):rows+=[('📅 Schedule Announcement','ops:announce'),('📜 Schedules','ops:schedules')]
        if can(uid,'stats'):rows.append(('📊 Usage','ops:stats'))
        if can(uid,'edit'):rows.append(('⚙️ Settings & Messages','ctl:home:0'))
        if is_owner(uid):rows.append(('⬅️ Owner Panel','own:menu'))
        card(uid,'👑 OWNER TOOLS\n\nအောက်က function ကို ရွေးပါ။',rows)
    def schedules(uid):
        rows=[];lines=['📜 Schedules · Myanmar time']
        for sid,target,when,status in schedule_rows(uid):
            lines.append(f'#{sid} · {target} · {when.astimezone(MMT):%m-%d %H:%M} · {status}')
            if status=='pending':rows.append((f'❌ Cancel #{sid}',f'ops:cancel:{sid}'))
        rows.append(('⬅️ Back','ops:home'));card(uid,'\n'.join(lines)[:3500],rows)
    def selected_groups():
        refresh()
        return [(cid,title or str(cid)) for cid,title in groups() if cid in _cache['groups']]
    def selected_card(uid,cid,page=0,notice=''):
        title=dict(groups()).get(cid,str(cid))
        rows=[('🎮 Game ရွေးမယ်','ops:features:0'),('👥 Group ရွေးမယ် / ပြောင်းမယ်',f'ops:tests:{page}')]
        if cid in _cache['groups']:rows.append(('ဖယ်မယ်',f'ops:test:{cid}:0:{page}'))
        rows.append(('⬅️ နောက်သို့','ops:home'))
        card(uid,(notice or ('✅ '+title+' ကို ရွေးထားပြီးပါပြီ။'))+'\n\nအခု စမ်းချင်တဲ့ Game ကို ရွေးပါ။',rows)
    def group_list(uid,action,page,notice=''):
        entries=groups();rows=[];refresh()
        for cid,title in entries[page*10:(page+1)*10]:
            enabled=cid in _cache['groups']
            label=('✅ ' if enabled else '')+(title or str(cid))[:45] if action=='tests' else (title or str(cid))[:45]
            data=f'ops:test:{cid}:1:{page}' if action=='tests' else f'ops:leave:{cid}'
            rows.append((label,data))
        if page:rows.append(('← ရှေ့စာမျက်နှာ',f'ops:{action}:{page-1}'))
        if (page+1)*10<len(entries):rows.append(('နောက်စာမျက်နှာ →',f'ops:{action}:{page+1}'))
        if action=='tests' and selected_groups():rows.append(('🎮 Game ရွေးမယ်','ops:features:0'))
        rows.append(('⬅️ နောက်သို့','ops:home'))
        text='🧪 ဘယ် Group မှာ Game စမ်းချင်လဲ?\n\nအောက်က Group ကို နှိပ်ရွေးပါ။' if action=='tests' else '🚪 ထွက်ခိုင်းချင်တဲ့ Group ရွေးပါ။'
        if notice:text=notice+'\n\n'+text
        card(uid,text,rows)
    def game_list(uid,page=0):
        entries=ordered_games();page=max(0,min(page,(len(entries)-1)//8))
        rows=[(label,f'ops:game:{kind}') for kind,label in entries[page*8:(page+1)*8]]
        if page:rows.append(('← ရှေ့ဂိမ်းများ',f'ops:features:{page-1}'))
        if (page+1)*8<len(entries):rows.append(('နောက်ဂိမ်းများ →',f'ops:features:{page+1}'))
        rows += [('👥 စမ်းမယ့် Group ရွေးမယ်','ops:tests:0'),('⬅️ နောက်သို့','ops:home')]
        names=', '.join(title[:45] for _,title in selected_groups())
        text=f'🎮 ဘယ် Game ကို စမ်းချင်လဲ? ({page+1}/{(len(entries)+7)//8})'
        text+='\n\nစမ်းမယ့် Group: '+names[:500] if names else '\n\nစမ်းမယ့် Group ကို အရင်ရွေးပါ။'
        card(uid,text,rows)
    def game_card(uid,kind,notice=''):
        if kind not in GAME_LABELS:raise ValueError('Game မရှိပါ။')
        refresh()
        testing=any(_cache['releases'].get(key)=='test' for key in ['game:'+kind,GAME_HANDLERS.get(kind)])
        text=GAME_LABELS[kind]+'\n\n'+(notice+'\n\n' if notice else '')
        text+='လက်ရှိ: '+('စမ်းသပ် Group မှာပဲ ဖွင့်ထားပါတယ်။' if testing else 'Group အားလုံးမှာ ဖွင့်ထားပါတယ်။')
        selected=selected_groups()
        if selected:text+='\n\nစမ်းသပ် Group: '+', '.join(title[:45] for _,title in selected)[:500]
        if notice:text+='\n\nအဲဒီ Group ထဲမှာ '+GAME_COMMANDS[kind]+' ပို့ပြီး ကစားပါ။'
        rows=[('🧪 ရွေးထားတဲ့ Group မှာပဲ စမ်းမယ်',f'ops:mode:{kind}:test'),('🌍 Group အားလုံးမှာ ဖွင့်မယ်',f'ops:mode:{kind}:all'),('🎮 တခြား Game ရွေးမယ်','ops:features:0'),('👥 Group ပြောင်းမယ်','ops:tests:0')]
        card(uid,text,rows)
    def targets(uid,page=0):
        entries=groups();rows=[('🌍 All Groups','ops:target:all')]
        rows += [((title or str(cid))[:50],f'ops:target:{cid}') for cid,title in entries[page*10:(page+1)*10]]
        if page:rows.append(('← Previous',f'ops:targets:{page-1}'))
        if (page+1)*10<len(entries):rows.append(('Next →',f'ops:targets:{page+1}'))
        rows.append(('❌ Cancel','ops:home'));card(uid,'📅 Destination ရွေးပါ။',rows)
    @bot.message_handler(commands=['ownertools','staff'])
    def owner_tools_command(m):
        if not private(m) or not (is_owner(m.from_user.id) or any(can(m.from_user.id,p) for p in PERMISSIONS)):return ContinueHandling()
        draft(m.from_user.id,{});clear_broadcast(m.from_user.id);home(m.from_user.id)
        return ContinueHandling()
    @bot.callback_query_handler(func=lambda q:bool(q.data and q.data.startswith('ops:')))
    def owner_tools_action(q):
        if not private(q):bot.answer_callback_query(q.id,'Private chat only',show_alert=True);return
        uid=q.from_user.id
        try:
            _,latest,_=owner_dashboard._load_panel_state(uid)
            if not latest or latest!=q.message.message_id:raise ValueError('Menu ဟောင်းပါ။ /ownertools သို့မဟုတ် /staff နဲ့ ပြန်ဖွင့်ပါ။')
            parts=q.data.split(':');action=parts[1]
            permission='announce' if action in ('announce','target','targets','cancel','schedules','confirm','sendnow','confirmnow') else 'stats' if action=='stats' else None
            if action=='home':
                if not (is_owner(uid) or any(can(uid,p) for p in PERMISSIONS)):raise ValueError('Permission မရှိပါ။')
            elif not permitted(q,permission):raise ValueError('Permission မရှိပါ။')
            clear_broadcast(uid)
            # Starting another action cancels pending text input, but confirmation retains its source.
            current=draft(uid)
            if action not in ('target','targets','confirm','sendnow','confirmnow'):draft(uid,{})
            if action=='home':home(uid)
            elif action in ('tests','leavegroups'):group_list(uid,action,int(parts[2]))
            elif action=='test':
                cid=int(parts[2]);enabled=parts[3]=='1';page=max(0,int(parts[4])) if len(parts)>4 else 0
                test_group(uid,cid,enabled)
                if enabled:selected_card(uid,cid,page)
                else:group_list(uid,'tests',page,'✅ Group ကို စမ်းသပ်စာရင်းမှ ဖယ်ပြီးပါပြီ။')
            elif action=='features':game_list(uid,int(parts[2]) if len(parts)>2 else 0)
            elif action=='feature':game_list(uid)
            elif action=='game':game_card(uid,parts[2])
            elif action=='mode':
                kind=parts[2];rollout=parts[3]
                if kind not in GAME_LABELS:raise ValueError('Game မရှိပါ။')
                change_release(uid,'game:'+kind,rollout)
                notice='✅ ရွေးထားတဲ့ Group မှာပဲ ဒီ Game ကို စမ်းနိုင်ပါပြီ။' if rollout=='test' else '✅ Group အားလုံးမှာ ဒီ Game ကို ဖွင့်ပေးပြီးပါပြီ။'
                game_card(uid,kind,notice)
            elif action=='release':game_list(uid)
            elif action=='leave':
                cid=int(parts[2]);destinations(str(cid));title=dict(groups()).get(cid,str(cid))
                card(uid,f'🚪 {title}\n{cid}\n\nဒီ Group ကနေ Bot ထွက်ခိုင်းမှာလား။',[('✅ Confirm Leave',f'ops:leaveyes:{cid}'),('❌ Cancel','ops:home')])
            elif action=='leaveyes':leave_group(uid,int(parts[2]),bot);home(uid)
            elif action=='assistants':
                with get_db_connection() as conn,conn.cursor() as cur:cur.execute('SELECT user_id,permissions FROM owner_assistants ORDER BY user_id');entries=cur.fetchall()
                text='👥 Assistants\n\n'+'\n'.join(f'{i}: {", ".join(p)}' for i,p in entries)+'\n\nUser ID နဲ့ permissions ပို့ပါ။\nဥပမာ 123456789 edit announce\nပြန်ပိတ်ရန် 123456789 revoke\nPermissions: edit / announce / stats'
                draft(uid,{'phase':'assistant'});card(uid,text[:3500],[('❌ Cancel','ops:home')])
            elif action=='announce':
                draft(uid,{'phase':'source','token':secrets.token_hex(20)})
                card(uid,'📅 အချိန်သတ်မှတ်ပို့ချင်တဲ့ စာ၊ ပုံ၊ video ကို ဒီမှာပို့ပါ။ Forward လုပ်လည်းရပါတယ်။',[('❌ Cancel','ops:home')])
            elif action=='targets':
                if not current or current.get('phase')!='target':raise ValueError('Draft သက်တမ်းကုန်ပါပြီ။')
                targets(uid,max(0,int(parts[2])))
            elif action=='target':
                if not current or current.get('phase')!='target':raise ValueError('Draft သက်တမ်းကုန်ပါပြီ။')
                target=parts[2];destinations(target);current.update(target=target,phase='time');draft(uid,current)
                card(uid,'⏰ Myanmar time နဲ့ အချိန်ရေးပို့ပါ။\nYYYY-MM-DD HH:MM\nဥပမာ 2026-10-12 09:00\n\nချက်ချင်းပို့ချင်ရင် Now ကိုနှိပ်ပါ။',[('📨 Send Now','ops:sendnow'),('❌ Cancel','ops:home')])
            elif action in ('confirm','sendnow'):
                expected='confirm' if action=='confirm' else 'time'
                if not current or current.get('phase')!=expected:raise ValueError('Draft သက်တမ်းကုန်ပါပြီ။')
                if action=='sendnow':
                    current['phase']='now_confirm';draft(uid,current)
                    card(uid,'ဒီ Message ကို ရွေးထားတဲ့ destination ဆီ အခုပို့မှာလား။',[('✅ Confirm Send','ops:confirmnow'),('❌ Cancel','ops:home')])
                else:
                    sid=create_schedule(uid,current['target'],datetime.fromisoformat(current['when']),source_chat=current['source_chat'],source_msg=current['source_msg'],request_id=current['token'])
                    draft(uid,{});card(uid,f'✅ Schedule #{sid} သိမ်းပြီးပြီ။\nMyanmar time: {datetime.fromisoformat(current["when"]).astimezone(MMT):%Y-%m-%d %H:%M}',[('📜 Schedules','ops:schedules'),('⬅️ Back','ops:home')])
            elif action=='confirmnow':
                if not can(uid,'announce') or not current or current.get('phase')!='now_confirm':raise ValueError('Permission / Draft မရှိပါ။')
                jid=owner_dashboard._queue_broadcast('[Telegram original]',destinations(current['target']),current['source_chat'],current['source_msg'],current['token'])
                draft(uid,{});threading.Thread(target=owner_dashboard._send_broadcast,args=(jid,),daemon=True).start();card(uid,f'✅ Broadcast #{jid} ပို့နေပြီ။',[('⬅️ Back','ops:home')])
            elif action=='cancel':cancel_schedule(uid,parts[2]);schedules(uid)
            elif action=='schedules':schedules(uid)
            elif action=='stats':
                activity,games,left=stats();lines=['📊 Usage · Last 30 days','Counts start from this update.','\nGroups (messages / commands / games):']
                lines += [f'{title or cid}: {m} / {c} / {g}' for title,cid,m,c,g in activity[:10]]
                lines += ['\nGame starts:']+[f'{name}: {n}' for name,n in games]+['\nLeft groups:']+[f'{title or cid} · {when.astimezone(MMT):%m-%d %H:%M}' for title,cid,when in left[:5]]
                card(uid,'\n'.join(lines)[:3500],[('⬅️ Back','ops:home')])
            bot.answer_callback_query(q.id)
        except (ValueError,IndexError,KeyError) as exc:bot.answer_callback_query(q.id,str(exc)[:180],show_alert=True)
        except Exception as exc:
            print('Owner tools:',type(exc).__name__);bot.answer_callback_query(q.id,'ခေတ္တ အဆင်မပြေပါ။',show_alert=True)
    @bot.message_handler(func=lambda m:m.chat.type=='private',content_types=['text','photo','video','animation','document','audio','voice','sticker','video_note'])
    def owner_tools_input(m):
        if not private(m):return ContinueHandling()
        uid=m.from_user.id
        if not (is_owner(uid) or can(uid,'announce')):return ContinueHandling()
        if (getattr(m,'text',None) or '').lstrip().startswith('/'):return ContinueHandling()
        try:
            current=draft(uid)
            if not current:return ContinueHandling()
            phase=current.get('phase')
            if phase=='assistant':
                if not is_owner(uid):raise ValueError('Owner only')
                parts=(m.text or '').split();set_assistant(uid,int(parts[0]),[] if parts[1:]==['revoke'] else parts[1:]);draft(uid,{});home(uid)
            elif phase=='source':
                if not can(uid,'announce'):raise ValueError('Permission မရှိပါ။')
                current.update(phase='target',source_chat=m.chat.id,source_msg=m.message_id);draft(uid,current)
                targets(uid)
            elif phase=='time':
                when=parse_when(m.text or '');current.update(phase='confirm',when=when.isoformat());draft(uid,current)
                card(uid,f'📅 {when.astimezone(MMT):%Y-%m-%d %H:%M} Myanmar time\nDestination: {current["target"]}\n\nသိမ်းပြီး schedule လုပ်မှာလား။',[('✅ Confirm Schedule','ops:confirm'),('❌ Cancel','ops:home')])
            else:return ContinueHandling()
        except (ValueError,IndexError,TypeError) as exc:bot.reply_to(m,'⚠️ '+str(exc)[:300])
        except Exception as exc:print('Owner tools input:',type(exc).__name__);bot.reply_to(m,'⚠️ ခေတ္တ အဆင်မပြေပါ။')
        return ContinueHandling()
