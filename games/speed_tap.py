# =========================================================
# ⚡ SPEED TAP GAME ENGINE
# =========================================================

import threading
import time


# =========================================================
# ⚙️ SETTINGS
# =========================================================

SPEED_TAP_WAIT_MIN = 3
SPEED_TAP_WAIT_MAX = 8

SPEED_TAP_ACTIVE_TIME = 10


# =========================================================
# 🔒 ACTIVE GAMES
# =========================================================

_active_speed_tap_games = {}
_speed_tap_lock = threading.RLock()


# =========================================================
# ▶️ CREATE GAME
# =========================================================

def create_speed_tap_game(
    chat_id,
    wait_seconds,
):

    now = time.time()

    game = {
        "chat_id": chat_id,

        "state": "waiting",

        "created_at": now,

        "wait_seconds":
            float(wait_seconds),

        "go_at":
            now + float(wait_seconds),

        "expires_at": None,

        "winner_id": None,

        "winner_name": None,

        "winner_time_ms": None,

        "message_id": None,

        "finished": False,
    }

    with _speed_tap_lock:

        if chat_id in _active_speed_tap_games:
            return False, (
                _active_speed_tap_games[
                    chat_id
                ]
            )

        _active_speed_tap_games[
            chat_id
        ] = game

    return True, game


# =========================================================
# 🔎 GET GAME
# =========================================================

def get_speed_tap_game(chat_id):

    with _speed_tap_lock:

        return _active_speed_tap_games.get(
            chat_id
        )


# =========================================================
# 📨 STORE TELEGRAM MESSAGE ID
# =========================================================

def set_speed_tap_message_id(
    chat_id,
    message_id,
):

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(
            chat_id
        )

        if not game:
            return False

        game["message_id"] = message_id

        return True


# =========================================================
# 🟢 START TAP PHASE
# =========================================================

def activate_speed_tap(
    chat_id,
    active_time=SPEED_TAP_ACTIVE_TIME,
):

    now = time.time()

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(
            chat_id
        )

        if not game:
            return None

        if game["finished"]:
            return None

        game["state"] = "active"
        game["go_at"] = now

        game["expires_at"] = (
            now + float(active_time)
        )

        return game.copy()


# =========================================================
# ⚡ HANDLE TAP
#
# status:
#
# no_game
# too_early
# expired
# winner
# finished
# =========================================================

def register_speed_tap(
    chat_id,
    user_id,
    user_name,
):

    tap_time = time.time()

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(
            chat_id
        )

        if not game:
            return {
                "status": "no_game"
            }

        if game["finished"]:
            return {
                "status": "finished"
            }

        # -----------------------------------------
        # User tapped before GO
        # -----------------------------------------

        if game["state"] == "waiting":

            remaining = max(
                0,
                game["go_at"] - tap_time
            )

            return {
                "status": "too_early",
                "remaining": remaining,
            }

        # -----------------------------------------
        # Invalid state
        # -----------------------------------------

        if game["state"] != "active":

            return {
                "status": "finished"
            }

        # -----------------------------------------
        # Time expired
        # -----------------------------------------

        expires_at = game.get(
            "expires_at"
        )

        if (
            expires_at is not None
            and tap_time >= expires_at
        ):

            game["finished"] = True
            game["state"] = "finished"

            return {
                "status": "expired"
            }

        # -----------------------------------------
        # FIRST TAP WINS
        # -----------------------------------------

        reaction_seconds = max(
            0,
            tap_time - game["go_at"]
        )

        reaction_ms = round(
            reaction_seconds * 1000
        )

        game["winner_id"] = user_id
        game["winner_name"] = user_name

        game["winner_time_ms"] = (
            reaction_ms
        )

        game["finished"] = True
        game["state"] = "finished"

        return {
            "status": "winner",

            "winner_id":
                user_id,

            "winner_name":
                user_name,

            "reaction_ms":
                reaction_ms,
        }


# =========================================================
# ⏰ EXPIRE ROUND
# =========================================================

def expire_speed_tap(chat_id):

    with _speed_tap_lock:

        game = _active_speed_tap_games.get(
            chat_id
        )

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

        game = _active_speed_tap_games.get(
            chat_id
        )

        if not game:
            return None

        return {
            "state":
                game["state"],

            "winner_id":
                game["winner_id"],

            "winner_name":
                game["winner_name"],

            "winner_time_ms":
                game["winner_time_ms"],

            "message_id":
                game["message_id"],

            "finished":
                game["finished"],
        }
