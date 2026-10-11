"""Would You Rather: group voting with reproducible scenario combinations."""
import hashlib
import random
import threading
import time
import uuid
from core.sessions import start_session, end_session
from core.rewards import add_bonus_points
from database.db import get_db_connection

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
CONTEXTS = ("on a surprise weekend","during a school holiday","for a special adventure",
            "with your best friends","during a big festival","on your next birthday",
            "for an exciting challenge","on a once-in-a-lifetime trip")
TWISTS = ("but only for one day","but only once a month","but you must decide right now",
          "but you cannot switch later","but nobody else can choose for you",
          "but you must share the experience","but you have to plan it yourself",
          "but you only have one chance")
FRAMES = ("Would you rather {a} or {b} {context}, {twist}?",
          "Imagine you could {a} or {b} {context}, {twist}. Which would you pick?",
          "Big choice: {a} versus {b} {context}, {twist}. Which one?",
          "Your next adventure: {a} or {b} {context}, {twist}. Which would you choose?")
# 80+ paired ideas x 8 contexts x 8 twists x 4 frames > 20,000 variants.
CAPACITY = len(PAIRS) * len(CONTEXTS) * len(TWISTS) * len(FRAMES)
_lock = threading.RLock()
_rounds = {}
_last_edits = {}
_recent_questions = {}
_recent_order = {}
_auto_activity = {}
_auto_threshold = {}
_auto_last = {}
_DURATION = (300, 900)


def generate(rng=None):
    rng = rng or random
    ix = rng.randrange(CAPACITY)
    return generate_by_index(ix)


def generate_by_index(ix):
    if not 0 <= ix < CAPACITY:
        raise ValueError("invalid scenario index")
    pair_idx, rest = divmod(ix, len(CONTEXTS) * len(TWISTS) * len(FRAMES))
    context_idx, rest = divmod(rest, len(TWISTS) * len(FRAMES))
    twist_idx, frame_idx = divmod(rest, len(FRAMES))
    a, b = PAIRS[pair_idx]
    context, twist = CONTEXTS[context_idx], TWISTS[twist_idx]
    question = FRAMES[frame_idx].format(a=a, b=b, context=context, twist=twist)
    return {"id": "WYR-"+str(ix), "question": question, "options": (a, b),
            "category": "scenario"}


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
        print("WYR database initialization:", exc)
        return False


def _next_question(chat_id):
    recent = _recent_questions.setdefault(chat_id, set())
    history = _recent_order.setdefault(chat_id, [])
    for _ in range(35):
        ix = random.randrange(CAPACITY)
        q = generate_by_index(ix)
        if q["id"] in recent:
            continue
        if _db_ready:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""INSERT INTO wyr_history(chat_id,question_id)
                                       VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING question_id""",
                                    (chat_id,q["id"]))
                        inserted = cur.fetchone()
                if not inserted:
                    continue
            except Exception as exc:
                print("WYR history DB:",exc)
        recent.add(q["id"])
        history.append(q["id"])
        if len(history)>300:
            recent.discard(history.pop(0))
        return q
    return None


_db_ready = False


def register(bot):
    global _db_ready
    _db_ready = initialize_db()

    def render(g, final=False):
        a,b=g["question"]["options"]
        count_a=g["a"]
        count_b=g["b"]
        total=count_a+count_b
        pa=round(100*count_a/total) if total else 0
        pb=100-pa if total else 0
        bar=lambda p: "█"*(p//10)+"░"*(10-p//10)
        t=max(0,int(g["ends"]-time.time()))
        heading="🏁 WOULD YOU RATHER — RESULT" if final else "🎲 WOULD YOU RATHER"
        text=(f"{heading}\n\n{g['question']['question']}\n\n"
              f"🅰️ {a}\n{bar(pa)} {pa}% ({count_a})\n\n"
              f"🅱️ {b}\n{bar(pb)} {pb}% ({count_b})\n\n"
              f"👥 {total} voters" + ("" if final else f"  |  ⏳ {t//60:02d}:{t%60:02d}"))
        if final and total >= 4:
            mode=int(hashlib.sha256(g["id"].encode()).hexdigest()[:4],16)
            if count_a and count_b and min(count_a,count_b)*100 <= 30*total and mode % 3 == 0:
                text+="\n\n👀 Minority Alert! The smaller team made an unusual choice."
            elif mode % 5 == 0:
                text+="\n\n💬 Debate Mode: Which choice would you defend, and why?"
        return text

    def keyboard(g):
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        k=InlineKeyboardMarkup(row_width=2)
        k.add(InlineKeyboardButton("🅰️ Option A",callback_data=f"wyr:{g['id']}:0"),
              InlineKeyboardButton("🅱️ Option B",callback_data=f"wyr:{g['id']}:1"))
        return k

    def update(g,final=False):
        try:
            bot.edit_message_text(render(g,final),chat_id=g["chat_id"],
                                  message_id=g["message_id"],
                                  reply_markup=None if final else keyboard(g))
        except Exception as exc:
            if "not modified" not in str(exc).lower():
                print("WYR edit:",exc)

    def finish(chat_id, game_id):
        with _lock:
            g=_rounds.get(chat_id)
            if not g or g["id"]!=game_id or g.get("done"):return
            if time.time()<g["ends"]:return
            g["done"]=True
            _rounds.pop(chat_id,None)
            end_session(chat_id,"would_you_rather")
            if _db_ready:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE wyr_rounds SET status='finished' WHERE chat_id=%s AND round_id=%s",
                                        (chat_id,game_id))
                except Exception as exc:print("WYR finish DB:",exc)
        update(g,final=True)

    def spawn(chat_id):
        if not _db_ready:
            return False
        with _lock:
            if chat_id in _rounds:return False
            duration=random.randint(*_DURATION)
            ok,_=start_session(chat_id,"would_you_rather",duration=duration+15)
            if not ok:return False
            q=_next_question(chat_id)
            if not q:
                end_session(chat_id,"would_you_rather")
                return False
            g={"id":uuid.uuid4().hex[:10],"chat_id":chat_id,"question":q,
               "ends":time.time()+duration,"a":0,"b":0,"message_id":None,"done":False}
            try:
                m=bot.send_message(chat_id,render(g),reply_markup=keyboard(g))
                g["message_id"]=m.message_id
                _rounds[chat_id]=g
                if _db_ready:
                    from datetime import datetime,timezone
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""INSERT INTO wyr_rounds
                             (chat_id,round_id,question_id,question,option_a,option_b,ends_at,message_id,status)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'active')
                             ON CONFLICT (chat_id) DO UPDATE SET
                             round_id=EXCLUDED.round_id,question_id=EXCLUDED.question_id,
                             question=EXCLUDED.question,option_a=EXCLUDED.option_a,
                             option_b=EXCLUDED.option_b,ends_at=EXCLUDED.ends_at,
                             message_id=EXCLUDED.message_id,status='active'""",
                             (chat_id,g["id"],q["id"],q["question"],*q["options"],
                              datetime.fromtimestamp(g["ends"],timezone.utc),g["message_id"]))
            except Exception as exc:
                print("WYR start:",exc)
                if not g.get("message_id"):
                    end_session(chat_id,"would_you_rather")
                    return False
                _rounds.pop(chat_id,None)
                end_session(chat_id,"would_you_rather")
                try:
                    bot.edit_message_text("⚠️ WYR start failed; please try again.",
                        chat_id=chat_id,message_id=g["message_id"],reply_markup=None)
                except Exception:
                    pass
                return False
        threading.Thread(target=wait_finish,args=(chat_id,g["id"]),daemon=True).start()
        return True

    def wait_finish(chat_id,gid):
        while True:
            with _lock:
                g=_rounds.get(chat_id)
                if not g or g["id"]!=gid:return
                remaining=g["ends"]-time.time()
            if remaining<=0:break
            time.sleep(min(10,max(1,remaining)))
        finish(chat_id,gid)

    # Recover recorded rounds after hosting restarts. End elapsed rounds without
    # restarting them, preserve votes from Neon for unexpired rounds.
    if _db_ready:
        try:
            from datetime import datetime,timezone
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""SELECT chat_id,round_id,question_id,question,option_a,option_b,
                                EXTRACT(EPOCH FROM ends_at),message_id FROM wyr_rounds WHERE status='active'""")
                    rows=cur.fetchall()
                    for chat_id,gid,qid,question,a,b,ends,mid in rows:
                        cur.execute("""SELECT choice,COUNT(*) FROM wyr_votes
                                       WHERE chat_id=%s AND round_id=%s GROUP BY choice""",(chat_id,gid))
                        votes=dict(cur.fetchall())
                        g={"id":gid,"chat_id":chat_id,"question":{"id":qid,"question":question,"options":(a,b)},
                           "ends":float(ends),"a":votes.get(0,0),"b":votes.get(1,0),
                           "message_id":mid,"done":False}
                        if g["ends"]<=time.time():
                            g["done"]=True
                            update(g,final=True)
                            cur.execute("UPDATE wyr_rounds SET status='finished' WHERE chat_id=%s",(chat_id,))
                        else:
                            ok,_=start_session(chat_id,"would_you_rather",duration=g["ends"]-time.time()+15)
                            if ok:
                                _rounds[chat_id]=g
                                threading.Thread(target=wait_finish,args=(chat_id,gid),daemon=True).start()
        except Exception as exc:print("WYR recovery:",exc)

    @bot.message_handler(commands=["wyr","wouldyourather"])
    def wyr_command(message):
        if message.chat.type not in ("group","supergroup"):return
        if not spawn(message.chat.id):
            bot.reply_to(message,"🎮 Another game is active, or WYR is already running.")

    @bot.callback_query_handler(func=lambda call:bool(call.data) and call.data.startswith("wyr:"))
    def wyr_callback(call):
        try:
            _,gid,choice_text=call.data.split(":")
            choice=int(choice_text)
        except (ValueError,AttributeError):
            bot.answer_callback_query(call.id,"Invalid option")
            return
        chat_id=call.message.chat.id
        uid=call.from_user.id
        with _lock:
            g=_rounds.get(chat_id)
            if not g or g["id"]!=gid or time.time()>=g["ends"] or g["done"]:
                bot.answer_callback_query(call.id,"Round already ended")
                return
            if not _db_ready:
                # Never accept unverifiable duplicates when persistent storage is absent.
                bot.answer_callback_query(call.id,"Voting temporarily unavailable")
                return
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""INSERT INTO wyr_votes(chat_id,round_id,user_id,choice)
                            VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING user_id""",
                            (chat_id,gid,uid,choice))
                        inserted=cur.fetchone()
            except Exception as exc:
                print("WYR vote DB:",exc)
                bot.answer_callback_query(call.id,"Please try again")
                return
            if not inserted:
                bot.answer_callback_query(call.id,"You have already voted")
                return
            g["a" if choice==0 else "b"]+=1
            now=time.monotonic()
            refresh=now-_last_edits.get(chat_id,0)>2.0
            if refresh:_last_edits[chat_id]=now
        bot.answer_callback_query(call.id,"✅ Vote counted")
        # One participation reward per user/round; successful DB insertion
        # guarantees repeat button presses cannot grant extra points.
        try:
            add_bonus_points(chat_id, uid, 1, reason="would_you_rather_vote")
        except Exception as exc:
            print("WYR participation reward:", exc)
        if refresh:update(g)

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
