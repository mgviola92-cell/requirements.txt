"""Five-round, restart-safe This or That persistence."""
import random
import uuid
from datetime import datetime, timedelta, timezone
from database.db import get_db_connection
from data.this_or_that_questions import TOTAL_QUESTIONS, get_question

ROUNDS = 5
VOTE_SECONDS = (45, 90)

def initialize():
    with get_db_connection() as db:
        with db.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS tot_games (
                chat_id BIGINT PRIMARY KEY, match_id TEXT NOT NULL,
                questions TEXT NOT NULL, round_no INT NOT NULL,
                ends_at TIMESTAMPTZ NOT NULL, status TEXT NOT NULL)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS tot_votes (
                chat_id BIGINT NOT NULL, match_id TEXT NOT NULL,
                round_no INT NOT NULL, user_id BIGINT NOT NULL,
                choice INT NOT NULL CHECK (choice IN (0,1)),
                PRIMARY KEY(chat_id, match_id, round_no, user_id))""")
            cur.execute("""CREATE TABLE IF NOT EXISTS tot_history (
                chat_id BIGINT NOT NULL, question_id TEXT NOT NULL,
                used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(chat_id, question_id))""")

def start(chat_id, rng=None):
    rng=rng or random
    with get_db_connection() as db:
        with db.cursor() as cur:
            cur.execute("SELECT status FROM tot_games WHERE chat_id=%s FOR UPDATE",(chat_id,))
            current=cur.fetchone()
            if current and current[0]=="active":
                return None
            cur.execute("SELECT question_id FROM tot_history WHERE chat_id=%s",(chat_id,))
            used={row[0] for row in cur.fetchall()}
            available=[i for i in range(TOTAL_QUESTIONS) if f"TOT-{i:05d}" not in used]
            if len(available)<ROUNDS:
                cur.execute("DELETE FROM tot_history WHERE chat_id=%s",(chat_id,))
                available=list(range(TOTAL_QUESTIONS))
            # Prefer a different category each round for a more varied match.
            buckets={}
            for ix in available:
                buckets.setdefault(ix//276,[]).append(ix)
            categories=rng.sample(list(buckets),min(ROUNDS,len(buckets)))
            picks=[rng.choice(buckets[category]) for category in categories]
            if len(picks)<ROUNDS:
                extras=[ix for ix in available if ix not in picks]
                picks.extend(rng.sample(extras,ROUNDS-len(picks)))
            for i in picks:
                cur.execute("INSERT INTO tot_history(chat_id,question_id) VALUES(%s,%s)",(chat_id,f"TOT-{i:05d}"))
            mid=uuid.uuid4().hex
            deadline=datetime.now(timezone.utc)+timedelta(seconds=rng.randint(*VOTE_SECONDS))
            cur.execute("""INSERT INTO tot_games(chat_id,match_id,questions,round_no,ends_at,status)
            VALUES(%s,%s,%s,1,%s,'active') ON CONFLICT(chat_id) DO UPDATE SET
            match_id=EXCLUDED.match_id,questions=EXCLUDED.questions,
            round_no=1,ends_at=EXCLUDED.ends_at,status='active'""",
            (chat_id,mid,",".join(map(str,picks)),deadline))
    return {"match_id":mid,"round":1,"question":get_question(picks[0]),"ends_at":deadline}

def snapshot(chat_id):
    with get_db_connection() as db:
        with db.cursor() as cur:
            cur.execute("SELECT match_id,questions,round_no,ends_at,status FROM tot_games WHERE chat_id=%s",(chat_id,))
            row=cur.fetchone()
            if not row:return None
            mid,raw,num,deadline,status=row
            ids=list(map(int,raw.split(",")))
            cur.execute("SELECT choice,COUNT(*) FROM tot_votes WHERE chat_id=%s AND match_id=%s AND round_no=%s GROUP BY choice",(chat_id,mid,num))
            totals=dict(cur.fetchall())
    return {"match_id":mid,"round":num,"ends_at":deadline,"status":status,
            "question":get_question(ids[num-1]),"counts":(totals.get(0,0),totals.get(1,0))}

def vote(chat_id,match_id,round_no,user_id,choice):
    if choice not in (0,1):return False
    with get_db_connection() as db:
        with db.cursor() as cur:
            cur.execute("SELECT match_id,round_no,ends_at,status FROM tot_games WHERE chat_id=%s FOR UPDATE",(chat_id,))
            row=cur.fetchone()
            if not row or row[0]!=match_id or row[1]!=round_no or row[3]!="active" or row[2]<=datetime.now(timezone.utc):
                return False
            cur.execute("""INSERT INTO tot_votes(chat_id,match_id,round_no,user_id,choice)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING user_id""",
                (chat_id,match_id,round_no,user_id,choice))
            return cur.fetchone() is not None

def advance(chat_id,match_id,rng=None):
    rng=rng or random
    with get_db_connection() as db:
        with db.cursor() as cur:
            cur.execute("SELECT match_id,questions,round_no,ends_at,status FROM tot_games WHERE chat_id=%s FOR UPDATE",(chat_id,))
            row=cur.fetchone()
            if not row or row[0]!=match_id or row[4]!="active" or row[3]>datetime.now(timezone.utc):
                return None
            _,raw,num,_,_=row
            ids=list(map(int,raw.split(",")))
            cur.execute("SELECT choice,COUNT(*) FROM tot_votes WHERE chat_id=%s AND match_id=%s AND round_no=%s GROUP BY choice",(chat_id,match_id,num))
            votes=dict(cur.fetchall())
            result={"completed_round":num,"counts":(votes.get(0,0),votes.get(1,0))}
            if num==ROUNDS:
                cur.execute("UPDATE tot_games SET status='finished' WHERE chat_id=%s AND match_id=%s",(chat_id,match_id))
                cur.execute("SELECT DISTINCT user_id FROM tot_votes WHERE chat_id=%s AND match_id=%s",(chat_id,match_id))
                result["participants"]=[row[0] for row in cur.fetchall()]
                result["finished"]=True
            else:
                deadline=datetime.now(timezone.utc)+timedelta(seconds=rng.randint(*VOTE_SECONDS))
                cur.execute("UPDATE tot_games SET round_no=%s,ends_at=%s WHERE chat_id=%s AND match_id=%s",(num+1,deadline,chat_id,match_id))
                result.update({"finished":False,"round":num+1,"ends_at":deadline,"question":get_question(ids[num])})
    return result

def active_games():
    with get_db_connection() as db:
        with db.cursor() as c:
            c.execute("SELECT chat_id,match_id,ends_at FROM tot_games WHERE status='active'")
            return c.fetchall()

def stop(chat_id, match_id):
    with get_db_connection() as db:
        with db.cursor() as c:
            c.execute("UPDATE tot_games SET status='finished' WHERE chat_id=%s AND match_id=%s AND status='active' RETURNING match_id", (chat_id,match_id))
            return c.fetchone() is not None
