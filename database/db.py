# =========================================================
# 🗄️ DATABASE CONNECTION
# =========================================================

import os
import psycopg


DATABASE_URL = os.getenv("DATABASE_URL")


def database_available():
    """DATABASE_URL ရှိ/မရှိ စစ်ရန်"""
    return bool(DATABASE_URL)


def get_db_connection():
    """
    Neon PostgreSQL connection အသစ်တစ်ခု ဖွင့်ပေးမည်။

    အသုံးပြုပုံ:
        with get_db_connection() as conn:
            ...
    """

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL မတွေ့ပါ။ "
            "Render Environment Variables ကို စစ်ပါ။"
        )

    return psycopg.connect(
        DATABASE_URL,
        connect_timeout=20
    )


def test_database_connection():
    """
    Database connection အလုပ်လုပ်/မလုပ် စစ်ရန်။
    Bot startup မှာ သုံးနိုင်သည်။
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

        print("✅ Neon Database Connection Ready")
        return True

    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        return False
