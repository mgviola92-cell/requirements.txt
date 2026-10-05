import random
import secrets
import threading
import time
import uuid

RAID_DURATION = 180
BASE_DAMAGE_MIN = 2
BASE_DAMAGE_MAX = 6
CRIT_CHANCE_PERCENT = 7
CRIT_DAMAGE_MIN = 8
CRIT_DAMAGE_MAX = 15
BLOCK_CHANCE_PERCENT = 6

BOSSES = [
    {"name":"Slime King","emoji":"🟢","tier":"EASY","hp":650},{"name":"Cave Troll","emoji":"👹","tier":"EASY","hp":760},{"name":"Wild Golem","emoji":"🪨","tier":"EASY","hp":880},{"name":"Venom Spider","emoji":"🕷️","tier":"EASY","hp":980},{"name":"Goblin Chief","emoji":"👺","tier":"EASY","hp":1100},{"name":"Frost Wolf","emoji":"🐺","tier":"EASY","hp":1250},
    {"name":"Orc Warlord","emoji":"🪓","tier":"NORMAL","hp":1500},{"name":"Stone Guardian","emoji":"🗿","tier":"NORMAL","hp":1700},{"name":"Sand Serpent","emoji":"🐍","tier":"NORMAL","hp":1900},{"name":"Dark Knight","emoji":"⚔️","tier":"NORMAL","hp":2150},{"name":"Thunder Beast","emoji":"⚡","tier":"NORMAL","hp":2400},{"name":"Swamp Hydra","emoji":"🐲","tier":"NORMAL","hp":2700},
    {"name":"Inferno Giant","emoji":"🔥","tier":"HARD","hp":3100},{"name":"Abyss Reaper","emoji":"💀","tier":"HARD","hp":3500},{"name":"Storm Titan","emoji":"🌩️","tier":"HARD","hp":3900},{"name":"Ancient Hydra","emoji":"🐉","tier":"HARD","hp":4400},{"name":"Demon Lord","emoji":"😈","tier":"HARD","hp":5000},{"name":"Void Colossus","emoji":"🌌","tier":"HARD","hp":5700},
    {"name":"Celestial Dragon","emoji":"🐲","tier":"LEGENDARY","hp":6500},{"name":"World Eater","emoji":"🌍","tier":"LEGENDARY","hp":7400},{"name":"Chaos Emperor","emoji":"👑","tier":"LEGENDARY","hp":8400},{"name":"Eclipse Titan","emoji":"🌑","tier":"LEGENDARY","hp":9500},{"name":"Immortal Demon","emoji":"👿","tier":"LEGENDARY","hp":10800},{"name":"Neon Destroyer","emoji":"☄️","tier":"LEGENDARY","hp":12500},
]

_raids={}
_lock=threading.RLock()

def _copy(raid):
    if not raid: return None
    out=dict(raid)
    out["fighters"]={uid:dict(v) for uid,v in raid["fighters"].items()}
    return out

def _phase(hp,max_hp):
    ratio=hp/max_hp if max_hp else 0
    if ratio<=.25:return 3
    if ratio<=.60:return 2
    return 1

def _mult(phase):
    return {1:1.0,2:.90,3:.80}.get(phase,1.0)

def start_raid(chat_id,duration=RAID_DURATION,boss=None):
    with _lock:
        current=_raids.get(chat_id)
        if current and not current["finished"]: return False,_copy(current)
        picked=dict(boss or random.choice(BOSSES))
        now=time.time()
        raid={"id":uuid.uuid4().hex[:10],"chat_id":chat_id,"boss":picked,"hp":picked["hp"],"max_hp":picked["hp"],"phase":1,"fighters":{},"total_damage":0,"started_at":now,"ends_at":now+duration,"message_id":None,"finished":False,"result":None}
        _raids[chat_id]=raid
        return True,_copy(raid)

def get_raid(chat_id):
    with _lock:
        raid=_raids.get(chat_id)
        if not raid:return None
        if not raid["finished"] and time.time()>=raid["ends_at"]:
            raid["finished"]=True;raid["result"]="timeout"
        return _copy(raid)

def set_message_id(chat_id,raid_id,message_id):
    with _lock:
        raid=_raids.get(chat_id)
        if not raid or raid["id"]!=raid_id:return False
        raid["message_id"]=message_id;return True

def attack(chat_id,raid_id,user_id,user_name):
    with _lock:
        raid=_raids.get(chat_id)
        if not raid or raid["id"]!=raid_id:return {"status":"no_raid"}
        if raid["finished"] or time.time()>=raid["ends_at"]:
            raid["finished"]=True
            raid["result"]=raid["result"] or "timeout"
            return {"status":"finished","raid":_copy(raid)}
        # No gameplay attack cooldown: every legitimate press is accepted.
        roll=secrets.randbelow(100);crit=False;blocked=False
        if roll<BLOCK_CHANCE_PERCENT: raw=0;blocked=True
        elif roll<BLOCK_CHANCE_PERCENT+CRIT_CHANCE_PERCENT:
            raw=secrets.randbelow(CRIT_DAMAGE_MAX-CRIT_DAMAGE_MIN+1)+CRIT_DAMAGE_MIN;crit=True
        else: raw=secrets.randbelow(BASE_DAMAGE_MAX-BASE_DAMAGE_MIN+1)+BASE_DAMAGE_MIN
        damage=int(round(raw*_mult(raid["phase"])))
        if raw>0:damage=max(1,damage)
        fighter=raid["fighters"].setdefault(user_id,{"name":user_name or "Player","damage":0,"hits":0})
        fighter["name"]=user_name or fighter["name"];fighter["hits"]+=1;fighter["damage"]+=damage
        raid["total_damage"]+=damage;raid["hp"]=max(0,raid["hp"]-damage);raid["phase"]=_phase(raid["hp"],raid["max_hp"])
        if raid["hp"]<=0:raid["finished"]=True;raid["result"]="victory"
        return {"status":"ok","damage":damage,"crit":crit,"blocked":blocked,"raid":_copy(raid)}

def finish_raid(chat_id,raid_id,result=None):
    with _lock:
        raid=_raids.get(chat_id)
        if not raid or raid["id"]!=raid_id:return None
        raid["finished"]=True;raid["result"]=result or raid["result"] or ("victory" if raid["hp"]<=0 else "timeout")
        return _copy(raid)

def clear_raid(chat_id):
    with _lock:return _raids.pop(chat_id,None)

def top_fighters(raid,limit=3):
    fighters=list((raid or {}).get("fighters",{}).values())
    fighters.sort(key=lambda x:(x["damage"],x["hits"]),reverse=True)
    return fighters[:limit]
