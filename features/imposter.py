"""Imposter Protocol: Telegram text UI + private callback alerts; Neon-backed state.

One impostor, 40-second entry, fixed clue order, 60-second AFK timeout,
majority decision, impostor tie-break, and final anonymous-to-other-players
votes. No bot DM or Mini App required.
"""
import html
import json
import random
import threading
import time
import uuid

from telebot import types
from telebot.handler_backends import ContinueHandling
from core.sessions import start_session, end_session
from core.rewards import add_bonus_points
from database.db import get_db_connection
from data.imposter_words import WORDS

LOCK = threading.RLock()
JOIN_TIME = 40
TURN_TIME = 60
DECISION_TIME = 60
MAX_ROUNDS = 5
MIN_PLAYERS = 4
_schedulers_started = False

def _db_init():
    with get_db_connection() as con:
        with con.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS imposter_games (
                chat_id BIGINT PRIMARY KEY, state JSONB NOT NULL, updated_at TIMESTAMPTZ DEFAULT NOW()
            )""")
            cur.execute("""CREATE TABLE IF NOT EXISTS imposter_word_history (
                chat_id BIGINT NOT NULL, word TEXT NOT NULL,
                PRIMARY KEY(chat_id,word)
            )""")

def _load(chat_id):
    with get_db_connection() as con:
        with con.cursor() as cur:
            cur.execute("SELECT state FROM imposter_games WHERE chat_id=%s",(chat_id,))
            row=cur.fetchone()
            return row[0] if row else None

def _save(chat_id,s):
    with get_db_connection() as con:
        with con.cursor() as cur:
            cur.execute("""INSERT INTO imposter_games(chat_id,state) VALUES(%s,%s::jsonb)
                ON CONFLICT(chat_id) DO UPDATE SET state=EXCLUDED.state,updated_at=NOW()""",
                (chat_id,json.dumps(s,ensure_ascii=False)))

def _word(chat_id):
    with get_db_connection() as con:
        with con.cursor() as cur:
            cur.execute("SELECT word FROM imposter_word_history WHERE chat_id=%s",(chat_id,))
            used={x[0] for x in cur.fetchall()}
            choices=[w for w in WORDS if w not in used]
            if not choices:
                cur.execute("DELETE FROM imposter_word_history WHERE chat_id=%s",(chat_id,))
                choices=list(WORDS)
            word=random.choice(choices)
            cur.execute("INSERT INTO imposter_word_history(chat_id,word) VALUES(%s,%s) ON CONFLICT DO NOTHING",(chat_id,word))
            return word

def _name(p):
    return html.escape(p["name"][:40])

def _players(s):
    return s["players"]

def _active(s):
    return s and s["phase"] not in ("finished","cancelled")

def _keyboard(s,page=0):
    k=types.InlineKeyboardMarkup(row_width=2)
    g=s["id"]
    phase=s["phase"]
    if phase=="join":
        k.add(types.InlineKeyboardButton("➕ ပါဝင်မယ်",callback_data=f"imp:{g}:join"))
        k.add(types.InlineKeyboardButton("☰ Player List",callback_data=f"imp:{g}:list:0"))
    elif phase in ("clue","decision","tie","final"):
        k.add(types.InlineKeyboardButton("🔐 SECRET ကြည့်မယ်",callback_data=f"imp:{g}:secret"))
        if phase=="decision":
            k.row(types.InlineKeyboardButton("🔁 ထပ်တိုးမယ်",callback_data=f"imp:{g}:decision:more"),
                  types.InlineKeyboardButton("🔎 ခန့်မှန်းမယ်",callback_data=f"imp:{g}:decision:guess"))
        elif phase=="tie":
            k.add(types.InlineKeyboardButton("🎭 သရေဖြတ် ဆုံးဖြတ်မယ်",callback_data=f"imp:{g}:tiebreak"))
        elif phase=="final":
            people=_players(s)
            page=max(0,min(page,(len(people)-1)//8))
            for i in range(page*8,min((page+1)*8,len(people))):
                k.add(types.InlineKeyboardButton(f"{i+1:02d} · {people[i]['name'][:25]}",callback_data=f"imp:{g}:vote:{i}"))
            nav=[]
            if page:nav.append(types.InlineKeyboardButton("◀",callback_data=f"imp:{g}:page:{page-1}"))
            if (page+1)*8<len(people):nav.append(types.InlineKeyboardButton("▶",callback_data=f"imp:{g}:page:{page+1}"))
            if nav:k.row(*nav)
    return k

def _view(s):
    phase=s["phase"]
    names=_players(s)
    head="🎭 <b>IMPOSTER PROTOCOL</b>\n<code>━━━━━━━━━━━━━━━━━━━━</code>\n"
    if phase=="join":
        rows="\n".join(f"<code>{i+1:02d}.</code> {_name(p)}" for i,p in enumerate(names[:12]))
        if len(names)>12:rows+=f"\n… နောက်ထပ် {len(names)-12} ယောက်"
        return (head+"🟢 <b>RECRUITMENT OPEN</b>\n"
                f"⏳ Join: 40 စက္ကန့်  · 👥 {len(names)} ယောက်\n\n"
                "🔐 Secret ကို DM မလိုဘဲ Group Button ကနေ ကိုယ်တစ်ယောက်တည်း မြင်နိုင်မယ်။\n"
                "Bot ကို Private Chat မှာ START နှိပ်စရာမလိုပါ။\n\n"
                +(rows or "အခုထိ မပါဝင်သေးပါ။"))
    if phase=="clue":
        idx=s["turn"]
        p=names[idx]
        done=sum(1 for i in range(idx) if not names[i].get("removed"))
        return (head+f"🗣️ <b>ROUND {s['round']} · CLUE {idx+1}/{len(names)}</b>\n"
                f"👉 အခုအလှည့် — <b>{_name(p)}</b>\n"
                "💬 Group Chat မှာ သဲလွန်စတစ်ခု ရေးပါ။\n"
                "⏳ 45s + 15s Warning · အလှည့်မကျော်ရ\n"
                f"✅ ဖြေပြီး: {done} · 👥 စုစုပေါင်း: {len(names)}")
    if phase=="decision":
        choices=s["decisions"]
        a=sum(x=="more" for x in choices.values())
        b=sum(x=="guess" for x in choices.values())
        return (head+f"🗳️ <b>ROUND {s['round']} ပြီးပါပြီ</b>\n"
                "နောက် Round ဆက်မလား၊ Imposter ကို ခန့်မှန်းမလား?\n"
                f"🔁 ဆက်မယ်: {a} · 🔎 ခန့်မှန်းမယ်: {b}\n"
                f"မဲပေးပြီး: {len(choices)}/{len(names)}")
    if phase=="tie":
        return (head+"⚖️ <b>VOTE သရေဖြစ်နေပါတယ်</b>\n"
                "🎭 Imposter က သရေဖြတ်ဆုံးဖြတ်မယ်။\n"
                "Button ကို Imposter တစ်ယောက်တည်း သုံးနိုင်ပြီး ရွေးချယ်မှုကို Private Alert နဲ့ ပြမယ်။")
    if phase=="final":
        return (head+"🔎 <b>WHO IS THE IMPOSTER?</b>\n"
                "သံသယအရှိဆုံး Player ကို ရွေးပါ။ ကိုယ့်ကိုယ်ကို မဲမပေးရ။\n"
                f"🗳️ မဲပေးပြီး: {len(s['votes'])}/{len(names)}\n"
                "⏳ 60 seconds · မပေးသူ Abstain")
    return head+"🏁 Game ပြီးဆုံးပါပြီ။"

def _edit(bot,chat_id,s):
    if not s.get("message_id"):return
    try:
        bot.edit_message_text(_view(s),chat_id,s["message_id"],parse_mode="HTML",
                              reply_markup=_keyboard(s))
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            print("Imposter edit:",e)

def _announce(bot,chat_id,text):
    try:bot.send_message(chat_id,text,parse_mode="HTML")
    except Exception as e:print("Imposter announce:",e)

def _finish(bot,chat_id,s,reason="vote"):
    if s["phase"]=="finished":return
    s["phase"]="finished"
    votes={int(u):int(idx) for u,idx in s["votes"].items()}
    imp_idx=next((i for i,p in enumerate(s["players"]) if p["id"]==s["imposter"]),-1)
    correct=[uid for uid,idx in votes.items() if idx==imp_idx and uid!=s["imposter"]]
    found=len(correct)>len(s["players"])//2
    if reason=="imposter_afk":found=True
    s["finished_reason"]=reason
    s["winners"]=correct
    s["found"]=found
    _save(chat_id,s)
    _edit(bot,chat_id,s)
    _announce(bot,chat_id,"🏁 <b>CASE CLOSED · IMPOSTER</b>\n"
              f"🎭 Imposter: <b>{_name(s['players'][imp_idx])}</b>\n"
              f"🔐 Secret Word: <b>{html.escape(s['word'])}</b>\n"
              f"🔍 မှန်ကန်တဲ့မဲ: {len(correct)} ယောက်\n"
              f"🏆 {'Normal Players' if found else 'Imposter'} အနိုင်ရပါတယ်။\n"
              +"🎯 မှန်ကန်စွာရွေးသူ: "
              +((", ".join(_name(p) for p in s["players"] if p["id"] in correct)) or "မရှိ"))
    end_session(chat_id,"imposter")
    # Reward participants only once. Claim before external DB side effects.
    if not s.get("rewards_claimed"):
        s["rewards_claimed"]=True
        _save(chat_id,s)
        rewarded=correct if found else [s["imposter"]]
        for uid in rewarded:
            try:add_bonus_points(chat_id,uid,10 if uid==s["imposter"] else 5,reason="imposter")
            except Exception as exc:print("Imposter rewards:",exc)

def _start_clues(s):
    s["phase"]="clue"
    s["round"]+=1
    s["turn"]=0
    s["deadline"]=time.time()+TURN_TIME

def _start_final(s):
    s["phase"]="final"
    s["deadline"]=time.time()+60
    s["votes"]={}

def _decide(s,decision):
    if decision=="more" and s["round"]<MAX_ROUNDS:
        _start_clues(s)
    else:_start_final(s)

def _next_turn(bot,chat_id,s):
    s["turn"]+=1
    while s["turn"]<len(s["players"]) and s["players"][s["turn"]].get("removed"):
        s["turn"]+=1
    if s["turn"]>=len(s["players"]):
        s["phase"]="decision"
        s["decisions"]={}
        s["deadline"]=time.time()+DECISION_TIME
    else:s["deadline"]=time.time()+TURN_TIME
    _save(chat_id,s)
    _edit(bot,chat_id,s)

def _tick(bot,chat_id,s):
    now=time.time()
    if now<s.get("deadline",now+1):return
    if s["phase"]=="join":
        if len(s["players"])<MIN_PLAYERS:
            s["phase"]="cancelled";_save(chat_id,s);end_session(chat_id,"imposter")
            _announce(bot,chat_id,"🎭 ပါဝင်သူ 4 ယောက်မပြည့်လို့ Game ပယ်ဖျက်ပါပြီ။")
            return
        s["imposter"]=random.choice(s["players"])["id"]
        s["word"]=_word(chat_id)
        s["round"]=0
        _start_clues(s)
        _save(chat_id,s)
        _announce(bot,chat_id,"📋 <b>OPERATIVE LIST · JOIN ORDER</b>\n"+
                  "\n".join(f"{i+1:02d}. {_name(p)}" for i,p in enumerate(s["players"][:100]))+
                  ("\n… ကျန်သူတွေကို List Button နဲ့ကြည့်ပါ။" if len(s["players"])>100 else "")+
                  "\n\n🔐 Game Message မှာ SECRET ကြည့်မယ် နှိပ်ပြီး ကိုယ့် Role ကို ကြည့်ပါ။")
        _edit(bot,chat_id,s)
    elif s["phase"]=="clue":
        p=s["players"][s["turn"]]
        if not s.get("warned"):
            s["warned"]=True
            s["deadline"]=now+15
            _save(chat_id,s)
            _announce(bot,chat_id,f"⏳ {_name(p)} — Clue ပေးဖို့ 15 seconds ကျန်ပါပြီ။")
            return
        s["warned"]=False
        p["afk"]=p.get("afk",0)+1
        if p["afk"]>=2:
            p["removed"]=True
            _announce(bot,chat_id,f"💤 {_name(p)} — AFK ၂ ကြိမ်ဆက်ဖြစ်လို့ ဖယ်ရှားပါတယ်။")
            if p["id"]==s["imposter"]:
                _finish(bot,chat_id,s,"imposter_afk");return
        _next_turn(bot,chat_id,s)
    elif s["phase"]=="decision":
        values=list(s["decisions"].values())
        more=values.count("more");guess=values.count("guess")
        if more==guess and s["round"]<MAX_ROUNDS:
            s["phase"]="tie";s["deadline"]=now+40
        else:_decide(s,"more" if more>guess else "guess")
        _save(chat_id,s);_edit(bot,chat_id,s)
    elif s["phase"]=="tie":
        _decide(s,"guess") # fail-safe if impostor does not respond
        _save(chat_id,s);_edit(bot,chat_id,s)
    elif s["phase"]=="final":_finish(bot,chat_id,s)

def _watch(bot):
    while True:
        try:
            with get_db_connection() as con:
                with con.cursor() as cur:
                    cur.execute("SELECT chat_id,state FROM imposter_games WHERE state->>'phase' IN ('join','clue','decision','tie','final')")
                    rows=cur.fetchall()
            for chat_id,s in rows:
                with LOCK:
                    # Re-read under lock: callbacks might already have changed state.
                    current=_load(chat_id)
                    if _active(current):_tick(bot,chat_id,current)
        except Exception as exc:print("Imposter watch:",exc)
        time.sleep(3)

def register(bot):
    global _schedulers_started
    _db_init()
    # Resumed games live in Neon; in-memory session guards are rebuilt.
    with get_db_connection() as con:
        with con.cursor() as cur:
            cur.execute("SELECT chat_id FROM imposter_games WHERE state->>'phase' IN ('join','clue','decision','tie','final')")
            for (chat_id,) in cur.fetchall():
                start_session(chat_id,"imposter",duration=24*3600)
    if not _schedulers_started:
        threading.Thread(target=_watch,args=(bot,),daemon=True,name="imposter-watch").start()
        _schedulers_started=True

    @bot.message_handler(commands=["imposter"])
    def command(msg):
        if msg.chat.type not in ("group","supergroup"):return bot.reply_to(msg,"Group ထဲမှာပဲ Imposter Game စလို့ရပါတယ်။")
        with LOCK:
            s=_load(msg.chat.id)
            if _active(s):return bot.reply_to(msg,"🎭 Imposter Game ကစားနေပြီးသားပါ။")
            ok,reason=start_session(msg.chat.id,"imposter",duration=24*3600)
            if not ok:return bot.reply_to(msg,f"🎮 {reason} Game ရှိနေပါတယ်။")
            s={"id":uuid.uuid4().hex[:10],"phase":"join","deadline":time.time()+JOIN_TIME,
               "players":[],"imposter":None,"word":None,"round":0,"turn":0,
               "warned":False,"decisions":{},"votes":{},"message_id":None}
            _save(msg.chat.id,s)
            try:
                m=bot.send_message(msg.chat.id,_view(s),parse_mode="HTML",reply_markup=_keyboard(s))
                s["message_id"]=m.message_id
                _save(msg.chat.id,s)
            except Exception:
                s["phase"]="cancelled";_save(msg.chat.id,s);end_session(msg.chat.id,"imposter")
                raise

    @bot.message_handler(commands=["imposterstop"])
    def stop(msg):
        if msg.chat.type not in ("group","supergroup"):return
        try:
            status=bot.get_chat_member(msg.chat.id,msg.from_user.id).status
        except Exception:return
        if status not in ("administrator","creator"):
            return bot.reply_to(msg,"Admin ပဲ Game ရပ်နိုင်ပါတယ်။")
        with LOCK:
            s=_load(msg.chat.id)
            if not _active(s):return bot.reply_to(msg,"Game မရှိပါ။")
            s["phase"]="cancelled";_save(msg.chat.id,s)
            _edit(bot,msg.chat.id,s)
            end_session(msg.chat.id,"imposter")
            bot.send_message(msg.chat.id,"🎭 Imposter Game ကို Admin က ရပ်လိုက်ပါပြီ။")

    @bot.callback_query_handler(func=lambda q:(q.data or "").startswith("imp:"))
    def callback(q):
        data=(q.data or "").split(":")
        if len(data)<3:return
        try:
            with LOCK:
                chat_id=q.message.chat.id
                s=_load(chat_id)
                if not _active(s) or s["id"]!=data[1]:
                    return bot.answer_callback_query(q.id,"ဒီ Game ပြီးသွားပါပြီ။",show_alert=True)
                action=data[2]
                uid=q.from_user.id
                player=next((p for p in s["players"] if p["id"]==uid),None)
                if action=="join":
                    if s["phase"]!="join" or time.time()>s["deadline"]:message="Join ပိတ်သွားပါပြီ။"
                    elif player:message="ပါဝင်ပြီးသားပါ။"
                    else:
                        s["players"].append({"id":uid,"name":q.from_user.first_name or "Player","afk":0,"removed":False})
                        _save(chat_id,s);_edit(bot,chat_id,s);message="✅ ပါဝင်ပြီးပါပြီ!"
                    return bot.answer_callback_query(q.id,message,show_alert=False)
                if action=="list":
                    page=int(data[3]) if len(data)>3 else 0
                    players=s["players"];page=max(0,min(page,(len(players)-1)//15 if players else 0))
                    text="\n".join(f"{i+1:02d}. {p['name']}" for i,p in enumerate(players[page*15:page*15+15],page*15))
                    return bot.answer_callback_query(q.id,text[:180] or "လူမရှိသေးပါ။",show_alert=True)
                if not player or player.get("removed"):
                    return bot.answer_callback_query(q.id,"ဒီ Game မှာ ပါဝင်သူမဟုတ်ပါ။",show_alert=True)
                if action=="secret":
                    message=("🎭 သင်က IMPOSTER ဖြစ်ပါတယ်။\nSecret Word မသိပါ။ တခြားသူတွေနဲ့ မကွာအောင် Clue ပေးပါ။"
                             if uid==s["imposter"] else "🔐 သင့် SECRET WORD:\n"+str(s["word"])+"\n\nGroup ထဲမှာ Word ကို တိုက်ရိုက်မပြောပါနဲ့။")
                    return bot.answer_callback_query(q.id,message,show_alert=True)
                if action=="decision" and s["phase"]=="decision" and len(data)>3:
                    if str(uid) in s["decisions"]:return bot.answer_callback_query(q.id,"မဲပေးပြီးသားပါ။")
                    s["decisions"][str(uid)]=data[3]
                    if len(s["decisions"])>=len(s["players"]):s["deadline"]=0
                    _save(chat_id,s);_edit(bot,chat_id,s)
                    return bot.answer_callback_query(q.id,"မဲပေးပြီးပါပြီ။")
                if action=="tiebreak" and s["phase"]=="tie":
                    if uid!=s["imposter"]:return bot.answer_callback_query(q.id,"ဒီဆုံးဖြတ်ချက်က Imposter အတွက်သာပါ။",show_alert=True)
                    # Callback popup cannot itself contain buttons; provide two new
                    # inline actions publicly, but authorize only the impostor.
                    k=types.InlineKeyboardMarkup()
                    k.row(types.InlineKeyboardButton("🔁 ဆက်မယ်",callback_data=f"imp:{s['id']}:tie:more"),
                          types.InlineKeyboardButton("🔎 ခန့်မှန်းမယ်",callback_data=f"imp:{s['id']}:tie:guess"))
                    bot.send_message(chat_id,"⚖️ သရေဖြတ် ရွေးချယ်မှု (Imposter တစ်ယောက်သာ အလုပ်လုပ်မယ်)",reply_markup=k)
                    return bot.answer_callback_query(q.id,"အောက်က ရွေးချယ်မှုတစ်ခု နှိပ်ပါ။",show_alert=True)
                if action=="tie" and s["phase"]=="tie" and len(data)>3:
                    if uid!=s["imposter"]:return bot.answer_callback_query(q.id,"Imposter တစ်ယောက်သာ ဆုံးဖြတ်နိုင်ပါတယ်။",show_alert=True)
                    _decide(s,data[3]);_save(chat_id,s);_edit(bot,chat_id,s)
                    return bot.answer_callback_query(q.id,"ဆုံးဖြတ်ပြီးပါပြီ။")
                if action=="page" and s["phase"]=="final":
                    page=int(data[3]);bot.edit_message_reply_markup(chat_id,s["message_id"],reply_markup=_keyboard(s,page))
                    return bot.answer_callback_query(q.id)
                if action=="vote" and s["phase"]=="final" and len(data)>3:
                    if str(uid) in s["votes"]:return bot.answer_callback_query(q.id,"မဲပေးပြီးသားပါ။")
                    idx=int(data[3])
                    if idx<0 or idx>=len(s["players"]):return bot.answer_callback_query(q.id,"ရွေးချယ်မှု မမှန်ပါ။")
                    if s["players"][idx]["id"]==uid:return bot.answer_callback_query(q.id,"ကိုယ့်ကိုယ်ကို မဲပေးလို့မရပါ။")
                    s["votes"][str(uid)]=idx
                    if len(s["votes"])>=len(s["players"]):
                        _finish(bot,chat_id,s)
                    else:_save(chat_id,s);_edit(bot,chat_id,s)
                    return bot.answer_callback_query(q.id,"မဲပေးပြီးပါပြီ။")
                return bot.answer_callback_query(q.id,"အခုအချိန်မှာ မရနိုင်ပါ။")
        except Exception as exc:
            print("Imposter callback:",exc)
            try:bot.answer_callback_query(q.id,"ခေတ္တ အဆင်မပြေပါ။")
            except Exception:pass

    @bot.message_handler(func=lambda m:True,content_types=["text"])
    def capture_clue(msg):
        if (msg.chat.type not in ("group","supergroup") or not msg.from_user or
            msg.from_user.is_bot or not msg.text or msg.text.startswith("/")):
            return ContinueHandling()
        # Fast path: only check Neon when there is a possible active game.
        try:
            with LOCK:
                s=_load(msg.chat.id)
                if not _active(s) or s["phase"]!="clue" or time.time()>s["deadline"]:
                    return ContinueHandling()
                p=s["players"][s["turn"]]
                if p["id"]!=msg.from_user.id:return ContinueHandling()
                value=msg.text.strip()
                if len(value)<2 or len(value)>150:return ContinueHandling()
                # The secret itself is not a clue; reject and ask for a hint.
                if s["word"] and s["word"] in value:
                    bot.reply_to(msg,"🔐 Secret Word ကို တိုက်ရိုက်မရေးပါနဲ့။ သဲလွန်စပဲ ရေးပေးပါ။")
                    return ContinueHandling()
                p["afk"]=0;s["warned"]=False
                _next_turn(bot,msg.chat.id,s)
        except Exception as exc:print("Imposter clue:",exc)
        return ContinueHandling()
