# =========================================================
# ⏱️ TIMER / SCHEDULE MANAGER
# =========================================================

import threading
import time
import uuid


_timers = {}
_timers_lock = threading.RLock()


# =========================================================
# ▶️ SCHEDULE TASK
# =========================================================

def schedule_task(
    delay_seconds,
    callback,
    *args,
    task_id=None,
    replace=False,
    **kwargs
):
    delay_seconds = max(
        0,
        float(delay_seconds)
    )

    if task_id is None:
        task_id = str(uuid.uuid4())

    with _timers_lock:

        # Same ID already exists
        if task_id in _timers:

            if not replace:
                return None

            old_task = _timers.pop(
                task_id,
                None
            )

            if old_task:
                old_task["timer"].cancel()

        run_at = (
            time.time()
            + delay_seconds
        )

        def wrapped_callback():
            try:
                callback(
                    *args,
                    **kwargs
                )

            except Exception as e:
                print(
                    f"❌ Timer Task Error "
                    f"[{task_id}]: {e}"
                )

            finally:
                with _timers_lock:
                    _timers.pop(
                        task_id,
                        None
                    )

        timer = threading.Timer(
            delay_seconds,
            wrapped_callback
        )

        # Bot shutdown ကို timer က
        # မတားထားစေရန် daemon
        timer.daemon = True

        _timers[task_id] = {
            "timer": timer,
            "run_at": run_at,
            "created_at": time.time()
        }

        timer.start()

    return task_id


# =========================================================
# ❌ CANCEL TASK
# =========================================================

def cancel_task(task_id):

    with _timers_lock:

        task = _timers.pop(
            task_id,
            None
        )

        if not task:
            return False

        task["timer"].cancel()

        return True


# =========================================================
# 🔎 TASK EXISTS?
# =========================================================

def has_task(task_id):

    with _timers_lock:
        return task_id in _timers


# =========================================================
# ⏳ GET REMAINING TIME
# =========================================================

def get_task_remaining(task_id):

    with _timers_lock:

        task = _timers.get(
            task_id
        )

        if not task:
            return 0

        remaining = (
            task["run_at"]
            - time.time()
        )

        return max(
            0,
            remaining
        )


# =========================================================
# 🔄 RESCHEDULE TASK
# =========================================================

def reschedule_task(
    task_id,
    delay_seconds,
    callback,
    *args,
    **kwargs
):

    return schedule_task(
        delay_seconds,
        callback,
        *args,
        task_id=task_id,
        replace=True,
        **kwargs
    )


# =========================================================
# 🧹 CLEAR ALL TIMERS
#
# Mainly for debug / shutdown.
# =========================================================

def clear_all_tasks():

    with _timers_lock:

        tasks = list(
            _timers.values()
        )

        _timers.clear()

    for task in tasks:
        try:
            task["timer"].cancel()
        except Exception:
            pass

    return len(tasks)
