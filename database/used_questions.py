# =========================================================
# 🧠 USED QUESTION TRACKING
# =========================================================

from database.db import (
    DATABASE_URL,
    get_db_connection,
)


# =========================================================
# 🗄️ INIT TABLE
# =========================================================

def init_used_questions_db():

    if not DATABASE_URL:
        return False

    try:

        with get_db_connection() as conn:

            with conn.cursor() as cur:

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS used_questions (

                        chat_id BIGINT NOT NULL,

                        game_type TEXT NOT NULL,

                        question_id TEXT NOT NULL,

                        used_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),

                        PRIMARY KEY (
                            chat_id,
                            game_type,
                            question_id
                        )
                    )
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_used_questions_recent
                    ON used_questions (
                        chat_id,
                        game_type,
                        used_at DESC
                    )
                """)

        print(
            "✅ Used Questions Database Ready"
        )

        return True

    except Exception as e:

        print(
            f"❌ Used Questions DB Init Error: {e}"
        )

        return False


# =========================================================
# ✅ MARK QUESTION AS USED
# =========================================================

def mark_question_used(
    chat_id,
    game_type,
    question_id
):

    try:

        with get_db_connection() as conn:

            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO used_questions (
                        chat_id,
                        game_type,
                        question_id
                    )

                    VALUES (
                        %s,
                        %s,
                        %s
                    )

                    ON CONFLICT (
                        chat_id,
                        game_type,
                        question_id
                    )

                    DO UPDATE SET
                        used_at = NOW()
                """, (
                    chat_id,
                    str(game_type),
                    str(question_id),
                ))

        return True

    except Exception as e:

        print(
            f"❌ Mark Question Used Error: {e}"
        )

        return False


# =========================================================
# 📚 GET ALL USED IDS
# =========================================================

def get_used_question_ids(
    chat_id,
    game_type
):

    try:

        with get_db_connection() as conn:

            with conn.cursor() as cur:

                cur.execute("""
                    SELECT question_id

                    FROM used_questions

                    WHERE
                        chat_id = %s
                        AND game_type = %s
                """, (
                    chat_id,
                    str(game_type),
                ))

                rows = cur.fetchall()

        return {
            str(row[0])
            for row in rows
        }

    except Exception as e:

        print(
            f"❌ Get Used Question IDs Error: {e}"
        )

        return set()


# =========================================================
# 🕘 GET RECENT USED IDS
# =========================================================

def get_recent_question_ids(
    chat_id,
    game_type,
    limit=150
):

    limit = max(
        0,
        int(limit)
    )

    if limit == 0:
        return []

    try:

        with get_db_connection() as conn:

            with conn.cursor() as cur:

                cur.execute("""
                    SELECT question_id

                    FROM used_questions

                    WHERE
                        chat_id = %s
                        AND game_type = %s

                    ORDER BY used_at DESC

                    LIMIT %s
                """, (
                    chat_id,
                    str(game_type),
                    limit,
                ))

                rows = cur.fetchall()

        return [
            str(row[0])
            for row in rows
        ]

    except Exception as e:

        print(
            f"❌ Recent Question IDs Error: {e}"
        )

        return []


# =========================================================
# 🔄 RESET USED QUESTION POOL
#
# Pool အကုန်သုံးပြီးသွားရင် reset လုပ်ရန်။
# =========================================================

def reset_used_questions(
    chat_id,
    game_type
):

    try:

        with get_db_connection() as conn:

            with conn.cursor() as cur:

                cur.execute("""
                    DELETE FROM used_questions

                    WHERE
                        chat_id = %s
                        AND game_type = %s
                """, (
                    chat_id,
                    str(game_type),
                ))

        return True

    except Exception as e:

        print(
            f"❌ Reset Used Questions Error: {e}"
        )

        return False
