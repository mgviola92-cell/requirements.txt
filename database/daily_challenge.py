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
    return True

def record_message(chat_id,user_id,text,now=None):
    """Count at most one distinct meaningful text per user per 15s, up to 12/day."""
    from datetime import datetime
    now = now or datetime.now(timezone.utc)
    normalized=' '.join(str(text or '').casefold().split())[:250]
    if len(normalized)<4 or normalized.startswith('/') or len(set(normalized))<3:
        return False
    day=now.astimezone(MMT).date()
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

MISSIONS=((6,2,1,(3,8)),(15,3,3,(8,15)),(30,4,5,(15,25)))

def claim(chat_id,user_id,mission,day=None):
    """Single DB transaction: progress check + unique claim + award. No double claims on restart."""
    import random, hashlib
    day=day or today()
    if mission not in (1,2,3): return 'invalid',0
    total_needed,users_needed,personal_needed,reward=MISSIONS[mission-1]
    double=int(hashlib.sha256(f'{chat_id}:{day}:double'.encode()).hexdigest(),16)%7==0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Serialize concurrent claims by the same user on a given day.
            cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',(int(chat_id)%2147483647,int(user_id)%2147483647))
            cur.execute('''SELECT COALESCE(SUM(messages),0),COUNT(*)
                FROM daily_group_activity WHERE chat_id=%s AND day=%s''',(chat_id,day))
            total,users=cur.fetchone()
            cur.execute('''SELECT messages FROM daily_group_activity WHERE chat_id=%s AND day=%s AND user_id=%s''',(chat_id,day,user_id))
            row=cur.fetchone();mine=row[0] if row else 0
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
