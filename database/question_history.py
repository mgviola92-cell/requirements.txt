"""Shared persistent question history across games in a Telegram group."""
import hashlib
from database.db import get_db_connection

_ready = False

def _key(question):
    return hashlib.sha256(" ".join(str(question).casefold().split()).encode()).hexdigest()

def _init():
    global _ready
    if _ready:
        return
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS game_question_history (chat_id BIGINT NOT NULL, question_hash TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY(chat_id, question_hash))")
    _ready = True

def seen(chat_id, question):
    try:
        _init()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM game_question_history WHERE chat_id=%s AND question_hash=%s", (chat_id, _key(question)))
                return cur.fetchone() is not None
    except Exception as exc:
        print("Question history lookup:", exc)
        return False

def mark(chat_id, question):
    try:
        _init()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO game_question_history(chat_id, question_hash) VALUES (%s,%s) ON CONFLICT DO NOTHING", (chat_id, _key(question)))
        return True
    except Exception as exc:
        print("Question history mark:", exc)
        return False


def claim(chat_id, question):
    """Reserve a question once per chat, atomically."""
    try:
        _init()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO game_question_history(chat_id,question_hash) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING question_hash", (chat_id, _key(question)))
                return cur.fetchone() is not None
    except Exception as exc:
        print("Question claim failed:", exc)
        return None
