import random
import threading
import time
import uuid

_lock = threading.RLock()
_games = {}

QUESTIONS = [
    ("🍕", "Pizza or Burger?", "Pizza", "Burger"),
    ("🌙", "Night owl or Early bird?", "Night", "Morning"),
    ("🎮", "Gaming or Movies?", "Gaming", "Movies"),
    ("🏖️", "Beach or Mountains?", "Beach", "Mountains"),
    ("☕", "Coffee or Tea?", "Coffee", "Tea"),
    ("🐱", "Cats or Dogs?", "Cats", "Dogs"),
    ("🎵", "Music or Podcasts?", "Music", "Podcasts"),
    ("💬", "Texting or Calling?", "Text", "Call"),
]

def _copy(g):
    if not g: return None
    out=dict(g); out["players"]={uid:dict(row) for uid,row in g["players"].items()}
    return out

def start(chat_id,duration=90):
    with _lock:
        cur=_games.get(chat_id)
        if cur and not cur.get("finished"): return False,_copy(cur)
        emoji,question,left,right=random.choice(QUESTIONS); now=time.time()
        g={"id":uuid.uuid4().hex[:10],"chat_id":chat_id,"emoji":emoji,"question":question,
           "left":left,"right":right,"players":{},"started_at":now,"ends_at":now+duration,
           "message_id":None,"finished":False}
        _games[chat_id]=g
        return True,_copy(g)

def get(chat_id):
    with _lock: return _copy(_games.get(chat_id))

def set_message(chat_id,game_id,message_id):
    with _lock:
        g=_games.get(chat_id)
        if not g or g["id"]!=game_id:return False
        g["message_id"]=message_id; return True

def choose(chat_id,game_id,user_id,name,choice):
    with _lock:
        g=_games.get(chat_id)
        if not g or g["id"]!=game_id or g.get("finished") or time.time()>=g["ends_at"]:
            return {"status":"closed"}
        if choice not in ("a","b"):return {"status":"invalid"}
        if user_id in g["players"]:return {"status":"already"}
        g["players"][user_id]={"name":name or "Player","choice":choice}
        return {"status":"ok","game":_copy(g)}

def finish(chat_id,game_id):
    with _lock:
        g=_games.get(chat_id)
        if not g or g["id"]!=game_id:return None
        g["finished"]=True; return _copy(g)

def pairs(game):
    groups={"a":[],"b":[]}
    for uid,row in (game or {}).get("players",{}).items():
        groups[row["choice"]].append((uid,row["name"]))
    random.shuffle(groups["a"]); random.shuffle(groups["b"])
    made=[]
    for key in ("a","b"):
        rows=groups[key]
        for i in range(0,len(rows)-1,2):made.append((key,rows[i],rows[i+1]))
    return made
