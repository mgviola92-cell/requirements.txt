# =========================================================
# 👤 PLAYER STATS DATABASE
# =========================================================

import threading

from database.db import DATABASE_URL, get_db_connection


player_stats = {}
player_stats_lock = threading.RLock()


# =========================================================
# 🗄️ INIT PLAYER STATS TABLE
# =========================================================

def init_player_stats_db():
    if not DATABASE_URL:
        print(
            "❌ DATABASE_URL မတွေ့ပါ။ "
            "Render Environment မှာ ထည့်ပါ။"
        )
        return False

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS player_stats (
                        chat_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,

                        points INTEGER NOT NULL DEFAULT 0,
                        games INTEGER NOT NULL DEFAULT 0,

                        wins INTEGER NOT NULL DEFAULT 0,
                        losses INTEGER NOT NULL DEFAULT 0,
                        draws INTEGER NOT NULL DEFAULT 0,

                        PRIMARY KEY (
                            chat_id,
                            user_id
                        )
                    )
                """)

        print("✅ Player Stats Database Ready")
        return True

    except Exception as e:
        print(f"❌ Player Stats DB Init Error: {e}")
        return False


# =========================================================
# 📥 LOAD DATABASE → RAM
# =========================================================

def load_player_stats():
    if not DATABASE_URL:
        return

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        chat_id,
                        user_id,
                        points,
                        games,
                        wins,
                        losses,
                        draws
                    FROM player_stats
                """)

                rows = cur.fetchall()

        with player_stats_lock:
            player_stats.clear()

            for row in rows:
                (
                    chat_id,
                    user_id,
                    points,
                    games,
                    wins,
                    losses,
                    draws
                ) = row

                player_stats[(chat_id, user_id)] = {
                    "points": max(0, points),
                    "games": games,
                    "wins": wins,
                    "losses": losses,
                    "draws": draws
                }

        print(
            f"✅ Player Stats Loaded: "
            f"{len(rows)} players"
        )

    except Exception as e:
        print(f"❌ Player Stats Load Error: {e}")


# =========================================================
# 👤 GET PLAYER STATS
# =========================================================

def get_player_stats(chat_id, user_id):
    key = (chat_id, user_id)

    with player_stats_lock:
        if key not in player_stats:
            player_stats[key] = {
                "points": 0,
                "games": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0
            }

        return player_stats[key]


# =========================================================
# 🎮 ADD GAME RESULT
# =========================================================

def add_game_result(
    chat_id,
    user_id,
    result,
    points=0
):
    if result not in [
        "win",
        "loss",
        "draw"
    ]:
        print(f"❌ Invalid Game Result: {result}")
        return False

    if not DATABASE_URL:
        print(
            "❌ Points မသိမ်းနိုင်ပါ။ "
            "DATABASE_URL မရှိပါ။"
        )
        return False

    add_win = 1 if result == "win" else 0
    add_loss = 1 if result == "loss" else 0
    add_draw = 1 if result == "draw" else 0

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO player_stats (
                        chat_id,
                        user_id,

                        points,
                        games,

                        wins,
                        losses,
                        draws
                    )

                    VALUES (
                        %s,
                        %s,

                        GREATEST(0, %s),
                        1,

                        %s,
                        %s,
                        %s
                    )

                    ON CONFLICT (
                        chat_id,
                        user_id
                    )

                    DO UPDATE SET

                        points = GREATEST(
                            0,
                            player_stats.points
                            + EXCLUDED.points
                        ),

                        games =
                            player_stats.games
                            + EXCLUDED.games,

                        wins =
                            player_stats.wins
                            + EXCLUDED.wins,

                        losses =
                            player_stats.losses
                            + EXCLUDED.losses,

                        draws =
                            player_stats.draws
                            + EXCLUDED.draws

                    RETURNING
                        points,
                        games,
                        wins,
                        losses,
                        draws
                """, (
                    chat_id,
                    user_id,
                    points,
                    add_win,
                    add_loss,
                    add_draw
                ))

                row = cur.fetchone()

        with player_stats_lock:
            player_stats[(chat_id, user_id)] = {
                "points": row[0],
                "games": row[1],
                "wins": row[2],
                "losses": row[3],
                "draws": row[4]
            }

        return True

    except Exception as e:
        print(f"❌ Player Stats Save Error: {e}")
        return False


# =========================================================
# 🚀 STARTUP HELPER
# =========================================================

def initialize_player_stats():
    player_ready = init_player_stats_db()
    reward_ready = init_reward_transactions_db()

    if player_ready:
        load_player_stats()

    return player_ready and reward_ready

# =========================================================
# ⭐ ADD BONUS POINTS
#
# Achievement / Daily Challenge / Event / Lucky Drop
# စတဲ့ non-game rewards အတွက်
#
# games / wins / losses / draws မတိုးပါ
# =========================================================

def add_bonus_points(
    chat_id,
    user_id,
    points
):
    if not DATABASE_URL:
        print(
            "❌ Bonus Points မသိမ်းနိုင်ပါ။ "
            "DATABASE_URL မရှိပါ။"
        )
        return False

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO player_stats (
                        chat_id,
                        user_id,
                        points,
                        games,
                        wins,
                        losses,
                        draws
                    )

                    VALUES (
                        %s,
                        %s,
                        GREATEST(0, %s),
                        0,
                        0,
                        0,
                        0
                    )

                    ON CONFLICT (
                        chat_id,
                        user_id
                    )

                    DO UPDATE SET
                        points = GREATEST(
                            0,
                            player_stats.points
                            + EXCLUDED.points
                        )

                    RETURNING
                        points,
                        games,
                        wins,
                        losses,
                        draws
                """, (
                    chat_id,
                    user_id,
                    points
                ))

                row = cur.fetchone()

        with player_stats_lock:
            player_stats[(chat_id, user_id)] = {
                "points": row[0],
                "games": row[1],
                "wins": row[2],
                "losses": row[3],
                "draws": row[4]
            }

        log_reward_transaction(
    chat_id,
    user_id,
    points,
    reason="bonus"
)
        
        return True

    except Exception as e:
        print(
            f"❌ Bonus Point Save Error: {e}"
        )
        return False

# =========================================================
# 🧾 REWARD TRANSACTIONS TABLE
# =========================================================

def init_reward_transactions_db():
    if not DATABASE_URL:
        return False

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS reward_transactions (
                        id BIGSERIAL PRIMARY KEY,

                        chat_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,

                        points INTEGER NOT NULL,
                        reason TEXT,

                        created_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                    )
                """)

        print("✅ Reward Transactions Database Ready")
        return True

    except Exception as e:
        print(
            f"❌ Reward Transactions DB Init Error: {e}"
        )
        return False


def log_reward_transaction(
    chat_id,
    user_id,
    points,
    reason=None
):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reward_transactions (
                        chat_id,
                        user_id,
                        points,
                        reason
                    )

                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                """, (
                    chat_id,
                    user_id,
                    int(points),
                    reason
                ))

        log_reward_transaction(
    chat_id,
    user_id,
    points,
    reason="bonus"
)
        
        return True

    except Exception as e:
        print(
            f"❌ Reward Transaction Log Error: {e}"
        )
        return False
