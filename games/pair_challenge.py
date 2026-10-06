import random
import threading
import time
import uuid

_lock = threading.RLock()
_games = {}
_recent = {}

MODES = {
    "duo": {"title": "CO-OP DUO", "min": 2, "max": 2, "rounds": 5},
    "squad": {"title": "CO-OP SQUAD", "min": 2, "max": 4, "rounds": 5},
    "versus": {"title": "TEAM VERSUS 2v2", "min": 4, "max": 4, "rounds": 5},
}

# This is a starter bank for the framework, not a claimed final bank size.
# The engine avoids repeats inside a match and supports adding more entries later.
CHALLENGES = [
    {"id":"q1","kind":"quiz","question":"Which planet is known as the Red Planet?","options":["Mars","Venus"],"answer":"a"},
    {"id":"q2","kind":"quiz","question":"Which is the largest ocean?","options":["Pacific","Atlantic"],"answer":"a"},
    {"id":"q3","kind":"quiz","question":"Which animal is fastest on land?","options":["Cheetah","Lion"],"answer":"a"},
    {"id":"q4","kind":"quiz","question":"Which one is a programming language?","options":["Python","Photoshop"],"answer":"a"},
    {"id":"q5","kind":"quiz","question":"Which gas do plants absorb?","options":["Carbon dioxide","Oxygen"],"answer":"a"},
    {"id":"q6","kind":"quiz","question":"Which is a mammal?","options":["Dolphin","Shark"],"answer":"a"},
    {"id":"p1","kind":"puzzle","question":"Complete: 2, 4, 8, 16, ?","options":["24","32"],"answer":"b"},
    {"id":"p2","kind":"puzzle","question":"Complete: 3, 6, 12, 24, ?","options":["36","48"],"answer":"b"},
    {"id":"p3","kind":"puzzle","question":"Odd one out","options":["Triangle","Circle"],"answer":"b"},
    {"id":"p4","kind":"puzzle","question":"5 + 5 x 2 = ?","options":["15","20"],"answer":"a"},
    {"id":"p5","kind":"puzzle","question":"Complete: 1, 1, 2, 3, 5, ?","options":["8","10"],"answer":"a"},
    {"id":"m1","kind":"math","question":"18 + 7 = ?","options":["25","26"],"answer":"a"},
    {"id":"m2","kind":"math","question":"9 x 6 = ?","options":["54","56"],"answer":"a"},
    {"id":"m3","kind":"math","question":"72 / 8 = ?","options":["8","9"],"answer":"b"},
    {"id":"s1","kind":"sync","question":"SYNC: Pick the same side without chatting.","options":["LEFT","RIGHT"],"answer":None},
    {"id":"s2","kind":"sync","question":"SYNC: Match your teammate.","options":["SUN","MOON"],"answer":None},
    {"id":"s3","kind":"sync","question":"SYNC: Think alike and choose.","options":["FIRE","ICE"],"answer":None},
    {"id":"s4","kind":"sync","question":"SYNC: Same choice wins.","options":["DAY","NIGHT"],"answer":None},
]

def _copy(game):
    if not game:
        return None
    out = dict(game)
    out["players"] = {uid: dict(row) for uid, row in game["players"].items()}
    out["answers"] = dict(game.get("answers", {}))
    out["team_scores"] = dict(game.get("team_scores", {}))
    out["match_scores"] = dict(game.get("match_scores", {}))
    out["used_challenges"] = list(game.get("used_challenges", []))
    out["round_results"] = list(game.get("round_results", []))
    if game.get("challenge"):
        out["challenge"] = dict(game["challenge"])
    return out

def _allowed_kinds(game):
    mode = game.get("mode")
    if mode == "versus":
        return {"quiz", "puzzle", "math"}
    return {"quiz", "puzzle", "sync"}

def _pick_challenge(game):
    used = set(game.get("used_challenges", []))
    pool = [q for q in CHALLENGES if q["kind"] in _allowed_kinds(game) and q["id"] not in used]
    if not pool:
        game["used_challenges"] = []
        pool = [q for q in CHALLENGES if q["kind"] in _allowed_kinds(game)]
    challenge = dict(random.choice(pool))
    game["used_challenges"].append(challenge["id"])
    return challenge

def create_lobby(chat_id, owner_id, owner_name):
    with _lock:
        current = _games.get(chat_id)
        if current and not current.get("finished"):
            return False, _copy(current)
        game = {
            "id": uuid.uuid4().hex[:10],
            "chat_id": chat_id,
            "owner_id": owner_id,
            "players": {owner_id: {"name": owner_name or "Player", "team": None}},
            "mode": None,
            "state": "mode",
            "message_id": None,
            "challenge": None,
            "answers": {},
            "team_scores": {"red": 0, "blue": 0},
            "match_scores": {"red": 0, "blue": 0},
            "round_no": 0,
            "total_rounds": 5,
            "used_challenges": [],
            "round_results": [],
            "created_at": time.time(),
            "ends_at": None,
            "finished": False,
        }
        _games[chat_id] = game
        return True, _copy(game)

def get(chat_id):
    with _lock:
        return _copy(_games.get(chat_id))

def set_message(chat_id, game_id, message_id):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id:
            return False
        game["message_id"] = message_id
        return True

def select_mode(chat_id, game_id, user_id, mode):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id or game["state"] != "mode":
            return {"status": "closed"}
        if user_id != game["owner_id"]:
            return {"status": "owner_only"}
        if mode not in MODES:
            return {"status": "invalid"}
        game["mode"] = mode
        game["total_rounds"] = MODES[mode]["rounds"]
        game["state"] = "lobby"
        return {"status": "ok", "game": _copy(game)}

def join(chat_id, game_id, user_id, name):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id or game["state"] != "lobby":
            return {"status": "closed"}
        info = MODES[game["mode"]]
        if user_id in game["players"]:
            return {"status": "already", "game": _copy(game)}
        if len(game["players"]) >= info["max"]:
            return {"status": "full", "game": _copy(game)}
        game["players"][user_id] = {"name": name or "Player", "team": None}
        return {"status": "ok", "game": _copy(game)}

def leave(chat_id, game_id, user_id):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id or game["state"] != "lobby":
            return {"status": "closed"}
        if user_id not in game["players"]:
            return {"status": "not_player"}
        if user_id == game["owner_id"]:
            return {"status": "owner"}
        game["players"].pop(user_id, None)
        return {"status": "ok", "game": _copy(game)}

def can_start(game):
    if not game or game.get("state") != "lobby" or not game.get("mode"):
        return False
    info = MODES[game["mode"]]
    count = len(game["players"])
    return info["min"] <= count <= info["max"]

def start_round(chat_id, game_id, duration=90):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id:
            return None
        if game["state"] == "lobby":
            if not can_start(game):
                return None
            if game["mode"] == "versus":
                ids = list(game["players"])
                random.shuffle(ids)
                for index, uid in enumerate(ids):
                    game["players"][uid]["team"] = "red" if index < 2 else "blue"
        elif game["state"] != "between":
            return None
        if game["round_no"] >= game["total_rounds"]:
            return None
        game["round_no"] += 1
        game["challenge"] = _pick_challenge(game)
        game["answers"] = {}
        game["team_scores"] = {"red": 0, "blue": 0}
        game["state"] = "playing"
        game["ends_at"] = time.time() + duration
        return _copy(game)

def answer(chat_id, game_id, user_id, choice):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id or game["state"] != "playing" or time.time() >= game["ends_at"]:
            return {"status": "closed"}
        if user_id not in game["players"]:
            return {"status": "not_player"}
        if user_id in game["answers"]:
            return {"status": "already"}
        if choice not in ("a", "b"):
            return {"status": "invalid"}
        game["answers"][user_id] = choice
        return {"status": "ok", "game": _copy(game)}

def finish_round(chat_id, game_id):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id or game["state"] != "playing":
            return None
        challenge = game.get("challenge") or {}
        answers = game.get("answers", {})
        success = False
        winners = []
        round_winner = None
        if challenge.get("kind") == "sync":
            values = list(answers.values())
            success = len(values) == len(game["players"]) and len(set(values)) == 1
            if success:
                winners = list(game["players"])
        elif game.get("mode") == "versus":
            correct = challenge.get("answer")
            scores = {"red": 0, "blue": 0}
            for uid, choice in answers.items():
                if choice == correct:
                    team = game["players"][uid].get("team")
                    if team:
                        scores[team] += 1
            game["team_scores"] = scores
            if scores["red"] > scores["blue"]:
                round_winner = "red"
            elif scores["blue"] > scores["red"]:
                round_winner = "blue"
            if round_winner:
                game["match_scores"][round_winner] += 1
                winners = [uid for uid, row in game["players"].items() if row.get("team") == round_winner]
                success = True
        else:
            correct = challenge.get("answer")
            success = len(answers) == len(game["players"]) and all(choice == correct for choice in answers.values())
            if success:
                winners = list(game["players"])
        result = {
            "round": game["round_no"],
            "kind": challenge.get("kind"),
            "success": success,
            "winners": list(winners),
            "round_winner": round_winner,
            "team_scores": dict(game["team_scores"]),
        }
        game["round_results"].append(result)
        game["last_round"] = result
        game["state"] = "between"
        game["ends_at"] = None
        return _copy(game)

def match_complete(game):
    return bool(game) and game.get("round_no", 0) >= game.get("total_rounds", 5) and game.get("state") == "between"

def finish_match(chat_id, game_id):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id:
            return None
        if game["mode"] == "versus":
            red = game["match_scores"]["red"]
            blue = game["match_scores"]["blue"]
            if red > blue:
                winners = [uid for uid, row in game["players"].items() if row.get("team") == "red"]
                game["match_winner"] = "red"
            elif blue > red:
                winners = [uid for uid, row in game["players"].items() if row.get("team") == "blue"]
                game["match_winner"] = "blue"
            else:
                winners = []
                game["match_winner"] = "draw"
            game["success"] = bool(winners)
        else:
            cleared = sum(1 for row in game["round_results"] if row.get("success"))
            game["cleared_rounds"] = cleared
            game["success"] = cleared >= 3
            winners = list(game["players"]) if game["success"] else []
        game["winners"] = winners
        game["state"] = "finished"
        game["finished"] = True
        return _copy(game)

def cancel(chat_id, game_id):
    with _lock:
        game = _games.get(chat_id)
        if game and game["id"] == game_id:
            game["state"] = "finished"
            game["finished"] = True
            return _copy(game)
        return None
