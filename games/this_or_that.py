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
            picks=rng.sample(available,ROUNDS)
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
