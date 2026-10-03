# =========================================================
# ⏳ COOLDOWN MANAGER
# =========================================================

import random
import threading
import time


_cooldowns = {}
_cooldowns_lock = threading.RLock()


# =========================================================
# 🔑 INTERNAL KEY BUILDER
# =========================================================

def _make_key(
    cooldown_type,
    chat_id=None,
    user_id=None,
    extra=None
):
    return (
        cooldown_type,
        chat_id,
        user_id,
        extra
    )


# =========================================================
# 🕒 GET REMAINING COOLDOWN
#
# Return:
#   0      = ready
#   > 0    = seconds remaining
# =========================================================

def get_remaining_cooldown(
    cooldown_type,
    chat_id=None,
    user_id=None,
    extra=None
):
    key = _make_key(
        cooldown_type,
        chat_id,
        user_id,
        extra
    )

    now = time.time()

    with _cooldowns_lock:

        expires_at = _cooldowns.get(key)

        if expires_at is None:
            return 0

        remaining = expires_at - now

        if remaining <= 0:
            _cooldowns.pop(key, None)
            return 0

        return remaining


# =========================================================
# ✅ IS READY?
# =========================================================

def cooldown_ready(
    cooldown_type,
    chat_id=None,
    user_id=None,
    extra=None
):
    return (
        get_remaining_cooldown(
            cooldown_type,
            chat_id,
            user_id,
            extra
        ) <= 0
    )


# =========================================================
# ▶️ SET FIXED COOLDOWN
# =========================================================

def set_cooldown(
    cooldown_type,
    seconds,
    chat_id=None,
    user_id=None,
    extra=None
):
    seconds = max(
        0,
        float(seconds)
    )

    key = _make_key(
        cooldown_type,
        chat_id,
        user_id,
        extra
    )

    expires_at = (
        time.time()
        + seconds
    )

    with _cooldowns_lock:
        _cooldowns[key] = expires_at

    return expires_at


# =========================================================
# 🎲 SET RANDOM COOLDOWN
#
# Example:
# Boss attack:
# random 5–25 sec
# =========================================================

def set_random_cooldown(
    cooldown_type,
    min_seconds,
    max_seconds,
    chat_id=None,
    user_id=None,
    extra=None
):
    min_seconds = float(min_seconds)
    max_seconds = float(max_seconds)

    if min_seconds > max_seconds:
        min_seconds, max_seconds = (
            max_seconds,
            min_seconds
        )

    seconds = random.uniform(
        min_seconds,
        max_seconds
    )

    set_cooldown(
        cooldown_type,
        seconds,
        chat_id=chat_id,
        user_id=user_id,
        extra=extra
    )

    return seconds


# =========================================================
# 🧪 CHECK + START COOLDOWN
#
# Useful for commands/buttons.
#
# Return:
#   (True, 0)
#       = allowed, cooldown started
#
#   (False, remaining_seconds)
#       = still cooling down
# =========================================================

def check_and_start_cooldown(
    cooldown_type,
    seconds,
    chat_id=None,
    user_id=None,
    extra=None
):
    remaining = get_remaining_cooldown(
        cooldown_type,
        chat_id,
        user_id,
        extra
    )

    if remaining > 0:
        return False, remaining

    set_cooldown(
        cooldown_type,
        seconds,
        chat_id=chat_id,
        user_id=user_id,
        extra=extra
    )

    return True, 0


# =========================================================
# 🎲 CHECK + START RANDOM COOLDOWN
# =========================================================

def check_and_start_random_cooldown(
    cooldown_type,
    min_seconds,
    max_seconds,
    chat_id=None,
    user_id=None,
    extra=None
):
    remaining = get_remaining_cooldown(
        cooldown_type,
        chat_id,
        user_id,
        extra
    )

    if remaining > 0:
        return False, remaining, None

    seconds = set_random_cooldown(
        cooldown_type,
        min_seconds,
        max_seconds,
        chat_id=chat_id,
        user_id=user_id,
        extra=extra
    )

    return True, 0, seconds


# =========================================================
# 🗑️ CLEAR ONE COOLDOWN
# =========================================================

def clear_cooldown(
    cooldown_type,
    chat_id=None,
    user_id=None,
    extra=None
):
    key = _make_key(
        cooldown_type,
        chat_id,
        user_id,
        extra
    )

    with _cooldowns_lock:
        return _cooldowns.pop(
            key,
            None
        )


# =========================================================
# 🧹 CLEAR USER COOLDOWNS
# =========================================================

def clear_user_cooldowns(
    user_id,
    chat_id=None
):
    removed = 0

    with _cooldowns_lock:

        keys = list(
            _cooldowns.keys()
        )

        for key in keys:

            (
                cooldown_type,
                saved_chat_id,
                saved_user_id,
                extra
            ) = key

            if saved_user_id != user_id:
                continue

            if (
                chat_id is not None
                and saved_chat_id != chat_id
            ):
                continue

            _cooldowns.pop(
                key,
                None
            )

            removed += 1

    return removed


# =========================================================
# 🧹 CLEAR GROUP COOLDOWNS
# =========================================================

def clear_chat_cooldowns(
    chat_id
):
    removed = 0

    with _cooldowns_lock:

        keys = list(
            _cooldowns.keys()
        )

        for key in keys:

            (
                cooldown_type,
                saved_chat_id,
                saved_user_id,
                extra
            ) = key

            if saved_chat_id != chat_id:
                continue

            _cooldowns.pop(
                key,
                None
            )

            removed += 1

    return removed


# =========================================================
# 🧽 CLEAN EXPIRED COOLDOWNS
# =========================================================

def cleanup_expired_cooldowns():
    now = time.time()
    removed = 0

    with _cooldowns_lock:

        keys = list(
            _cooldowns.keys()
        )

        for key in keys:

            expires_at = _cooldowns.get(
                key
            )

            if (
                expires_at is not None
                and now >= expires_at
            ):
                _cooldowns.pop(
                    key,
                    None
                )

                removed += 1

    return removed
