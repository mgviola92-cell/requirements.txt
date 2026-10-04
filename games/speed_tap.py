# =========================================================
# ⚡ SPEED TAP GAME ENGINE
# =========================================================

import random
import threading
import time


# =========================================================
# ⚙️ SETTINGS
# =========================================================

# /speedtap ခေါ်ပြီးနောက် hidden random start delay
SPEED_TAP_PENDING_MIN = 10
SPEED_TAP_PENDING_MAX = 180

# WAIT card ပေါ်ပြီးနောက် GO မတိုင်ခင်
SPEED_TAP_WAIT_MIN = 3
SPEED_TAP_WAIT_MAX = 8

# GO ပေါ်ပြီးနောက် tap လုပ်နိုင်သည့်အချိန်
SPEED_TAP_ACTIVE_TIME = 10


# =========================================================
# 🔒 ACTIVE GAMES
# =========================================================

_active_speed_tap_games = {}
_speed_tap_lock = threading.RLock()


# =========================================================
# 🌌 CREATE PENDING ROUND
# =========================================================

def create_speed_tap_game(
    chat_id,
    pending_seconds,
):

    now = time.time()

    game = {
        "chat_id": chat_id,
        "state": "pending",
        "created_at": now,
        "pending_seconds": float(pending_seconds),
        "start_at": now + float(pending_seconds),
        "wait_seconds": None,
        "go_at": None,
        "expires_at": None,
        "winner_id": None,
        "winner_name": None,
        "winner_time_ms": None,
        "reward_points": None,
        "jackpot_bonus": 0,
        "pending_message_id": None,
        "message_id": None,
        "finished": False,
    }

    with _speed_tap_lock:

        if chat_id in _active_speed_tap_games:
            return False, _active_speed_tap_games[chat_id].copy()

        _active_speed_tap_games[chat_id] = game

    return True, game.copy()


# =========================================================
# 🔎 GET GAME
# =========================================================

def get_speed_tap_game(chat_id):

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(chat_id)

        if not game:
            return None

        return game.copy()


# =========================================================
# 🌌 STORE ∞ PENDING CARD ID
# =========================================================

def set_speed_tap_pending_message_id(
    chat_id,
    message_id,
):

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(chat_id)

        if not game:
            return False

        game["pending_message_id"] = message_id
        return True


# =========================================================
# 📨 STORE GAME CARD ID
# =========================================================

def set_speed_tap_message_id(
    chat_id,
    message_id,
):

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(chat_id)

        if not game:
            return False

        game["message_id"] = message_id
        return True


# =========================================================
# ⏳ PENDING -> WAIT
# =========================================================

def start_speed_tap_wait(
    chat_id,
    wait_seconds,
):

    now = time.time()

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(chat_id)

        if not game:
            return None

        if game["finished"]:
            return None

        if game["state"] != "pending":
            return None

        game["state"] = "waiting"
        game["wait_seconds"] = float(wait_seconds)

        # Estimated GO time for early-tap feedback.
        # Actual reaction timer begins only after GO card update succeeds.
        game["go_at"] = now + float(wait_seconds)

        return game.copy()


# =========================================================
# 🟢 WAIT -> ACTIVE
# =========================================================

def activate_speed_tap(
    chat_id,
    active_time=SPEED_TAP_ACTIVE_TIME,
):

    now = time.time()

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(chat_id)

        if not game:
            return None

        if game["finished"]:
            return None

        if game["state"] != "waiting":
            return None

        game["state"] = "active"

        # Reaction timer starts here.
        game["go_at"] = now
        game["expires_at"] = now + float(active_time)

        return game.copy()


# =========================================================
# 🎁 RANDOM REWARD
# =========================================================

def calculate_speed_tap_reward(
    reaction_ms,
):

    try:
        reaction_ms = int(reaction_ms)
    except Exception:
        reaction_ms = 999999

    if reaction_ms < 800:
        base_points = random.randint(12, 20)

    elif reaction_ms < 1500:
        base_points = random.randint(8, 15)

    elif reaction_ms < 2500:
        base_points = random.randint(5, 12)

    else:
        base_points = random.randint(3, 8)

    jackpot_bonus = 0

    # 5% rare jackpot
    if random.random() < 0.05:
        jackpot_bonus = random.randint(5, 15)

    total_points = base_points + jackpot_bonus

    return {
        "base_points": base_points,
        "jackpot_bonus": jackpot_bonus,
        "total_points": total_points,
    }


# =========================================================
# ⚡ HANDLE TAP
# =========================================================

def register_speed_tap(
    chat_id,
    user_id,
    user_name,
):

    tap_time = time.time()

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(chat_id)

        if not game:
            return {
                "status": "no_game"
            }

        if game["finished"]:
            return {
                "status": "finished"
            }

        if game["state"] == "pending":
            return {
                "status": "pending"
            }

        if game["state"] == "waiting":

            remaining = 0

            if game["go_at"] is not None:
                remaining = max(
                    0,
                    game["go_at"] - tap_time
                )

            return {
                "status": "too_early",
                "remaining": remaining,
            }

        if game["state"] != "active":
            return {
                "status": "finished"
            }

        expires_at = game.get("expires_at")

        if (
            expires_at is not None
            and tap_time >= expires_at
        ):
            game["finished"] = True
            game["state"] = "finished"

            return {
                "status": "expired"
            }

        go_at = game.get("go_at")

        if go_at is None:
            return {
                "status": "too_early",
                "remaining": 0,
            }

        reaction_seconds = max(
            0,
            tap_time - go_at
        )

        reaction_ms = round(
            reaction_seconds * 1000
        )

        reward = calculate_speed_tap_reward(
            reaction_ms
        )

        game["winner_id"] = user_id
        game["winner_name"] = user_name
        game["winner_time_ms"] = reaction_ms
        game["reward_points"] = reward["total_points"]
        game["jackpot_bonus"] = reward["jackpot_bonus"]
        game["finished"] = True
        game["state"] = "finished"

        return {
            "status": "winner",
            "winner_id": user_id,
            "winner_name": user_name,
            "reaction_ms": reaction_ms,
            "reward_points": reward["total_points"],
            "base_points": reward["base_points"],
            "jackpot_bonus": reward["jackpot_bonus"],
        }


# =========================================================
# ⏰ EXPIRE ROUND
# =========================================================

def expire_speed_tap(chat_id):

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(chat_id)

        if not game:
            return None

        if game["finished"]:
            return None

        game["finished"] = True
        game["state"] = "finished"

        return game.copy()


# =========================================================
# 🧹 END / REMOVE GAME
# =========================================================

def end_speed_tap_game(chat_id):

    with _speed_tap_lock:

        return _active_speed_tap_games.pop(
            chat_id,
            None
        )


# =========================================================
# 📊 GAME STATE
# =========================================================

def get_speed_tap_state(chat_id):

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(chat_id)

        if not game:
            return None

        return {
            "state": game["state"],
            "start_at": game["start_at"],
            "go_at": game["go_at"],
            "winner_id": game["winner_id"],
            "winner_name": game["winner_name"],
            "winner_time_ms": game["winner_time_ms"],
            "reward_points": game["reward_points"],
            "jackpot_bonus": game["jackpot_bonus"],
            "pending_message_id": game["pending_message_id"],
            "message_id": game["message_id"],
            "finished": game["finished"],
        }
