"""Discard stale chat activity and spread automatic posts after a restart."""
import hashlib
import threading
import time
from telebot import TeleBot

class FreshUpdatesBot(TeleBot):
    def __init__(self, *args, **kwargs):
        self.started_at = int(time.time())
        super().__init__(*args, **kwargs)

    def process_new_updates(self, updates):
        now = time.time()
        fresh = []
        for update in updates:
            message = (getattr(update, 'message', None)
                       or getattr(update, 'edited_message', None)
                       or getattr(update, 'channel_post', None)
                       or getattr(update, 'edited_channel_post', None))
            # Callback message dates belong to the menu, not the click. Keep
            # old menus usable; startup polling separately clears queued clicks.
            if message is not None:
                date = getattr(message, 'edit_date', None) or getattr(message, 'date', None)
                if isinstance(date, (int, float)) and date < max(self.started_at, now - 120):
                    continue
            fresh.append(update)
        if fresh:
            return super().process_new_updates(fresh)

class AutoPostGate:
    """Startup jitter plus a bounded batch per minute, shared by auto feeds."""
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.window = self.started
        self.count = 0
        self.lock = threading.Lock()

    def allow(self, feature, chat_id):
        now = self.clock()
        jitter = int.from_bytes(hashlib.sha256(f'{feature}:{chat_id}'.encode()).digest()[:4], 'big') % 301
        if now - self.started < 30 + jitter:
            return False
        with self.lock:
            if now - self.window >= 60:
                self.window, self.count = now, 0
            if self.count >= 5:
                return False
            self.count += 1
            return True

AUTO_POSTS = AutoPostGate()


def abandoned(state, now):
    """Long outages end matches; brief restarts keep existing recovery rules."""
    return now > state.get('deadline', now) and now - state.get('updated', now) > 3600
