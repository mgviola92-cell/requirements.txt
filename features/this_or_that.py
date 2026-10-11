"""Telegram interface for five-round, persisted This or That group game."""
import random
import threading
import time
from datetime import datetime, timezone
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from core.sessions import start_session, end_session
from core.rewards import add_bonus_points
from database.db import get_db_connection
from games import this_or_that as engine
from ui.this_or_that_card import round_card, illustrated_card, result_card

_lock=threading.RLock()
_threads=set()
_last_updates={}
_auto_counts={}
_auto_threshold={}
_auto_last={}
_db_ready=False

def _image(question,round_no,votes=(0,0)):
    return round_card(question,round_no,votes) or illustrated_card(question,round_no,votes)

def _buttons(match_id,num):
    markup=InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🅰️ A",callback_data=f"tot:{match_id}:{num}:0"),
        InlineKeyboardButton("🅱️ B",callback_data=f"tot:{match_id}:{num}:1"))
    return markup

def register(bot):
    global _db_ready
    try:
        engine.initialize()
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("ALTER TABLE tot_games ADD COLUMN IF NOT EXISTS message_id BIGINT")
        _db_ready=True
    except Exception as exc:
        print("This or That startup:",exc)
        return

    def _mid(chat_id):
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("SELECT message_id FROM tot_games WHERE chat_id=%s",(chat_id,))
                row=cur.fetchone()
                return row[0] if row else None

    def _set_mid(chat_id,match_id,message_id):
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("UPDATE tot_games SET message_id=%s WHERE chat_id=%s AND match_id=%s",
                            (message_id,chat_id,match_id))

    def _update(chat_id,state,finished=False):
        mid=_mid(chat_id)
        if not mid:return
        if finished:
            bot.edit_message_media(InputMediaPhoto(
                result_card(state["people"]),caption="🏁 THIS OR THAT — 5 ROUNDS FINISHED"),
                chat_id=chat_id,message_id=mid,reply_markup=None)
            return
        bot.edit_message_media(InputMediaPhoto(
            _image(state["question"],state["round"],state["counts"]),
            caption=f"🎭 THIS OR THAT • Round {state['round']}/5"),
            chat_id=chat_id,message_id=mid,
            reply_markup=_buttons(state["match_id"],state["round"]))

    def _launch(chat_id):
        with _lock:
            if not _db_ready:return False
            ok,_=start_session(chat_id,"this_or_that",duration=900)
            if not ok:return False
            try:
                state=engine.start(chat_id)
                if state is None:
                    end_session(chat_id,"this_or_that")
                    return False
                sent=bot.send_photo(chat_id,_image(state["question"],1),
                    caption="🎭 THIS OR THAT • Round 1/5",
                    reply_markup=_buttons(state["match_id"],1))
                _set_mid(chat_id,state["match_id"],sent.message_id)
            except Exception as exc:
                print("This or That launch:",exc)
                if "state" in locals() and state:
                    try:engine.stop(chat_id,state["match_id"])
                    except Exception:pass
                end_session(chat_id,"this_or_that")
                return False
            _start_watcher(chat_id,state["match_id"])
        return True

    def _watch(chat_id,match_id):
        try:
            try:
                state=engine.snapshot(chat_id)
                if state and state["status"]=="active":
                    _update(chat_id,state)
            except Exception as exc:
                print("This or That resume card:",exc)
            while True:
                with _lock:
                    state=engine.snapshot(chat_id)
                    if not state or state["match_id"]!=match_id or state["status"]!="active":
                        break
                    if state["ends_at"]>datetime.now(timezone.utc):
                        pass
                    else:
                        result=engine.advance(chat_id,match_id)
                        if result:
                            if result["finished"]:
                                try:_update(chat_id,{"people":len(result["participants"])},finished=True)
                                except Exception as exc:print("This or That final card:",exc)
                                end_session(chat_id,"this_or_that")
                                break
                            else:
                                new_state=engine.snapshot(chat_id)
                                try:_update(chat_id,new_state)
                                except Exception as exc:print("This or That next round:",exc)
                time.sleep(2)
        except Exception as exc:
            print("This or That watcher:",exc)
        finally:
            with _lock:
                _threads.discard((chat_id,match_id))

    def _start_watcher(chat_id,match_id):
        key=(chat_id,match_id)
        if key in _threads:return
        _threads.add(key)
        threading.Thread(target=_watch,args=key,daemon=True).start()

    @bot.message_handler(commands=["tot","thisorthat"])
    def tot_command(message):
        if message.chat.type not in ("group","supergroup"):return
        if not _launch(message.chat.id):
            bot.reply_to(message,"🎮 ဒီ Group မှာ Game တစ်ခုရှိနေပါတယ်။ ခဏနေမှ ပြန်စမ်းပါ။")

    @bot.callback_query_handler(func=lambda c:bool(c.data) and c.data.startswith("tot:"))
    def tot_answer(call):
        try:
            _,match_id,num_text,choice_text=call.data.split(":")
            round_no=int(num_text)
            choice=int(choice_text)
        except Exception:
            bot.answer_callback_query(call.id,"ရွေးချယ်မှု မှားနေပါတယ်။")
            return
        chat_id=call.message.chat.id
        with _lock:
            try:
                inserted=engine.vote(chat_id,match_id,round_no,call.from_user.id,choice)
            except Exception as exc:
                print("This or That vote error:",exc)
                bot.answer_callback_query(call.id,"ခဏနေပြီး ထပ်စမ်းပါ။")
                return
            if not inserted:
                bot.answer_callback_query(call.id,"Vote ပြီးသားဖြစ်နိုင်ပါတယ်၊ ဒါမှမဟုတ် Round ပိတ်သွားပါပြီ။")
                return
        bot.answer_callback_query(call.id,"✅ Vote လက်ခံပြီးပါပြီ")
        try:
            add_bonus_points(chat_id,call.from_user.id,1,reason="this_or_that_vote")
        except Exception as exc:
            print("This or That reward:",exc)
        with _lock:
            now=time.monotonic()
            if now-_last_updates.get(chat_id,0)>=2:
                _last_updates[chat_id]=now
                try:
                    state=engine.snapshot(chat_id)
                    if state and state["match_id"]==match_id and state["round"]==round_no:
                        _update(chat_id,state)
                except Exception as exc:
                    print("This or That count refresh:",exc)

    try:
        for chat_id,match_id,deadline in engine.active_games():
            allowed,_=start_session(chat_id,"this_or_that",duration=900)
            if allowed:_start_watcher(chat_id,match_id)
    except Exception as exc:
        print("This or That recovery:",exc)

    @bot.message_handler(func=lambda m:True,content_types=["text"])
    def tot_auto(m):
        from telebot.handler_backends import ContinueHandling
        if (m.chat.type in ("group","supergroup") and m.from_user
                and not m.from_user.is_bot and m.text and not m.text.startswith("/")):
            chat_id=m.chat.id
            n=_auto_counts.get(chat_id,0)+1
            target=_auto_threshold.setdefault(chat_id,random.randint(100,220))
            if n>=target:
                _auto_counts[chat_id]=0
                _auto_threshold[chat_id]=random.randint(100,220)
                if time.monotonic()-_auto_last.get(chat_id,0)>1800 and random.random()<0.25:
                    if _launch(chat_id):_auto_last[chat_id]=time.monotonic()
            else:
                _auto_counts[chat_id]=n
        return ContinueHandling()
