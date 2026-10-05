import random
import threading
import time
import uuid

_lock = threading.RLock()
_battles = {}
_listener = None

MIN_DURATION = 6 * 60
MAX_DURATION = 10 * 60

HYPE_LINES = [
    "အရှိန်မလျှော့နဲ့ — ဒီပွဲက မပြီးသေးဘူး!",
    "Score gap က ပြောင်းနိုင်သေးတယ် — points ရအောင် game တွေဆော့!",
    "Teamwork ပြချိန်ရောက်ပြီ — ကိုယ့်အသင်းအတွက် points ယူ!",
    "Battle က ပူလာပြီ — comeback လုပ်လို့ရသေးတယ်!",
]

def set_update_listener(callback):
    global _listener
    _listener = callback

def _copy(b):
    if not b:
        return None
    out = dict(b)
    out["members"] = {k: dict(v) for k, v in b["members"].items()}
    out["scores"] = dict(b["scores"])
    return out

def start_battle(chat_id):
    with _lock:
        cur = _battles.get(chat_id)
        if cur and not cur.get("finished"):
            return False, _copy(cur)
        now = time.time()
        duration = random.randint(MIN_DURATION, MAX_DURATION)
        half_ratio = random.uniform(0.42, 0.58)
        battle = {
            "id": uuid.uuid4().hex[:10],
            "chat_id": chat_id,
            "started_at": now,
            "half_at": now + duration * half_ratio,
            "ends_at": now + duration,
            "scores": {"red": 0, "blue": 0},
            "members": {},
            "message_id": None,
            "stage": "live",
            "finished": False,
        }
        _battles[chat_id] = battle
        return True, _copy(battle)

def get_battle(chat_id):
    with _lock:
        return _copy(_battles.get(chat_id))

def set_message_id(chat_id, battle_id, message_id, stage=None):
    with _lock:
        b = _battles.get(chat_id)
        if not b or b["id"] != battle_id:
            return False
        b["message_id"] = message_id
        if stage:
            b["stage"] = stage
        return True

def _pick_team(b):
    red_count = sum(1 for m in b["members"].values() if m["team"] == "red")
    blue_count = sum(1 for m in b["members"].values() if m["team"] == "blue")
    if red_count < blue_count:
        return "red"
    if blue_count < red_count:
        return "blue"
    return random.choice(("red", "blue"))

def record_points(chat_id, user_id, points, name=None):
    points = int(points)
    if points <= 0:
        return None
    callback = None
    snapshot = None
    with _lock:
        b = _battles.get(chat_id)
        if not b or b.get("finished") or time.time() >= b["ends_at"]:
            return None
        m = b["members"].get(user_id)
        if not m:
            m = {"name": name or "Player", "team": _pick_team(b), "points": 0}
            b["members"][user_id] = m
        elif name:
            m["name"] = name
        m["points"] += points
        b["scores"][m["team"]] += points
        snapshot = _copy(b)
        callback = _listener
    if callback:
        try:
            callback(snapshot)
        except Exception as exc:
            print("Team Battle update listener error:", exc)
    return snapshot

def top_members(battle, team, limit=3):
    rows = [
        dict(v) for v in (battle or {}).get("members", {}).values()
        if v.get("team") == team
    ]
    rows.sort(key=lambda x: x.get("points", 0), reverse=True)
    return rows[:limit]

def member_ids(battle, team=None):
    return [
        uid for uid, row in (battle or {}).get("members", {}).items()
        if team is None or row.get("team") == team
    ]

def finish_battle(chat_id, battle_id):
    with _lock:
        b = _battles.get(chat_id)
        if not b or b["id"] != battle_id:
            return None
        b["finished"] = True
        b["stage"] = "final"
        return _copy(b)

def hype_line():
    return random.choice(HYPE_LINES)
