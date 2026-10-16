"""Persistent group-member registry for known-member mentions.

Telegram Bot API does not expose a complete group member directory or online status.
This registry stores non-bot users the bot actually sees in messages/joins/replies.
"""
from database.db import get_db_connection
from core.batched_writes import BatchWriter
from datetime import datetime,timezone

_MEMBERS=BatchWriter("""INSERT INTO group_member_registry(chat_id,user_id,username,first_name,last_name,first_seen,last_seen)
VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(chat_id,user_id) DO UPDATE SET username=EXCLUDED.username,first_name=EXCLUDED.first_name,last_name=EXCLUDED.last_name,last_seen=EXCLUDED.last_seen""")


def initialize_member_registry():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS group_member_registry (
                    chat_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (chat_id, user_id)
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_group_member_registry_chat_last_seen
                ON group_member_registry (chat_id, last_seen DESC)
                """
            )
    return True


def remember_member(chat_id, user_id, username=None, first_name=None, last_name=None):
    if not chat_id or not user_id:
        return False
    now=datetime.now(timezone.utc)
    return _MEMBERS.submit((chat_id,user_id),(chat_id,user_id,username,first_name,last_name,now,now))


def get_known_member_ids(chat_id, limit=5000):
    _MEMBERS.flush()
    limit = max(1, min(int(limit), 10000))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id
                FROM group_member_registry
                WHERE chat_id = %s
                ORDER BY last_seen DESC, user_id ASC
                LIMIT %s
                """,
                (chat_id, limit),
            )
            known=[row[0] for row in cur.fetchall()]
    # Include activity still pending during a transient database write failure.
    pending=[row[1] for row in reversed(_MEMBERS.snapshot()) if row[0]==chat_id]
    return list(dict.fromkeys(pending+known))[:limit]
