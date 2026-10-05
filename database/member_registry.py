"""Persistent group-member registry for known-member mentions.

Telegram Bot API does not expose a complete group member directory or online status.
This registry stores non-bot users the bot actually sees in messages/joins/replies.
"""
from database.db import get_db_connection


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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO group_member_registry
                    (chat_id, user_id, username, first_name, last_name, first_seen, last_seen)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (chat_id, user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_seen = NOW()
                """,
                (chat_id, user_id, username, first_name, last_name),
            )
    return True


def get_known_member_ids(chat_id, limit=5000):
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
            return [row[0] for row in cur.fetchall()]
