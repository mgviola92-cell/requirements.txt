import random
import threading
import time
import uuid

_lock = threading.RLock()
_games = {}

MODES = {
    "duo": {"title": "CO-OP DUO", "min": 2, "max": 2},
    "squad": {"title": "CO-OP SQUAD", "min": 2, "max": 4},
    "versus": {"title": "TEAM VERSUS 2v2", "min": 4, "max": 4},
}

CHALLENGES = [
    {"kind": "quiz", "question": "Which planet is known as the Red Planet?", "options": ["Mars", "Venus"], "answer": "a"},
    {"kind": "quiz", "question": "Which is larger?", "options": ["Pacific Ocean", "Atlantic Ocean"], "answer": "a"},
    {"kind": "puzzle", "question": "Complete the pattern: 2, 4, 8, 16, ?", "options": ["24", "32"], "answer": "b"},
    {"kind": "puzzle", "question": "If CAT = 3 letters, ELEPHANT = ?", "options": ["7", "8"], "answer": "b"},
    {"kind": "sync", "question": "SYNC: Everyone pick the same side without chatting.", "options": ["LEFT", "RIGHT"], "answer": None},
]

def _copy(game):
    if not game:
        return None
    out = dict(game)
    out["players"] = {uid: dict(row) for uid, row in game["players"].items()}
    out["answers"] = dict(game.get("answers", {}))
    out["team_scores"] = dict(game.get("team_scores", {}))
    return out

def create_lobby(chat_id, owner_id, owner_name):
    with _lock:
        current = _games.get(chat_id)
        if current and not current.get("finished"):
            return False, _copy(current)
        game = {
            "id": uuid.uuid4().hex[:10], "chat_id": chat_id, "owner_id": owner_id,
            "players": {owner_id: {"name": owner_name or "Player", "team": None}},
            "mode": None, "state": "mode", "message_id": None, "challenge": None,
            "answers": {}, "team_scores": {"red": 0, "blue": 0},
            "created_at": time.time(), "ends_at": None, "finished": False,
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

def can_start(game):
    if not game or game.get("state") != "lobby" or not game.get("mode"):
        return False
    return len(game["players"]) >= MODES[game["mode"]]["min"]

def start_round(chat_id, game_id, duration=60):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id or not can_start(game):
            return None
        if game["mode"] == "versus":
            ids = list(game["players"])
            random.shuffle(ids)
            for index, uid in enumerate(ids):
                game["players"][uid]["team"] = "red" if index < 2 else "blue"
        challenge = dict(random.choice(CHALLENGES))
        game["challenge"] = challenge
        game["answers"] = {}
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

def finish(chat_id, game_id):
    with _lock:
        game = _games.get(chat_id)
        if not game or game["id"] != game_id:
            return None
        challenge = game.get("challenge") or {}
        answers = game.get("answers", {})
        success = False
        winners = []
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
            if scores["red"] != scores["blue"]:
                winning_team = "red" if scores["red"] > scores["blue"] else "blue"
                winners = [uid for uid, row in game["players"].items() if row.get("team") == winning_team]
                success = True
        else:
            correct = challenge.get("answer")
            success = len(answers) == len(game["players"]) and all(choice == correct for choice in answers.values())
            if success:
                winners = list(game["players"])
        game["success"] = success
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
