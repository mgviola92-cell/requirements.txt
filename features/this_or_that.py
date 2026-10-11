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
