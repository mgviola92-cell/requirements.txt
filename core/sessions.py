# =========================================================
# 🎮 ACTIVE SESSION MANAGER
# =========================================================

import threading
import time


# =========================================================
# 🔒 SESSION STORAGE
#
# Key:
#   (chat_id, session_type)
#
# Example:
#   (-100123456789, "boss_raid")
# =========================================================

_active_sessions = {}
_sessions_lock = threading.RLock()


# =========================================================
# ⚙️ SESSION PRIORITIES
#
# Priority မြင့်တဲ့ system run နေရင်
# low-priority random events တွေ မဝင်လာအောင် အသုံးပြုမည်။
# =========================================================

SESSION_PRIORITIES = {

    # -----------------------------------------
    # MAJOR EVENTS
    # -----------------------------------------

    "boss_raid": 100,
    "team_battle": 95,
    "math_battle": 90,

    # -----------------------------------------
    # MULTIPLAYER GAMES
    # -----------------------------------------

    "pair_challenge": 80,
    "roast_battle": 75,
    "word_chain": 70,

    # -----------------------------------------
    # QUICK GAMES
    # -----------------------------------------

    "emoji_guess": 60,
    "speed_tap": 55,
    "would_you_rather": 50,
    "this_or_that": 50,

    # -----------------------------------------
    # EVENTS
    # -----------------------------------------

    "random_event": 40,
    "lucky_drop": 35,

    # -----------------------------------------
    # PASSIVE / BACKGROUND SYSTEMS
    # -----------------------------------------

    "daily_challenge": 20,
    "group_goal": 20,
    "auto_fun": 10,
}


# =========================================================
# 🧩 SESSION GROUPS
#
# exclusive:
#   တစ်ချိန်တည်းမှာ major interactive game
#   တစ်ခုတည်း run စေချင်တဲ့အရာတွေ
#
# passive:
#   Daily Challenge / Group Goal လို
#   background မှာအတူရှိလို့ရတဲ့ systems
# =========================================================

EXCLUSIVE_SESSIONS = {
    "boss_raid",
    "team_battle",
    "math_battle",
    "pair_challenge",
    "roast_battle",
    "word_chain",
    "emoji_guess",
    "speed_tap",
    "would_you_rather",
    "this_or_that",
    "random_event",
    "lucky_drop",
}

PASSIVE_SESSIONS = {
    "daily_challenge",
    "group_goal",
}


# =========================================================
# 🔎 GET SESSION
# =========================================================

def get_session(chat_id, session_type):
    key = (chat_id, session_type)

    with _sessions_lock:
        session = _active_sessions.get(key)

        if not session:
            return None

        # Expired session cleanup
        expires_at = session.get("expires_at")

        if (
            expires_at is not None
            and time.time() >= expires_at
        ):
            _active_sessions.pop(key, None)
            return None

        return session


# =========================================================
# ✅ SESSION EXISTS?
# =========================================================

def has_session(chat_id, session_type):
    return get_session(
        chat_id,
        session_type
    ) is not None


# =========================================================
# 📋 GET ALL ACTIVE SESSIONS IN GROUP
# =========================================================

def get_chat_sessions(chat_id):
    now = time.time()
    result = {}

    with _sessions_lock:

        expired_keys = []

        for key, session in _active_sessions.items():

            saved_chat_id, session_type = key

            if saved_chat_id != chat_id:
                continue

            expires_at = session.get("expires_at")

            if (
                expires_at is not None
                and now >= expires_at
            ):
                expired_keys.append(key)
                continue

            result[session_type] = session

        for key in expired_keys:
            _active_sessions.pop(key, None)

    return result


# =========================================================
# 🚦 CAN START SESSION?
# =========================================================

def can_start_session(
    chat_id,
    session_type,
    allow_with=None
):
    """
    Return:
        (True, None)
    or
        (False, blocking_session_type)

    allow_with:
        set/list of session types which are explicitly
        allowed to run together.
    """

    allow_with = set(allow_with or [])

    # Passive systems can coexist
    if session_type in PASSIVE_SESSIONS:
        return True, None

    active = get_chat_sessions(chat_id)

    if not active:
        return True, None

    # Same session already active
    if session_type in active:
        return False, session_type

    if session_type not in EXCLUSIVE_SESSIONS:
        return True, None

    for active_type in active:

        if active_type in allow_with:
            continue

        if active_type in PASSIVE_SESSIONS:
            continue

        if active_type in EXCLUSIVE_SESSIONS:
            return False, active_type

    return True, None


# =========================================================
# ▶️ START SESSION
# =========================================================

def start_session(
    chat_id,
    session_type,
    data=None,
    duration=None,
    allow_with=None
):
    """
    duration:
        seconds
        None = manual end

    Returns:
        (True, session)
        (False, blocking_session_type)
    """

    allowed, blocker = can_start_session(
        chat_id,
        session_type,
        allow_with=allow_with
    )

    if not allowed:
        return False, blocker

    now = time.time()

    session = {
        "chat_id": chat_id,
        "type": session_type,
        "started_at": now,
        "expires_at": (
            now + duration
            if duration is not None
            else None
        ),
        "data": dict(data or {})
    }

    key = (chat_id, session_type)

    with _sessions_lock:
        _active_sessions[key] = session

    return True, session


# =========================================================
# ⏹️ END SESSION
# =========================================================

def end_session(
    chat_id,
    session_type
):
    key = (chat_id, session_type)

    with _sessions_lock:
        return _active_sessions.pop(
            key,
            None
        )


# =========================================================
# 📝 UPDATE SESSION DATA
# =========================================================

def update_session(
    chat_id,
    session_type,
    updates
):
    key = (chat_id, session_type)

    with _sessions_lock:

        session = _active_sessions.get(key)

        if not session:
            return False

        session["data"].update(
            updates
        )

        return True


# =========================================================
# 📦 GET SESSION DATA
# =========================================================

def get_session_data(
    chat_id,
    session_type,
    default=None
):
    session = get_session(
        chat_id,
        session_type
    )

    if not session:
        return default

    return session.get(
        "data",
        default
    )


# =========================================================
# 🧹 CLEAR ALL GROUP SESSIONS
#
# Mainly useful for admin/debug/recovery.
# =========================================================

def clear_chat_sessions(chat_id):
    removed = 0

    with _sessions_lock:

        keys = [
            key
            for key in _active_sessions
            if key[0] == chat_id
        ]

        for key in keys:
            _active_sessions.pop(
                key,
                None
            )
            removed += 1

    return removed


# =========================================================
# 🎯 HIGHEST ACTIVE PRIORITY
# =========================================================

def get_highest_priority_session(
    chat_id
):
    active = get_chat_sessions(
        chat_id
    )

    if not active:
        return None

    highest_type = max(
        active.keys(),
        key=lambda session_type:
            SESSION_PRIORITIES.get(
                session_type,
                0
            )
    )

    return {
        "type": highest_type,
        "priority":
            SESSION_PRIORITIES.get(
                highest_type,
                0
            ),
        "session":
            active[highest_type]
    }


# =========================================================
# 🤖 AUTO FUN ALLOWED?
#
# Major games/events run နေရင် Auto Fun
# silence လုပ်ဖို့ အသုံးပြုမည်။
# =========================================================

def auto_fun_allowed(chat_id):

    highest = get_highest_priority_session(
        chat_id
    )

    if highest is None:
        return True

    return (
        highest["priority"]
        < SESSION_PRIORITIES["auto_fun"]
    )
