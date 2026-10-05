"""Atomic Neon persistence for daily group missions and player claims."""
from datetime import datetime, timezone, timedelta
from database.db import get_db_connection
from database.players import player_stats, player_stats_lock

MMT = timezone(timedelta(hours=6, minutes=30))

def today():
    return datetime.now(MMT).date()

def initialize_daily_challenge():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS daily_group_activity (
              chat_id BIGINT NOT NULL, day DATE NOT NULL, user_id BIGINT NOT NULL,
              messages INTEGER NOT NULL DEFAULT 0, last_text TEXT NOT NULL DEFAULT '',
              last_at TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01',
              PRIMARY KEY(chat_id,day,user_id))''')
            cur.execute('''CREATE TABLE IF NOT EXISTS daily_claims (
              chat_id BIGINT NOT NULL, day DATE NOT NULL, user_id BIGINT NOT NULL,
              mission INTEGER NOT NULL, points INTEGER NOT NULL,
              claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY(chat_id,day,user_id,mission))''')
            cur.execute('''CREATE TABLE IF NOT EXISTS daily_cards (
              chat_id BIGINT NOT NULL, day DATE NOT NULL, message_id BIGINT NOT NULL,
              PRIMARY KEY(chat_id,day))''')
            cur.execute('''CREATE TABLE IF NOT EXISTS daily_groups (
              chat_id BIGINT PRIMARY KEY, last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
            cur.execute('''CREATE TABLE IF NOT EXISTS daily_game_events (
                chat_id BIGINT NOT NULL, day DATE NOT NULL, user_id BIGINT NOT NULL,
                event_id TEXT NOT NULL, kind TEXT NOT NULL, game TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(chat_id,day,event_id,user_id))''')
            cur.execute('''CREATE INDEX IF NOT EXISTS daily_game_event_lookup
                ON daily_game_events(chat_id,day,kind,user_id)''')
            cur.execute("""CREATE TABLE IF NOT EXISTS daily_personal_missions (
                chat_id BIGINT NOT NULL, cycle_day DATE NOT NULL, user_id BIGINT NOT NULL,
                mission INTEGER NOT NULL, kind TEXT NOT NULL, game TEXT NOT NULL DEFAULT '',
                needed INTEGER NOT NULL, lo INTEGER NOT NULL, hi INTEGER NOT NULL,
                PRIMARY KEY(chat_id,cycle_day,user_id,mission))""")
            cur.execute("""CREATE TABLE IF NOT EXISTS daily_personal_claims (
                chat_id BIGINT NOT NULL, cycle_day DATE NOT NULL, user_id BIGINT NOT NULL,
                mission INTEGER NOT NULL, points INTEGER NOT NULL,
                claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(chat_id,cycle_day,user_id,mission))""")
    return True

def register_group(chat_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO daily_groups(chat_id,last_seen) VALUES(%s,NOW())
              ON CONFLICT(chat_id) DO UPDATE SET last_seen=NOW()''',(chat_id,))

def active_groups():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_id FROM daily_groups WHERE last_seen>NOW()-INTERVAL '30 days'")
            return [r[0] for r in cur.fetchall()]

def previous_card(chat_id, day):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT message_id FROM daily_cards WHERE chat_id=%s AND day<%s ORDER BY day DESC LIMIT 1",(chat_id,day))
            r=cur.fetchone()
            return r[0] if r else None

def record_message(chat_id,user_id,text,now=None):
    """Count at most one distinct meaningful text per user per 15s, up to 12/day."""
    from datetime import datetime
    now = now or datetime.now(timezone.utc)
    normalized=' '.join(str(text or '').casefold().split())[:250]
    if len(normalized)<4 or normalized.startswith('/') or len(set(normalized))<3:
        return False
    day=active_cycle(chat_id)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO daily_group_activity
                (chat_id,day,user_id,messages,last_text,last_at) VALUES (%s,%s,%s,1,%s,%s)
                ON CONFLICT (chat_id,day,user_id) DO UPDATE SET
                  messages=daily_group_activity.messages+1,
                  last_text=EXCLUDED.last_text,last_at=EXCLUDED.last_at
                WHERE daily_group_activity.messages<12
                  AND daily_group_activity.last_text<>EXCLUDED.last_text
                  AND daily_group_activity.last_at<=EXCLUDED.last_at-INTERVAL '15 seconds'
                RETURNING messages''',(chat_id,day,user_id,normalized,now))
            return cur.fetchone() is not None

def record_game_event(chat_id, user_id, game, kind, event_id):
    """Persist meaningful results once. Cap same-kind events per member/day."""
    if kind not in ('win', 'play', 'correct') or not event_id:
        return False
    day = active_cycle(chat_id)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM daily_game_events WHERE chat_id=%s AND day=%s AND user_id=%s AND kind=%s',
                        (chat_id, day, user_id, kind))
            if cur.fetchone()[0] >= 12:
                return False
            cur.execute("""INSERT INTO daily_game_events(chat_id,day,user_id,event_id,kind,game)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_id""",
                (chat_id, day, user_id, str(event_id),kind,str(game)))
            return cur.fetchone() is not None


def game_progress(chat_id, day, kind, user_id=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*), COUNT(DISTINCT user_id) FROM daily_game_events
                WHERE chat_id=%s AND day=%s AND kind=%s""",(chat_id,day,kind))
            total, users = cur.fetchone()
            mine=0
            if user_id is not None:
                cur.execute("""SELECT COUNT(*) FROM daily_game_events WHERE chat_id=%s AND day=%s
                    AND kind=%s AND user_id=%s""",(chat_id,day,kind,user_id))
                mine=cur.fetchone()[0]
    return int(total),int(users),int(mine)

def overview(chat_id,user_id=None,day=None):
    day=day or today()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT COALESCE(SUM(messages),0),
                COUNT(*) FILTER (WHERE messages>0), COUNT(*) FILTER (WHERE messages>=3),
                COUNT(*) FILTER (WHERE messages>=5)
                FROM daily_group_activity WHERE chat_id=%s AND day=%s''',(chat_id,day))
            total,users,users3,users5=cur.fetchone()
            cur.execute('''SELECT user_id,messages FROM daily_group_activity
                WHERE chat_id=%s AND day=%s ORDER BY messages DESC,user_id LIMIT 3''',(chat_id,day))
            top=cur.fetchall()
            mine=0; claimed=set()
            if user_id is not None:
                cur.execute('''SELECT messages FROM daily_group_activity
                    WHERE chat_id=%s AND day=%s AND user_id=%s''',(chat_id,day,user_id))
                r=cur.fetchone(); mine=r[0] if r else 0
                cur.execute('''SELECT mission FROM daily_claims
                    WHERE chat_id=%s AND day=%s AND user_id=%s''',(chat_id,day,user_id))
                claimed={r[0] for r in cur.fetchall()}
    return {'day':day,'total':total,'users':users,'users3':users3,'users5':users5,
            'top':top,'mine':mine,'claimed':claimed}

# Three tiers, each with 4 feasible variants. Stable per group/day.
MISSION_POOL = (
    ((6,2,1,(3,8)),(8,2,2,(3,8)),(10,2,2,(3,8)),(7,3,1,(3,8))),
    ((15,3,3,(8,15)),(18,3,3,(8,15)),(20,3,4,(8,15)),(16,4,2,(8,15))),
    ((30,4,5,(15,25)),(35,4,5,(15,25)),(32,5,4,(15,25)),(36,4,6,(15,25))),
)
MISSIONS=tuple(pool[0] for pool in MISSION_POOL)  # compatibility

# Pool entries: (kind, group events, distinct members, personal events, rewards).
# Tier 1 remains accessible through messaging; upper tiers rotate among activity,
# wins, and correct game answers. Stable selection for a group/day.
GAME_MISSION_POOL = (
    [('message',*m) for m in MISSION_POOL[0]],
    [('message',*m) for m in MISSION_POOL[1]] +
    [('play',4,2,1,(8,15)),('correct',4,2,1,(8,15)),('win',2,2,1,(8,15))],
    [('message',*m) for m in MISSION_POOL[2]] +
    [('play',9,3,2,(15,25)),('correct',7,3,2,(15,25)),('win',4,2,1,(15,25))],
)

def missions_for(chat_id,day=None):
    import hashlib
    day=day or today()
    return tuple(pool[int(hashlib.sha256(f'{chat_id}:{day}:{tier}:mission'.encode()).hexdigest(),16)%len(pool)]
                 for tier,pool in enumerate(GAME_MISSION_POOL))

def mission_state(chat_id,user_id, mission,day=None):
    day=day or today()
    kind,required,unique,personal,_=mission
    if kind=='message':
        snap=overview(chat_id,user_id,day)
        return snap['total'],snap['users'],snap['mine']
    return game_progress(chat_id,day,kind,user_id)


def claim(chat_id,user_id,mission,day=None):
    """Single DB transaction: progress check + unique claim + award. No double claims on restart."""
    import random, hashlib
    day=day or today()
    if mission not in (1,2,3): return 'invalid',0
    kind,total_needed,users_needed,personal_needed,reward=missions_for(chat_id,day)[mission-1]
    double=int(hashlib.sha256(f'{chat_id}:{day}:double'.encode()).hexdigest(),16)%7==0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Serialize concurrent claims by the same user on a given day.
            cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',(int(chat_id)%2147483647,int(user_id)%2147483647))
            if kind=='message':
                cur.execute("""SELECT COALESCE(SUM(messages),0),COUNT(*)
                    FROM daily_group_activity WHERE chat_id=%s AND day=%s""",(chat_id,day))
                total,users=cur.fetchone()
                cur.execute("""SELECT messages FROM daily_group_activity WHERE chat_id=%s AND day=%s AND user_id=%s""",(chat_id,day,user_id))
                row=cur.fetchone();mine=row[0] if row else 0
            else:
                cur.execute("""SELECT COUNT(*),COUNT(DISTINCT user_id) FROM daily_game_events
                    WHERE chat_id=%s AND day=%s AND kind=%s""",(chat_id,day,kind))
                total,users=cur.fetchone()
                cur.execute("""SELECT COUNT(*) FROM daily_game_events WHERE chat_id=%s AND day=%s
                    AND kind=%s AND user_id=%s""",(chat_id,day,kind,user_id))
                mine=cur.fetchone()[0]
            if total<total_needed or users<users_needed or mine<personal_needed:
                return 'locked',0
            pts=random.randint(*reward)*(2 if double else 1)
            cur.execute('''INSERT INTO daily_claims(chat_id,day,user_id,mission,points)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING points''',
                (chat_id,day,user_id,mission,pts))
            if not cur.fetchone():return 'claimed',0
            cur.execute('''INSERT INTO player_stats (chat_id,user_id,points,games,wins,losses,draws)
                VALUES (%s,%s,%s,0,0,0,0) ON CONFLICT(chat_id,user_id)
                DO UPDATE SET points=GREATEST(0,player_stats.points+EXCLUDED.points)
                RETURNING points,games,wins,losses,draws''',(chat_id,user_id,pts))
            stats=cur.fetchone()
            # Ledger belongs to same transaction as claim and points.
            cur.execute('''INSERT INTO reward_transactions(chat_id,user_id,points,reason)
                VALUES (%s,%s,%s,%s)''',(chat_id,user_id,pts,f'daily_{day}_mission_{mission}'))
    with player_stats_lock:
        player_stats[(chat_id,user_id)]=dict(zip(('points','games','wins','losses','draws'),stats))
    return 'ok',pts

def get_card_id(chat_id,day=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT message_id FROM daily_cards WHERE chat_id=%s AND day=%s',(chat_id,day or today()))
            row=cur.fetchone();return row[0] if row else None

def set_card_id(chat_id,message_id,day=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO daily_cards(chat_id,day,message_id) VALUES(%s,%s,%s)
              ON CONFLICT(chat_id,day) DO UPDATE SET message_id=EXCLUDED.message_id''',
              (chat_id,day or today(),message_id))

# The cycle changes when the NEW MAIN CARD is published, not on /daily or at midnight.
def active_cycle(chat_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT MAX(day) FROM daily_cards WHERE chat_id=%s',(chat_id,))
            r=cur.fetchone()
            return r[0] if r and r[0] is not None else today()

# Three independent personal missions, stable per member and main-card cycle.
# Only use events actually emitted by bot.py; other games can join this pool later.
PERSONAL_POOL = (
    [('message','',2),('play','',1),('correct','',1),('win','',1)],
    [('message','',4),('play','',3),('correct','',2),('win','',2),
     ('correct','math_battle',2),('correct','word_chain',2)],
    [('message','',6),('play','',5),('correct','',4),('win','',3),
     ('correct','math_battle',4),('correct','word_chain',4)],
)
PERSONAL_REWARDS=((3,8),(8,15),(15,25))
PERSONAL_DESCRIPTIONS={
    ('message',''):'Send {n} different meaningful group messages',
    ('play',''):'Participate in {n} group game actions',
    ('correct',''):'Get {n} correct game answers',
    ('win',''):'Win {n} mini-games',
    ('correct','math_battle'):'Get {n} Math Battle answers correct',
    ('correct','word_chain'):'Submit {n} correct Word Chain words',
}

def personal_missions(chat_id,user_id,day=None):
    import hashlib
    day=day or active_cycle(chat_id)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for tier,pool in enumerate(PERSONAL_POOL,1):
                seed=f'personal:{chat_id}:{user_id}:{day}:{tier}'.encode()
                k=int.from_bytes(hashlib.sha256(seed).digest()[:8],'big')%len(pool)
                kind,game,needed=pool[k]
                lo,hi=PERSONAL_REWARDS[tier-1]
                cur.execute('''INSERT INTO daily_personal_missions
                    (chat_id,cycle_day,user_id,mission,kind,game,needed,lo,hi)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                    (chat_id,day,user_id,tier,kind,game,needed,lo,hi))
            cur.execute('''SELECT mission,kind,game,needed,lo,hi FROM daily_personal_missions
                WHERE chat_id=%s AND cycle_day=%s AND user_id=%s ORDER BY mission''',
                (chat_id,day,user_id))
            return cur.fetchall()

def personal_progress(chat_id,user_id,mission,day=None):
    day=day or active_cycle(chat_id)
    _,kind,game,needed,lo,hi=mission
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if kind=='message':
                cur.execute('''SELECT COALESCE(messages,0) FROM daily_group_activity
                    WHERE chat_id=%s AND day=%s AND user_id=%s''',(chat_id,day,user_id))
            else:
                cur.execute('''SELECT COUNT(*) FROM daily_game_events WHERE chat_id=%s
                    AND day=%s AND user_id=%s AND kind=%s AND (%s='' OR game=%s)''',
                    (chat_id,day,user_id,kind,game,game))
            r=cur.fetchone()
            return int(r[0]) if r else 0

def personal_overview(chat_id,user_id):
    day=active_cycle(chat_id)
    missions=personal_missions(chat_id,user_id,day)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT mission FROM daily_personal_claims
                WHERE chat_id=%s AND cycle_day=%s AND user_id=%s''',(chat_id,day,user_id))
            claimed={x[0] for x in cur.fetchall()}
    return {'day':day,'chat_id':chat_id,'viewer_id':user_id,'personal':True,
            'missions':[(m,personal_progress(chat_id,user_id,m,day)) for m in missions],
            'claimed':claimed}

def personal_claim(chat_id,user_id,index):
    import random,hashlib
    if index not in (1,2,3):return 'invalid',0
    day=active_cycle(chat_id)
    missions=personal_missions(chat_id,user_id,day)
    chosen=next((m for m in missions if m[0]==index),None)
    if chosen is None:return 'invalid',0
    if personal_progress(chat_id,user_id,chosen,day)<chosen[3]:return 'locked',0
    double=int(hashlib.sha256(f'{chat_id}:{day}:double'.encode()).hexdigest(),16)%7==0
    pts=random.randint(chosen[4],chosen[5])*(2 if double else 1)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',(int(chat_id)%2147483647,int(user_id)%2147483647))
            cur.execute('''INSERT INTO daily_personal_claims(chat_id,cycle_day,user_id,mission,points)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING points''',
                (chat_id,day,user_id,index,pts))
            if not cur.fetchone():return 'claimed',0
            cur.execute('''INSERT INTO player_stats(chat_id,user_id,points,games,wins,losses,draws)
                VALUES(%s,%s,%s,0,0,0,0) ON CONFLICT(chat_id,user_id)
                DO UPDATE SET points=GREATEST(0,player_stats.points+EXCLUDED.points)
                RETURNING points,games,wins,losses,draws''',(chat_id,user_id,pts))
            stats=cur.fetchone()
            cur.execute('''INSERT INTO reward_transactions(chat_id,user_id,points,reason)
                VALUES(%s,%s,%s,%s)''',(chat_id,user_id,pts,f'daily_personal_{day}_mission_{index}'))
    with player_stats_lock:
        player_stats[(chat_id,user_id)]=dict(zip(('points','games','wins','losses','draws'),stats))
    return 'ok',pts
