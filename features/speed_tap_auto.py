# =========================================================
# ⚡ SPEED TAP AUTO-SPAWN ACTIVITY ENGINE
# =========================================================
#
# Purpose:
# - Track real group activity.
# - Avoid fixed/repetitive spawn intervals.
# - Randomly evaluate active groups.
# - Trigger a callback only when the group is active enough.
# - Prevent auto-spawn spam with a random quiet period.
#
# IMPORTANT:
# This module does NOT send Telegram messages itself.
# bot.py supplies:
#   1) a spawn callback
#   2) an optional "can spawn?" callback
#
# This keeps the activity engine independent from Telegram UI.
# =========================================================

import random
import threading
import time

from core.timers import (
    schedule_task,
    cancel_task,
    has_task,
)


# =========================================================
# ⚙️ SETTINGS
# =========================================================

# Recent activity window.
ACTIVITY_WINDOW_SECONDS = 5 * 60

# Minimum recent text messages required.
MIN_ACTIVE_MESSAGES = 6

# Minimum distinct members required.
MIN_ACTIVE_USERS = 2

# First/random evaluation delay after activity.
CHECK_DELAY_MIN = 90
CHECK_DELAY_MAX = 300

# If group is still active but the random roll fails,
# evaluate again after another unpredictable delay.
RECHECK_DELAY_MIN = 120
RECHECK_DELAY_MAX = 480

# Chance of auto-spawning on a qualified evaluation.
AUTO_SPAWN_CHANCE = 0.35

# After a successful automatic spawn, keep the auto system
# quiet for a random amount of time.
AUTO_QUIET_MIN = 15 * 60
AUTO_QUIET_MAX = 45 * 60

# Prevent one user from creating fake "group activity"
# by sending messages extremely quickly.
PER_USER_ACTIVITY_GAP = 8


# =========================================================
# 🔒 STATE
# =========================================================

_lock = threading.RLock()

# chat_id -> list[(timestamp, user_id)]
_activity = {}

# (chat_id, user_id) -> last accepted activity timestamp
_last_user_activity = {}

# chat_id -> timestamp until automatic spawning is quiet
_quiet_until = {}

_spawn_callback = None
_can_spawn_callback = None


# =========================================================
# 🧹 INTERNAL CLEANUP
# =========================================================

def _cleanup_activity_locked(
    chat_id,
    now=None,
):

    if now is None:
        now = time.time()

    cutoff = (
        now
        - ACTIVITY_WINDOW_SECONDS
    )

    items = _activity.get(
        chat_id,
        []
    )

    items = [
        item
        for item in items
        if item[0] >= cutoff
    ]

    if items:
        _activity[chat_id] = items
    else:
        _activity.pop(
            chat_id,
            None,
        )

    return items


# =========================================================
# 📊 ACTIVITY SNAPSHOT
# =========================================================

def get_speed_tap_activity(
    chat_id,
):

    now = time.time()

    with _lock:

        items = _cleanup_activity_locked(
            chat_id,
            now=now,
        )

        users = {
            user_id
            for _, user_id
            in items
        }

        return {
            "messages": len(items),
            "users": len(users),
            "active": (
                len(items)
                >= MIN_ACTIVE_MESSAGES
                and len(users)
                >= MIN_ACTIVE_USERS
            ),
            "quiet_remaining": max(
                0,
                _quiet_until.get(
                    chat_id,
                    0,
                )
                - now,
            ),
        }


# =========================================================
# 🚦 AUTO SPAWN CONFIG
# =========================================================

def configure_speed_tap_auto(
    spawn_callback,
    can_spawn_callback=None,
):

    global _spawn_callback
    global _can_spawn_callback

    with _lock:

        _spawn_callback = (
            spawn_callback
        )

        _can_spawn_callback = (
            can_spawn_callback
        )

    return True


# =========================================================
# 🕒 RANDOM CHECK SCHEDULER
# =========================================================

def _task_id(chat_id):

    return (
        f"speedtap_auto_check:"
        f"{chat_id}"
    )


def _schedule_random_check(
    chat_id,
    minimum,
    maximum,
):

    delay = random.randint(
        int(minimum),
        int(maximum),
    )

    return schedule_task(
        delay,
        _evaluate_speed_tap_auto,
        chat_id,
        task_id=_task_id(chat_id),
        replace=False,
    )


# =========================================================
# ⚡ AUTO-SPAWN EVALUATION
# =========================================================

def _evaluate_speed_tap_auto(
    chat_id,
):

    now = time.time()

    with _lock:

        activity = (
            _cleanup_activity_locked(
                chat_id,
                now=now,
            )
        )

        message_count = len(
            activity
        )

        user_count = len({
            user_id
            for _, user_id
            in activity
        })

        quiet_until = (
            _quiet_until.get(
                chat_id,
                0,
            )
        )

        spawn_callback = (
            _spawn_callback
        )

        can_spawn_callback = (
            _can_spawn_callback
        )

    # -----------------------------------------
    # Automatic quiet period
    # -----------------------------------------

    if now < quiet_until:

        # Do not constantly reschedule while quiet.
        return False

    # -----------------------------------------
    # Group not active enough
    # -----------------------------------------

    if (
        message_count
        < MIN_ACTIVE_MESSAGES
        or user_count
        < MIN_ACTIVE_USERS
    ):

        return False

    # -----------------------------------------
    # No bot callback connected yet
    # -----------------------------------------

    if spawn_callback is None:
        return False

    # -----------------------------------------
    # Major game/event currently blocking?
    # -----------------------------------------

    if can_spawn_callback is not None:

        try:

            if not can_spawn_callback(
                chat_id
            ):

                _schedule_random_check(
                    chat_id,
                    RECHECK_DELAY_MIN,
                    RECHECK_DELAY_MAX,
                )

                return False

        except Exception as e:

            print(
                "Speed Tap Auto "
                f"can-spawn error: {e}"
            )

            return False

    # -----------------------------------------
    # Randomness:
    # Active group does NOT guarantee a spawn.
    # -----------------------------------------

    if (
        random.random()
        > AUTO_SPAWN_CHANCE
    ):

        _schedule_random_check(
            chat_id,
            RECHECK_DELAY_MIN,
            RECHECK_DELAY_MAX,
        )

        return False

    # -----------------------------------------
    # Trigger actual Speed Tap spawn
    # -----------------------------------------

    try:

        started = bool(
            spawn_callback(
                chat_id
            )
        )

    except Exception as e:

        print(
            "Speed Tap Auto "
            f"spawn error: {e}"
        )

        started = False

    if not started:

        _schedule_random_check(
            chat_id,
            RECHECK_DELAY_MIN,
            RECHECK_DELAY_MAX,
        )

        return False

    # -----------------------------------------
    # Successful auto spawn:
    # random quiet period before another
    # automatic Speed Tap may happen.
    # -----------------------------------------

    quiet_seconds = random.randint(
        AUTO_QUIET_MIN,
        AUTO_QUIET_MAX,
    )

    with _lock:

        _quiet_until[
            chat_id
        ] = (
            time.time()
            + quiet_seconds
        )

        # Clear previous activity so the same burst
        # cannot immediately trigger another event.
        _activity.pop(
            chat_id,
            None,
        )

    return True


# =========================================================
# 💬 RECORD GROUP ACTIVITY
# =========================================================

def record_speed_tap_activity(
    chat_id,
    user_id,
):

    now = time.time()

    key = (
        chat_id,
        user_id,
    )

    with _lock:

        last_time = (
            _last_user_activity.get(
                key,
                0,
            )
        )

        # Ignore rapid messages from one person.
        if (
            now - last_time
            < PER_USER_ACTIVITY_GAP
        ):
            return False

        _last_user_activity[
            key
        ] = now

        _cleanup_activity_locked(
            chat_id,
            now=now,
        )

        _activity.setdefault(
            chat_id,
            []
        ).append(
            (
                now,
                user_id,
            )
        )

        quiet = (
            now
            < _quiet_until.get(
                chat_id,
                0,
            )
        )

    # During auto quiet time, record activity
    # but do not arm another check yet.
    if quiet:
        return True

    # Only one random evaluation task per group.
    if not has_task(
        _task_id(chat_id)
    ):

        _schedule_random_check(
            chat_id,
            CHECK_DELAY_MIN,
            CHECK_DELAY_MAX,
        )

    return True


# =========================================================
# 🧹 RESET / DEBUG HELPERS
# =========================================================

def clear_speed_tap_auto(
    chat_id,
):

    cancel_task(
        _task_id(chat_id)
    )

    with _lock:

        _activity.pop(
            chat_id,
            None,
        )

        _quiet_until.pop(
            chat_id,
            None,
        )

        keys = [
            key
            for key
            in _last_user_activity
            if key[0] == chat_id
        ]

        for key in keys:
            _last_user_activity.pop(
                key,
                None,
            )

    return True
