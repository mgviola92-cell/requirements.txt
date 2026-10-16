# =========================================================
# 🗄️ DATABASE CONNECTION
# =========================================================

import os
import psycopg
import atexit
import threading
from psycopg_pool import ConnectionPool

_pool = None
_pool_lock = threading.Lock()


DATABASE_URL = os.getenv("DATABASE_URL")


def database_available():
    """DATABASE_URL ရှိ/မရှိ စစ်ရန်"""
    return bool(DATABASE_URL)


def get_db_connection():
    """
    Shared pool မှ Neon PostgreSQL connection ကို ခဏငှားပေးမည်။

    အသုံးပြုပုံ:
        with get_db_connection() as conn:
            ...
    """

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL မတွေ့ပါ။ "
            "Render Environment Variables ကို စစ်ပါ။"
        )

    global _pool
    with _pool_lock:
        if _pool is None:
            pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=12,
                                  timeout=20, max_idle=300, max_lifetime=1800,
                                  kwargs={'connect_timeout':20}, open=False)
            pool.open()
            _pool = pool
            atexit.register(pool.close)
    # Commit on success / rollback on failure, then return to the shared pool.
    return _pool.connection()



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
