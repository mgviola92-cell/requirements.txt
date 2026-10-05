import random
import secrets
import threading
import time
import uuid
from collections import deque

RAID_DURATION=180
BASE_DAMAGE_MIN=3
BASE_DAMAGE_MAX=8
CRIT_CHANCE_PERCENT=7
CRIT_DAMAGE_MIN=10
CRIT_DAMAGE_MAX=18
BLOCK_CHANCE_PERCENT=6
PHASE_THRESHOLDS=(75,50,25,10)
BOSS_EVENT_CHANCE_PERCENT=8
BOSS_EVENT_MIN_HITS=8
MODIFIER_DURATION_HITS=18
MODIFIER_DAMAGE_MULTIPLIERS={"rage":0.82,"exposed":1.35,"fortify":0.68}

BOSSES=[
{"name":"Slime King","emoji":"🟢","tier":"EASY","hp":650},{"name":"Cave Troll","emoji":"👹","tier":"EASY","hp":760},{"name":"Wild Golem","emoji":"🪨","tier":"EASY","hp":880},{"name":"Venom Spider","emoji":"🕷️","tier":"EASY","hp":980},{"name":"Goblin Chief","emoji":"👺","tier":"EASY","hp":1100},{"name":"Frost Wolf","emoji":"🐺","tier":"EASY","hp":1250},
{"name":"Orc Warlord","emoji":"🪓","tier":"NORMAL","hp":1500},{"name":"Stone Guardian","emoji":"🗿","tier":"NORMAL","hp":1700},{"name":"Sand Serpent","emoji":"🐍","tier":"NORMAL","hp":1900},{"name":"Dark Knight","emoji":"⚔️","tier":"NORMAL","hp":2150},{"name":"Thunder Beast","emoji":"⚡","tier":"NORMAL","hp":2400},{"name":"Swamp Hydra","emoji":"🐲","tier":"NORMAL","hp":2700},
{"name":"Inferno Giant","emoji":"🔥","tier":"HARD","hp":3100},{"name":"Abyss Reaper","emoji":"💀","tier":"HARD","hp":3500},{"name":"Storm Titan","emoji":"🌩️","tier":"HARD","hp":3900},{"name":"Ancient Hydra","emoji":"🐉","tier":"HARD","hp":4400},{"name":"Demon Lord","emoji":"😈","tier":"HARD","hp":5000},{"name":"Void Colossus","emoji":"🌌","tier":"HARD","hp":5700},
{"name":"Celestial Dragon","emoji":"🐲","tier":"LEGENDARY","hp":6500},{"name":"World Eater","emoji":"🌍","tier":"LEGENDARY","hp":7400},{"name":"Chaos Emperor","emoji":"👑","tier":"LEGENDARY","hp":8400},{"name":"Eclipse Titan","emoji":"🌑","tier":"LEGENDARY","hp":9500},{"name":"Immortal Demon","emoji":"👿","tier":"LEGENDARY","hp":10800},{"name":"Neon Destroyer","emoji":"☄️","tier":"LEGENDARY","hp":12500},
]

# Pools are deliberately large and recent picks are remembered per boss/event.
PHASE_LINES=[
"အားကောင်းတယ်ထင်နေတာလား… အခုမှစတာ။","ဒီလောက်နဲ့ ငါ့ကိုလှဲနိုင်မယ်ထင်လား။","ကောင်းတယ်… နည်းနည်းတော့နာလာပြီ။","ဆက်လာစမ်း၊ ဘယ်လောက်ခံနိုင်လဲကြည့်မယ်။",
"အုပ်စုလိုက်လာလည်း ငါမကြောက်ဘူး။","ဟေ့… အခုတော့ စိတ်ဝင်စားလာပြီ။","ငါ့ HP ကိုကြည့်ပြီး မပျော်နဲ့ဦး။","တကယ်တိုက်တတ်တာလား၊ button ပဲနှိပ်တတ်တာလား။",
"ဒီတစ်ခါတော့ မင်းတို့ကံကောင်းတာ။","အရှိန်တင်လိုက်… ငါလည်းအရှိန်တင်တော့မယ်။","နောက် Phase မှာ မငိုနဲ့။","မဆိုးဘူး… ဒါပေမယ့် မလုံလောက်သေးဘူး။",
]
LOSE_LINES=[
"အချိန်ကုန်ပြီ။ အုပ်စုလိုက်လာပြီး ဒီလောက်ပဲလား။","ငါ့ရှေ့မှာ party တစ်ခုလုံးတောင် မလုံလောက်ဘူး။","ပြန်လေ့ကျင့်ပြီးမှလာခဲ့ကြ။ ဒီတစ်ခါ ငါနိုင်တယ်။",
"ATTACK ကိုတော့တော်တော်နှိပ်တယ်… damage ကဘယ်မှာလဲ။","ဒီ Raid ကို ငါပိုင်တယ်။ နောက်တစ်ခါ ပိုကောင်းအောင်လာ။","မင်းတို့အဖွဲ့ကို ငါ့ HP ကပဲ နှုတ်ဆက်လိုက်တယ်။",
"အချိန်က မင်းတို့ကိုကယ်မပေးနိုင်ခဲ့ဘူး။","Fighters တွေများတာနဲ့ Boss မသေဘူးကွ။","ဒီနေ့တော့ ငါ့နေ့ပဲ။ ပြန်လာချင်ရင်လာခဲ့။","တံခါးက ဟိုဘက်မှာ… defeat party ရေ။",
]
WIN_LINES=[
"မဖြစ်နိုင်ဘူး… ဒီအုပ်စုက ငါ့ကိုတကယ်လှဲလိုက်တာလား။","ဒီတစ်ခါ မင်းတို့နိုင်တယ်… နောက်တစ်ခါ မလွယ်ဘူး။","ငါ့အဆုံးသတ်က ဒီလိုဖြစ်မယ်မထင်ခဲ့ဘူး။",
"ကောင်းတယ်… ဒီ victory ကို ထိုက်တန်တယ်။","ငါရှုံးပြီ။ ဒါပေမယ့် နောက် Boss က မင်းတို့ကိုစောင့်နေတယ်။","ဒီအုပ်စုကို လျှော့တွက်မိတာ ငါ့အမှားပဲ။",
"လက်ခံတယ်… ဒီ Raid ကို မင်းတို့ယူသွား။","ငါ့ HP သုည… မင်းတို့ရဲ့ teamwork ကတော့ full ပဲ။","ဒီနေ့ Champion က မင်းတို့ပဲ။","နောက်တစ်ခါတွေ့ရင် ဒီလိုလွယ်မယ်မထင်နဲ့။",
]
BOSS_ATTACK_LINES=[
"Boss က မြေပြင်ကိုထုချလိုက်တယ် — Raid party တစ်ခုလုံး လှုပ်ခါသွားတယ်!",
"Boss ရဲ့ counter attack ဝင်လာတယ် — အရှိန်မလျှော့နဲ့!",
"Boss က rage ဖြစ်လာပြီ — ဒီအချိန်က damage တင်ရမယ့်အချိန်!",
"Boss က party ကို ခြိမ်းခြောက်လိုက်တယ် — နောက်မဆုတ်နဲ့!",
"Boss ရဲ့ heavy strike ကျလာတယ် — Raid က ပိုပြင်းလာပြီ!",
"Boss က roar လုပ်လိုက်တယ် — battlefield တစ်ခုလုံး တုန်သွားတယ်!",
]
BOSS_ATTACK_EFFECTS=[
("quake","🌋 QUAKE","Boss quake ကြောင့် party damage momentum ကျသွားတယ်!",-18),
("slam","💥 HEAVY SLAM","Heavy Slam! Boss က HP နည်းနည်းပြန်တက်သွားတယ်!",28),
("roar","📣 WAR ROAR","War Roar! Boss defense တင်းလာတယ်!",0),
]
MODIFIER_LINES=[
("rage","🔥 RAGE","Boss rage ဖြစ်နေတယ် — Phase resistance ပိုပြင်းလာပြီ!"),
("exposed","💢 EXPOSED","Boss guard ပွင့်သွားတယ် — အခုအချိန် ဝိုင်းချ!"),
("fortify","🛡 FORTIFY","Boss က defense တင်လိုက်တယ် — မရပ်ဘဲ ဆက်တိုက်ချ!"),
]
_raids={}
_recent={}
_lock=threading.RLock()

def _copy(r):
    if not r:return None
    o=dict(r);o["fighters"]={u:dict(v) for u,v in r["fighters"].items()};o["thresholds_seen"]=set(r.get("thresholds_seen",set()));return o

def _phase(h,m):
    x=h/m if m else 0
    return 3 if x<=.25 else (2 if x<=.60 else 1)

def _mult(p):return {1:1.,2:.90,3:.80}.get(p,1.)

def _pick(key,pool):
    hist=_recent.setdefault(key,deque(maxlen=min(6,max(1,len(pool)-1))))
    choices=[x for x in pool if x not in hist] or list(pool)
    x=secrets.choice(choices);hist.append(x);return x

def start_raid(chat_id,duration=RAID_DURATION,boss=None):
    with _lock:
        cur=_raids.get(chat_id)
        if cur and not cur["finished"]:return False,_copy(cur)
        b=dict(boss or random.choice(BOSSES));now=time.time()
        r={"id":uuid.uuid4().hex[:10],"chat_id":chat_id,"boss":b,"hp":b["hp"],"max_hp":b["hp"],"phase":1,"fighters":{},"total_damage":0,"started_at":now,"ends_at":now+duration,"message_id":None,"finished":False,"result":None,"thresholds_seen":set(),"ending_handled":False,"event_hits":0,"modifier":None,"modifier_hits_left":0}
        _raids[chat_id]=r;return True,_copy(r)

def get_raid(chat_id):
    with _lock:
        r=_raids.get(chat_id)
        if not r:return None
        # Timeout ownership belongs to the scheduled timeout handler.
        # Reads/callbacks must not silently finish the raid before that handler
        # can run the result + unpin sequence.
        return _copy(r)

def set_message_id(chat_id,raid_id,message_id):
    with _lock:
        r=_raids.get(chat_id)
        if not r or r["id"]!=raid_id:return False
        r["message_id"]=message_id;return True

def attack(chat_id,raid_id,user_id,user_name):
    with _lock:
        r=_raids.get(chat_id)
        if not r or r["id"]!=raid_id:return {"status":"no_raid"}
        if r["finished"] or time.time()>=r["ends_at"]:
            r["finished"]=True;r["result"]=r["result"] or "timeout";return {"status":"finished","raid":_copy(r)}
        old_pct=r["hp"]/r["max_hp"]*100
        roll=secrets.randbelow(100);crit=False;blocked=False
        if roll<BLOCK_CHANCE_PERCENT:raw=0;blocked=True
        elif roll<BLOCK_CHANCE_PERCENT+CRIT_CHANCE_PERCENT:raw=secrets.randbelow(CRIT_DAMAGE_MAX-CRIT_DAMAGE_MIN+1)+CRIT_DAMAGE_MIN;crit=True
        else:raw=secrets.randbelow(BASE_DAMAGE_MAX-BASE_DAMAGE_MIN+1)+BASE_DAMAGE_MIN
        modifier=r.get("modifier")
        mod_mult=MODIFIER_DAMAGE_MULTIPLIERS.get(modifier,1.0)
        dmg=int(round(raw*_mult(r["phase"])*mod_mult))
        if raw>0:dmg=max(1,dmg)
        if r.get("modifier_hits_left",0)>0:
            r["modifier_hits_left"]-=1
            if r["modifier_hits_left"]<=0:
                r["modifier"]=None
        f=r["fighters"].setdefault(user_id,{"name":user_name or "Player","damage":0,"hits":0})
        f["name"]=user_name or f["name"];f["hits"]+=1;f["damage"]+=dmg
        r["total_damage"]+=dmg;r["hp"]=max(0,r["hp"]-dmg);r["phase"]=_phase(r["hp"],r["max_hp"])
        r["event_hits"]+=1
        new_pct=r["hp"]/r["max_hp"]*100
        reaction=None
        for t in PHASE_THRESHOLDS:
            if old_pct>t>=new_pct and t not in r["thresholds_seen"]:
                r["thresholds_seen"].add(t);reaction={"threshold":t,"text":_pick((r["boss"]["name"],"phase"),PHASE_LINES)};break
        event=None
        if not r["finished"] and r["event_hits"]>=BOSS_EVENT_MIN_HITS and secrets.randbelow(100)<BOSS_EVENT_CHANCE_PERCENT:
            r["event_hits"]=0
            if secrets.randbelow(100)<45:
                mod=secrets.choice(MODIFIER_LINES);r["modifier"]=mod[0];r["modifier_hits_left"]=MODIFIER_DURATION_HITS
                event={"kind":"modifier","title":mod[1],"text":mod[2],"hits":MODIFIER_DURATION_HITS}
            else:
                effect=secrets.choice(BOSS_ATTACK_EFFECTS)
                if effect[0]=="slam":
                    heal=min(effect[3],r["max_hp"]-r["hp"]);r["hp"]+=heal
                    event={"kind":"attack","title":effect[1],"text":effect[2],"heal":heal}
                elif effect[0]=="roar":
                    r["modifier"]="fortify";r["modifier_hits_left"]=10
                    event={"kind":"attack","title":effect[1],"text":effect[2],"hits":10}
                else:
                    # Quake is a battle event, not a player punishment/mute.
                    event={"kind":"attack","title":effect[1],"text":effect[2]}
        if r["hp"]<=0:r["finished"]=True;r["result"]="victory"
        return {"status":"ok","damage":dmg,"crit":crit,"blocked":blocked,"reaction":reaction,"event":event,"raid":_copy(r)}

def ending_line(raid):
    kind="win" if raid.get("result")=="victory" else "lose"
    return _pick((raid["boss"]["name"],kind),WIN_LINES if kind=="win" else LOSE_LINES)

def claim_ending(chat_id,raid_id):
    """Exactly one callback/timer owns the final ending sequence."""
    with _lock:
        r=_raids.get(chat_id)
        if not r or r["id"]!=raid_id or r.get("ending_handled"):
            return None
        # Never claim a live raid by mistake.
        if not r.get("finished"):
            return None
        r["ending_handled"]=True
        return _copy(r)

def finish_raid(chat_id,raid_id,result=None):
    with _lock:
        r=_raids.get(chat_id)
        if not r or r["id"]!=raid_id:return None
        r["finished"]=True;r["result"]=result or r["result"] or ("victory" if r["hp"]<=0 else "timeout");return _copy(r)

def clear_raid(chat_id):
    with _lock:return _raids.pop(chat_id,None)

def top_fighters(r,limit=3):
    fs=list((r or {}).get("fighters",{}).values());fs.sort(key=lambda x:(x["damage"],x["hits"]),reverse=True);return fs[:limit]
