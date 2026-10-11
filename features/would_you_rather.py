"""Would You Rather: group voting with reproducible scenario combinations."""
import hashlib
import random
import threading
import time
import uuid
from datetime import datetime, timezone
from core.sessions import start_session, end_session
from core.rewards import add_bonus_points
from database.db import get_db_connection
from data.wyr_expansion import TOTAL as EXPANDED_TOTAL, choices_at

# Explicit matched trade-offs, not random unrelated word fragments.
PAIRS = [
("fly anywhere", "become invisible"), ("pause time", "rewind time"),
("read minds", "see the future"), ("talk to animals", "understand every language"),
("visit the moon", "explore the deep ocean"), ("travel to the past", "visit the future"),
("teleport", "run at super speed"), ("control the weather", "control gravity"),
("have a robot assistant", "have an AI tutor"), ("own a spaceship", "own a submarine"),
("have unlimited mobile data", "have unlimited device battery"),
("never lag in games", "never lose game progress"), ("master every game", "invent a new game"),
("play games with friends all night", "watch movies with friends all night"),
("live inside a fantasy RPG", "live inside a sci-fi game"),
("have perfect memory", "learn new skills instantly"), ("never need to charge devices", "never need Wi-Fi"),
("design the next viral game", "design the next viral app"),
("have a pet dragon", "have a pet phoenix"), ("live in a sky castle", "live in an underwater city"),
("explore a hidden temple", "discover a new planet"), ("solve a famous mystery", "find a lost city"),
("be a famous inventor", "be a famous explorer"), ("have a magical backpack", "have magical shoes"),
("control fire", "control ice"), ("breathe underwater", "walk on clouds"),
("have a treehouse mansion", "have a houseboat mansion"), ("live in the mountains", "live by the sea"),
("know every musical instrument", "speak every language"), ("be a great artist", "be a great musician"),
("have an extra hour each day", "have one extra day each week"),
("always find lost things", "never forget important things"), ("be able to draw anything", "be able to build anything"),
("have an endless library", "have an endless movie collection"),
("cook amazing meals", "bake amazing desserts"), ("eat your favorite breakfast", "eat your favorite dinner"),
("travel by floating train", "travel by flying car"), ("camp under the stars", "stay in a glass observatory"),
("meet a friendly alien", "meet a time traveler"), ("discover a new animal", "discover a new island"),
("learn astronomy", "learn archaeology"), ("build a small robot", "build a small satellite"),
("visit a giant aquarium", "visit a planetarium"), ("explore a rainforest", "explore a coral reef"),
("have a cozy reading room", "have a private gaming room"), ("win a team trivia contest", "win a team puzzle contest"),
("create your own comic", "create your own animation"), ("master chess", "master speed cubing"),
("remember every dream", "choose what you dream"), ("have your own theme park", "have your own museum"),
("be able to fix any computer", "be able to repair any bicycle"), ("plant a giant garden", "build a giant greenhouse"),
("visit every national park", "visit every major museum"), ("watch a meteor shower", "watch an eclipse"),
("explore an ice cave", "explore a lava cave"), ("ride a giant friendly turtle", "ride a giant friendly bird"),
("have a talking map", "have a talking compass"), ("invent a clean energy source", "invent a pollution-cleaning machine"),
("be amazing at math", "be amazing at coding"), ("learn photography", "learn filmmaking"),
("lead a space mission", "lead an ocean expedition"), ("have a home observatory", "have a home recording studio"),
("build your own mini arcade", "build your own mini cinema"), ("find hidden treasure", "decode an ancient message"),
("fly a hot air balloon", "sail a tall ship"), ("see dinosaurs safely", "see a future city safely"),
("have a magical sketchbook", "have a magical notebook"), ("learn to play piano", "learn to play violin"),
("be the fastest puzzle solver", "be the fastest quiz solver"), ("create a new sport", "create a new board game"),
("visit a robot festival", "visit a science festival"), ("explore an enchanted forest", "explore a floating city"),
("have a hologram screen", "have a pocket-sized projector"), ("get a surprise book every week", "get a surprise game every week"),
("have a sunrise view", "have a sunset view"), ("live in a quiet village", "live in a busy futuristic city"),
("collect rare fossils", "collect rare meteorites"), ("make a documentary", "write a novel"),
("be a park ranger", "be a marine biologist"), ("learn to design robots", "learn to design spacecraft"),
("have a self-cleaning room", "have a self-organizing backpack"), ("meet your favorite fictional hero", "visit your favorite fictional world"),
("have a garden on your roof", "have a pond in your yard"), ("explore mountains by train", "explore islands by boat"),
]
MYANMAR_PAIRS = tuple(tuple(line.split("|", 1)) for line in "ဘယ်နေရာမဆို ပျံသန်းနိုင်မယ်|ကိုယ်ပျောက်နိုင်မယ်\nအချိန်ကို ရပ်ထားနိုင်မယ်|အချိန်ကို နောက်ပြန်လှည့်နိုင်မယ်\nလူတွေရဲ့စိတ်ကို ဖတ်နိုင်မယ်|အနာဂတ်ကို မြင်နိုင်မယ်\nတိရစ္ဆာန်တွေနဲ့ စကားပြောနိုင်မယ်|ဘာသာစကားအားလုံး နားလည်မယ်\nလပေါ်သွားမယ်|ပင်လယ်အနက်ဆုံးကို စူးစမ်းမယ်\nအတိတ်ကို သွားမယ်|အနာဂတ်ကို သွားမယ်\nချက်ချင်း နေရာရွှေ့နိုင်မယ်|အလွန်မြန်မြန် ပြေးနိုင်မယ်\nရာသီဥတုကို ထိန်းချုပ်မယ်|ဆွဲငင်အားကို ထိန်းချုပ်မယ်\nစက်ရုပ်အကူရှိမယ်|AI ဆရာရှိမယ်\nအာကာသယာဉ်ပိုင်မယ်|ရေငုပ်သင်္ဘောပိုင်မယ်\nမိုဘိုင်းဒေတာ အကန့်အသတ်မရှိသုံးမယ်|ဖုန်းဘက်ထရီ အမြဲပြည့်နေမယ်\nဂိမ်းဆော့တိုင်း လုံးဝမလေးတော့ဘူး|ဂိမ်းတိုးတက်မှု ဘယ်တော့မှ မပျောက်ဘူး\nဂိမ်းတိုင်း ကျွမ်းကျင်မယ်|ဂိမ်းအသစ် တီထွင်မယ်\nသူငယ်ချင်းတွေနဲ့ တစ်ညလုံးဂိမ်းဆော့မယ်|သူငယ်ချင်းတွေနဲ့ တစ်ညလုံးရုပ်ရှင်ကြည့်မယ်\nမှော်ဆန်တဲ့ RPG ကမ္ဘာထဲနေမယ်|အနာဂတ်သိပ္ပံဂိမ်းကမ္ဘာထဲနေမယ်\nအရာရာ မှတ်မိမယ်|ပညာရပ်အသစ် ချက်ချင်းတတ်မယ်\nစက်တွေ ဘယ်တော့မှ အားသွင်းစရာမလိုဘူး|Wi-Fi ဘယ်တော့မှ မလိုတော့ဘူး\nနာမည်ကြီးဂိမ်း တီထွင်မယ်|နာမည်ကြီး App တီထွင်မယ်\nနဂါးလေးတစ်ကောင် မွေးမယ်|ဖီးနစ်ငှက်တစ်ကောင် မွေးမယ်\nမိုးပေါ်ရဲတိုက်မှာနေမယ်|ရေအောက်မြို့မှာနေမယ်\nလျှို့ဝှက်ဘုရားကျောင်းကို စူးစမ်းမယ်|ဂြိုဟ်အသစ် ရှာတွေ့မယ်\nနာမည်ကြီးပဟေဠိ ဖြေရှင်းမယ်|ပျောက်ဆုံးမြို့ကို ရှာတွေ့မယ်\nနာမည်ကြီးတီထွင်ရှင်ဖြစ်မယ်|နာမည်ကြီးစူးစမ်းရှာဖွေသူဖြစ်မယ်\nမှော်ကျောပိုးအိတ်ရမယ်|မှော်ဖိနပ်ရမယ်\nမီးကိုထိန်းချုပ်မယ်|ရေခဲကိုထိန်းချုပ်မယ်\nရေအောက်မှာ အသက်ရှူမယ်|တိမ်ပေါ် လမ်းလျှောက်မယ်\nသစ်ပင်ပေါ် အိမ်ကြီးရှိမယ်|ရေပေါ်အိမ်ကြီးရှိမယ်\nတောင်ပေါ်မှာနေမယ်|ပင်လယ်ကမ်းစပ်မှာနေမယ်\nတူရိယာအားလုံး တီးတတ်မယ်|ဘာသာစကားအားလုံး ပြောတတ်မယ်\nပန်းချီဆရာကောင်းဖြစ်မယ်|ဂီတပညာရှင်ကောင်းဖြစ်မယ်\nနေ့တိုင်း အချိန်တစ်နာရီပိုရမယ်|အပတ်တိုင်း တစ်ရက်ပိုရမယ်\nပျောက်တဲ့ပစ္စည်း အမြဲရှာတွေ့မယ်|အရေးကြီးတာ ဘယ်တော့မှမမေ့ဘူး\nဘာမဆို ပုံဆွဲနိုင်မယ်|ဘာမဆို တည်ဆောက်နိုင်မယ်\nစာကြည့်တိုက်အဆုံးမရှိရှိမယ်|ရုပ်ရှင်စုဆောင်းမှုအဆုံးမရှိရှိမယ်\nဟင်းချက် အရမ်းတော်မယ်|မုန့်ဖုတ် အရမ်းတော်မယ်\nအကြိုက်ဆုံးမနက်စာကို ရွေးမယ်|အကြိုက်ဆုံးညစာကို ရွေးမယ်\nပျံသန်းနေတဲ့ရထားစီးမယ်|ပျံကားစီးမယ်\nကြယ်တွေအောက် စခန်းချမယ်|မှန်လုံကြယ်ကြည့်ခန်းမှာအိပ်မယ်\nမိတ်ဆွေဂြိုဟ်သားနဲ့ တွေ့မယ်|အချိန်ခရီးသွားနဲ့ တွေ့မယ်\nတိရစ္ဆာန်မျိုးစိတ်အသစ် ရှာတွေ့မယ်|ကျွန်းအသစ် ရှာတွေ့မယ်\nနက္ခတ္တဗေဒ လေ့လာမယ်|ရှေးဟောင်းသုတေသန လေ့လာမယ်\nစက်ရုပ်အသေးလေး တည်ဆောက်မယ်|ဂြိုဟ်တုအသေးလေး တည်ဆောက်မယ်\nငါးပြတိုက်ကြီး သွားမယ်|ကြယ်တာရာပြတိုက် သွားမယ်\nမိုးသစ်တောကို စူးစမ်းမယ်|သန္တာကျောက်တန်းကို စူးစမ်းမယ်\nစာဖတ်ခန်းအေးအေးလေးရှိမယ်|ကိုယ်ပိုင်ဂိမ်းခန်းရှိမယ်\nအဖွဲ့လိုက် Trivia ပြိုင်ပွဲနိုင်မယ်|အဖွဲ့လိုက်ပဟေဠိပြိုင်ပွဲနိုင်မယ်\nကိုယ်ပိုင်ကာတွန်းရေးမယ်|ကိုယ်ပိုင် Animation ဖန်တီးမယ်\nစစ်တုရင်ကျွမ်းကျင်မယ်|Rubik's Cube မြန်မြန်ဖြေနိုင်မယ်\nအိပ်မက်တိုင်းမှတ်မိမယ်|အိပ်မက်ကို စိတ်ကြိုက်ရွေးနိုင်မယ်\nကိုယ်ပိုင်ပျော်ပွဲရွှင်ပွဲဥယျာဉ်ရှိမယ်|ကိုယ်ပိုင်ပြတိုက်ရှိမယ်\nကွန်ပျူတာတိုင်းပြင်တတ်မယ်|စက်ဘီးတိုင်းပြင်တတ်မယ်\nဥယျာဉ်ကြီး စိုက်မယ်|ဖန်လုံအိမ်ကြီး တည်ဆောက်မယ်\nအမျိုးသားဥယျာဉ်အားလုံး သွားမယ်|ပြတိုက်ကြီးအားလုံး သွားမယ်\nကြယ်ကြွေတာကြည့်မယ်|နေကြတ်တာကြည့်မယ်\nရေခဲဂူထဲ စူးစမ်းမယ်|ချော်ရည်ဂူထဲ စူးစမ်းမယ်\nလိမ္မာတဲ့လိပ်ကြီးစီးမယ်|လိမ္မာတဲ့ငှက်ကြီးစီးမယ်\nစကားပြောတတ်တဲ့မြေပုံရှိမယ်|စကားပြောတတ်တဲ့အိမ်မြှောင်ရှိမယ်\nသန့်ရှင်းတဲ့စွမ်းအင် တီထွင်မယ်|လေထုသန့်စင်စက် တီထွင်မယ်\nသင်္ချာမှာ အရမ်းတော်မယ်|Coding မှာ အရမ်းတော်မယ်\nဓာတ်ပုံပညာသင်မယ်|ရုပ်ရှင်ဖန်တီးပညာသင်မယ်\nအာကာသခရီးကို ဦးဆောင်မယ်|သမုဒ္ဒရာစူးစမ်းရေး ဦးဆောင်မယ်\nကိုယ်ပိုင်ကြယ်ကြည့်စင်ရှိမယ်|ကိုယ်ပိုင်အသံသွင်းခန်းရှိမယ်\nကိုယ်ပိုင်ဂိမ်းဆိုင်လေးတည်မယ်|ကိုယ်ပိုင်ရုပ်ရှင်ရုံလေးတည်မယ်\nလျှို့ဝှက်ရတနာ ရှာတွေ့မယ်|ရှေးဟောင်းစာဝှက် ဖော်နိုင်မယ်\nမိုးပျံပူဖောင်းစီးမယ်|ရွက်သင်္ဘောကြီးစီးမယ်\nဒိုင်နိုဆောတွေကို ဘေးကင်းကင်းကြည့်မယ်|အနာဂတ်မြို့ကို ဘေးကင်းကင်းကြည့်မယ်\nမှော်ပုံဆွဲစာအုပ်ရှိမယ်|မှော်မှတ်စုစာအုပ်ရှိမယ်\nပီယာနိုတီးတတ်မယ်|ဗိုင်အိုလင်တီးတတ်မယ်\nပဟေဠိဖြေ အမြန်ဆုံးဖြစ်မယ်|ဉာဏ်စမ်းဖြေ အမြန်ဆုံးဖြစ်မယ်\nအားကစားအသစ် တီထွင်မယ်|ဘုတ်ဂိမ်းအသစ် တီထွင်မယ်\nစက်ရုပ်ပွဲတော်သွားမယ်|သိပ္ပံပွဲတော်သွားမယ်\nမှော်သစ်တောကို စူးစမ်းမယ်|မိုးပေါ်ပျံမြို့ကို စူးစမ်းမယ်\nHologram Screen ရမယ်|အိတ်ဆောင် Projector ရမယ်\nအပတ်တိုင်း စာအုပ်အံ့အားသင့်လက်ဆောင်ရမယ်|အပတ်တိုင်း ဂိမ်းအံ့အားသင့်လက်ဆောင်ရမယ်\nနေထွက်ချိန်မြင်ကွင်းရမယ်|နေဝင်ချိန်မြင်ကွင်းရမယ်\nတိတ်ဆိတ်တဲ့ရွာလေးမှာနေမယ်|ခေတ်မီမြို့ကြီးမှာနေမယ်\nရှားပါးကျောက်ဖြစ်ရုပ်ကြွင်းစုမယ်|ရှားပါးဥက္ကာခဲစုမယ်\nမှတ်တမ်းရုပ်ရှင်ရိုက်မယ်|ဝတ္ထုရေးမယ်\nသဘာဝဥယျာဉ်စောင့်ဖြစ်မယ်|ပင်လယ်ဇီဝဗေဒပညာရှင်ဖြစ်မယ်\nစက်ရုပ်ဒီဇိုင်းပညာသင်မယ်|အာကာသယာဉ်ဒီဇိုင်းပညာသင်မယ်\nအလိုအလျောက်သန့်ရှင်းတဲ့အခန်းရှိမယ်|ပစ္စည်းတွေ အလိုအလျောက်စီတဲ့အိတ်ရှိမယ်\nအကြိုက်ဆုံးဇာတ်ကောင်နဲ့တွေ့မယ်|အကြိုက်ဆုံးစိတ်ကူးယဉ်ကမ္ဘာထဲသွားမယ်\nခေါင်မိုးပေါ်ဥယျာဉ်ရှိမယ်|အိမ်ခြံထဲမှာ ရေကန်ရှိမယ်\nတောင်တန်းတွေကို ရထားနဲ့လည်မယ်|ကျွန်းတွေကို လှေနဲ့လည်မယ်".splitlines())
# One meaningful question per distinct pair; do not inflate question counts
# with repetitive birthday/holiday/condition wording.
CAPACITY = len(MYANMAR_PAIRS) + EXPANDED_TOTAL
_lock = threading.RLock()
_rounds = {}
_poll_rounds = {}
_recent_questions = {}
_recent_order = {}
_auto_activity = {}
_auto_threshold = {}
_auto_last = {}
_DURATION = (45, 120)

def generate(rng=None):
    rng = rng or random
    return generate_by_index(rng.randrange(CAPACITY))

def generate_by_index(ix):
    if not 0 <= ix < CAPACITY:
        raise ValueError("invalid scenario index")
    if ix < len(MYANMAR_PAIRS):
        a, b = MYANMAR_PAIRS[ix]
        question_id = "WYR-MM-" + str(ix)  # stable legacy IDs
    else:
        category, a, b = choices_at(ix - len(MYANMAR_PAIRS))
        question_id = "WYR-CAT-" + str(ix - len(MYANMAR_PAIRS))
    question = "🎲 Would You Rather?\n\nမင်းသာ တစ်ခုတည်း ရွေးခွင့်ရမယ်ဆို ဘယ်ဟာကို ရွေးမလဲ?"
    if len(question) > 300 or len(a) > 100 or len(b) > 100:
        raise ValueError("Telegram Poll text too long")
    return {"id": question_id, "question": question,
            "options": (a, b), "category": "scenario"}


def initialize_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS wyr_rounds (
                    chat_id BIGINT PRIMARY KEY, round_id TEXT NOT NULL,
                    question_id TEXT NOT NULL, question TEXT NOT NULL,
                    option_a TEXT NOT NULL, option_b TEXT NOT NULL,
                    ends_at TIMESTAMPTZ NOT NULL, message_id BIGINT,
                    status TEXT NOT NULL DEFAULT 'active')""")
                cur.execute("""ALTER TABLE wyr_rounds
                    ADD COLUMN IF NOT EXISTS poll_id TEXT""")
                cur.execute("""ALTER TABLE wyr_rounds
                    ADD COLUMN IF NOT EXISTS owner_id BIGINT""")
                cur.execute("""CREATE TABLE IF NOT EXISTS wyr_votes (
                    chat_id BIGINT NOT NULL, round_id TEXT NOT NULL,
                    user_id BIGINT NOT NULL, choice SMALLINT NOT NULL,
                    PRIMARY KEY(chat_id,round_id,user_id))""")
                cur.execute("""CREATE TABLE IF NOT EXISTS wyr_history (
                    chat_id BIGINT NOT NULL, question_id TEXT NOT NULL,
                    used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY(chat_id,question_id))""")
        return True
    except Exception as exc:
        print("WYR database init:",exc)
        return False

_db_ready=False
def _next_question(chat_id):
    recent = _recent_questions.setdefault(chat_id, set())
    order = _recent_order.setdefault(chat_id, [])
    for _ in range(35):
        q=generate()
        if q["id"] in recent:continue
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO wyr_history(chat_id,question_id) VALUES (%s,%s)
                        ON CONFLICT DO NOTHING RETURNING question_id""",(chat_id,q["id"]))
                    inserted=cur.fetchone()
            if not inserted:continue
        except Exception as exc:
            print("WYR history:",exc)
            return None
        recent.add(q["id"])
        order.append(q["id"])
        if len(order)>300:recent.discard(order.pop(0))
        return q
    return None

def register(bot):
    global _db_ready
    _db_ready=initialize_db()

    def stop(chat_id, gid, *, force=False):
        with _lock:
            g=_rounds.get(chat_id)
            if not g or g["id"]!=gid:
                return False
            if not force and time.time()<g["ends"]:
                return False
            try:
                result=bot.stop_poll(chat_id,g["message_id"])
            except Exception as exc:
                print("WYR stop_poll:",exc)
                return False  # do not announce success if Telegram did not close poll
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE wyr_rounds SET status='finished' WHERE chat_id=%s AND round_id=%s",
                                    (chat_id,gid))
            except Exception as exc:
                print("WYR finish storage:",exc)
            _poll_rounds.pop(g["poll_id"],None)
            _rounds.pop(chat_id,None)
            end_session(chat_id,"would_you_rather")

        return True

    def wait_finish(chat_id,gid):
        while True:
            with _lock:
                g=_rounds.get(chat_id)
                if not g or g["id"]!=gid:return
                remaining=g["ends"]-time.time()
            if remaining<=0:break
            time.sleep(min(10,max(1,remaining)))
        stop(chat_id,gid)

    def spawn(chat_id, owner_id=None):
        if not _db_ready:return False
        with _lock:
            if chat_id in _rounds:return False
            duration=random.randint(*_DURATION)
            ok,_=start_session(chat_id,"would_you_rather",duration=duration+15)
            if not ok:return False
            q=_next_question(chat_id)
            if not q:
                end_session(chat_id,"would_you_rather")
                return False
            gid=uuid.uuid4().hex[:12]
            ends=time.time()+duration
            try:
                sent=bot.send_poll(chat_id,q["question"],list(q["options"]),
                    is_anonymous=False,allows_multiple_answers=False,
                    type="regular")
                poll_id=sent.poll.id
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""INSERT INTO wyr_rounds
                          (chat_id,round_id,question_id,question,option_a,option_b,
                           ends_at,message_id,poll_id,owner_id,status)
                          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')
                          ON CONFLICT (chat_id) DO UPDATE SET
                           round_id=EXCLUDED.round_id,question_id=EXCLUDED.question_id,
                           question=EXCLUDED.question,option_a=EXCLUDED.option_a,
                           option_b=EXCLUDED.option_b,ends_at=EXCLUDED.ends_at,
                           message_id=EXCLUDED.message_id,poll_id=EXCLUDED.poll_id,
                           owner_id=EXCLUDED.owner_id,status='active'""",
                          (chat_id,gid,q["id"],q["question"],*q["options"],
                           datetime.fromtimestamp(ends,timezone.utc),
                           sent.message_id,poll_id,owner_id))
            except Exception as exc:
                print("WYR start:",exc)
                if "sent" in locals():
                    try:bot.stop_poll(chat_id,sent.message_id)
                    except Exception:pass
                end_session(chat_id,"would_you_rather")
                return False
            g={"id":gid,"chat_id":chat_id,"owner_id":owner_id,"poll_id":poll_id,
               "message_id":sent.message_id,"ends":ends}
            _rounds[chat_id]=g
            _poll_rounds[poll_id]=chat_id
        threading.Thread(target=wait_finish,args=(chat_id,gid),daemon=True).start()
        return True

    # Restore polls and owner after Render restart. Old keyboard-era rounds
    # have no poll_id and are not reactivated.
    if _db_ready:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""SELECT chat_id,round_id,EXTRACT(EPOCH FROM ends_at),
                           message_id,poll_id,owner_id
                           FROM wyr_rounds WHERE status='active'""")
                    rows=cur.fetchall()
            for cid,gid,ends,mid,pid,owner in rows:
                if not pid or ends<=time.time():
                    if pid:
                        try:bot.stop_poll(cid,mid)
                        except Exception:pass
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE wyr_rounds SET status='finished' WHERE chat_id=%s AND round_id=%s",(cid,gid))
                    continue
                ok,_=start_session(cid,"would_you_rather",duration=float(ends)-time.time()+15)
                if not ok:continue
                g={"id":gid,"chat_id":cid,"owner_id":owner,"poll_id":pid,
                   "message_id":mid,"ends":float(ends)}
                with _lock:
                    _rounds[cid]=g
                    _poll_rounds[pid]=cid
                threading.Thread(target=wait_finish,args=(cid,gid),daemon=True).start()
        except Exception as exc:print("WYR recovery:",exc)

    @bot.message_handler(commands=["wyr","wouldyourather"])
    def wyr_command(message):
        if message.chat.type not in ("group","supergroup"):return
        if not spawn(message.chat.id,owner_id=message.from_user.id):
            bot.reply_to(message,"🎮 အခု Round တစ်ခုရှိနေနိုင်ပါတယ်။ ခဏနေပြီး ထပ်စမ်းပါ။")

    @bot.message_handler(commands=["wyrstop"])
    def wyr_stop_command(message):
        if message.chat.type not in ("group","supergroup"):return
        with _lock:
            g=_rounds.get(message.chat.id)
            if not g:
                response="❌ ရပ်စရာ WYR Poll မရှိသေးဘူး။"
            elif g["owner_id"] is None:
                response="🤖 Auto WYR Poll ကတော့ အချိန်ပြည့်မှ ပိတ်ပါမယ်။"
            elif g["owner_id"]!=message.from_user.id:
                response="🔒 ဒီ Poll ကို /wyr နဲ့ စခဲ့တဲ့သူပဲ ရပ်လို့ရတယ်။"
            else:
                response=None if stop(message.chat.id,g["id"],force=True) else "❌ Poll ပိတ်မရသေးပါ။ ထပ်စမ်းပါ။"
        if response:
            bot.reply_to(message,response)

    @bot.poll_answer_handler(func=lambda ans:True)
    def wyr_poll_answer(ans):
        with _lock:
            cid=_poll_rounds.get(ans.poll_id)
            if cid is None:return
            g=_rounds.get(cid)
            if not g or g["poll_id"]!=ans.poll_id or time.time()>=g["ends"]:return
            if len(ans.option_ids)!=1:
                # Removing a vote is handled by Telegram; it cannot earn points.
                # We only reward the first ever recorded selection.
                return
            choice=int(ans.option_ids[0])
            if choice not in (0,1):return
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""INSERT INTO wyr_votes(chat_id,round_id,user_id,choice)
                               VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING
                               RETURNING user_id""",(cid,g["id"],ans.user.id,choice))
                        first=cur.fetchone() is not None
                        if not first:
                            cur.execute("""UPDATE wyr_votes SET choice=%s
                                WHERE chat_id=%s AND round_id=%s AND user_id=%s""",
                                (choice,cid,g["id"],ans.user.id))
            except Exception as exc:
                print("WYR poll answer storage:",exc)
                return
        if first:
            try:add_bonus_points(cid,ans.user.id,1,reason="would_you_rather_vote")
            except Exception as exc:print("WYR participation reward:",exc)

    @bot.message_handler(func=lambda m:True,content_types=["text"])
    def wyr_activity(m):
        from telebot.handler_backends import ContinueHandling
        if (m.chat.type in ("group","supergroup") and m.from_user
            and not m.from_user.is_bot and m.text and not m.text.startswith("/")):
            cid=m.chat.id
            count=_auto_activity.get(cid,0)+1
            threshold=_auto_threshold.setdefault(cid,random.randint(65,170))
            if count>=threshold:
                _auto_activity[cid]=0
                _auto_threshold[cid]=random.randint(65,170)
                if time.monotonic()-_auto_last.get(cid,0)>1800 and random.random()<0.30:
                    if spawn(cid):_auto_last[cid]=time.monotonic()
            else:_auto_activity[cid]=count
        return ContinueHandling()
