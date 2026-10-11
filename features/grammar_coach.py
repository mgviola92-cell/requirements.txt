"""Privacy-first, free Telegram Grammar Coach (manual and admin opt-in auto)."""
import re
import time
import threading
from telebot.handler_backends import ContinueHandling
from database.db import get_db_connection
from core.grammar_engine import analyze, explain

_guard=threading.RLock()
_recent={}
_ready=False

def setup():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS grammar_group_settings(
                chat_id BIGINT PRIMARY KEY, auto_enabled BOOLEAN NOT NULL DEFAULT FALSE)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS grammar_optouts(
                chat_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
                PRIMARY KEY(chat_id,user_id))""")

def _active(chat_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT auto_enabled FROM grammar_group_settings WHERE chat_id=%s",(chat_id,))
            row=cur.fetchone()
            return bool(row and row[0])

def _opted_out(chat_id,user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM grammar_optouts WHERE chat_id=%s AND user_id=%s",(chat_id,user_id))
            return cur.fetchone() is not None

def _set_auto(chat_id,enabled):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO grammar_group_settings(chat_id,auto_enabled)
              VALUES(%s,%s) ON CONFLICT(chat_id) DO UPDATE SET auto_enabled=EXCLUDED.auto_enabled""",
              (chat_id,enabled))

def _set_optout(chat_id,user_id,off):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if off:
                cur.execute("INSERT INTO grammar_optouts(chat_id,user_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",(chat_id,user_id))
            else:
                cur.execute("DELETE FROM grammar_optouts WHERE chat_id=%s AND user_id=%s",(chat_id,user_id))

def register(bot):
    global _ready
    try:
        setup()
        _ready=True
    except Exception as exc:
        print("Grammar DB initialization:",exc)
        return

    def _admin(msg):
        if msg.chat.type=="private":return False
        try:
            member=bot.get_chat_member(msg.chat.id,msg.from_user.id)
            return member.status in ("administrator","creator")
        except Exception:return False

    @bot.message_handler(commands=["grammar"])
    def grammar_command(msg):
        if not msg.from_user or msg.from_user.is_bot:return ContinueHandling()
        if not _ready:
            bot.reply_to(msg,"Grammar Coach ခေတ္တ မရနိုင်သေးပါ။")
            return ContinueHandling()
        tokens=(msg.text or "").split(maxsplit=2)
        choice=tokens[1].lower() if len(tokens)>=2 else ""
        if choice in ("on","off"):
            if msg.chat.type not in ("group","supergroup"):
                bot.reply_to(msg,"Group ထဲမှာသာ Auto Mode ဖွင့်နိုင်ပါတယ်။")
            elif not _admin(msg):
                bot.reply_to(msg,"Auto Mode ကို Group Admin ပဲ ဖွင့်/ပိတ်နိုင်ပါတယ်။")
            else:
                try:
                    _set_auto(msg.chat.id,choice=="on")
                    bot.reply_to(msg,"✅ Grammar Auto Mode "+("ON" if choice=="on" else "OFF"))
                except Exception as exc:
                    print("Grammar settings:",exc)
                    bot.reply_to(msg,"Settings သိမ်းမရသေးပါ။")
            return ContinueHandling()
        if choice in ("mute","unmute"):
            if msg.chat.type not in ("group","supergroup"):
                bot.reply_to(msg,"Group ထဲမှာသာ သုံးနိုင်ပါတယ်။")
            else:
                try:
                    _set_optout(msg.chat.id,msg.from_user.id,choice=="mute")
                    bot.reply_to(msg,"✅ Grammar Auto Reply "+("ပိတ်ပြီးပါပြီ" if choice=="mute" else "ပြန်ဖွင့်ပြီးပါပြီ"))
                except Exception as exc:
                    print("Grammar opt out:",exc)
                    bot.reply_to(msg,"ခေတ္တ မရနိုင်သေးပါ။")
            return ContinueHandling()
        if msg.reply_to_message and msg.reply_to_message.text:
            target=msg.reply_to_message.text.strip()
        elif len(tokens)>1:
            target=(msg.text or "").split(maxsplit=1)[1].strip()
        else:
            bot.reply_to(msg,"📘 စစ်ချင်တဲ့ English Message ကို Reply လုပ်ပြီး /grammar ပို့ပါ။\n"
                             "ဒါမှမဟုတ် /grammar I didn't went လို့ ရေးပါ။\n"
                             "Admin: /grammar on | /grammar off\n"
                             "ကိုယ်ပိုင် Opt-out: /grammar mute | /grammar unmute")
            return ContinueHandling()
        if len(target)>500:
            bot.reply_to(msg,"စာသား 500 လုံးအောက်ပဲ စစ်ပေးနိုင်ပါသေးတယ်။")
            return ContinueHandling()
        bot.reply_to(msg,explain(target))
        return ContinueHandling()

    @bot.message_handler(func=lambda m:True,content_types=["text"])
    def grammar_auto(msg):
        if not _ready:return ContinueHandling()
        if (msg.chat.type not in ("group","supergroup") or not msg.from_user
            or msg.from_user.is_bot or not msg.text or msg.text.startswith("/")):
            return ContinueHandling()
        value=msg.text.strip()
        if len(value)<12 or len(value)>300 or not re.search(r"[A-Za-z]{2,}",value):
            return ContinueHandling()
        # Check locally before querying private group settings; irrelevant chat
        # never gets sent outside the bot and never triggers network lookups.
        issues=analyze(value,max_issues=2)
        if not issues:return ContinueHandling()
        chat_id=msg.chat.id
        now=time.monotonic()
        with _guard:
            if now-_recent.get((chat_id,msg.from_user.id),0)<180:
                return ContinueHandling()
            if now-_recent.get((chat_id,"group"),0)<35:
                return ContinueHandling()
            # Reserve before slow DB check to avoid many concurrent replies.
            _recent[(chat_id,msg.from_user.id)]=now
            _recent[(chat_id,"group")]=now
        try:
            if not _active(chat_id) or _opted_out(chat_id,msg.from_user.id):
                return ContinueHandling()
            bot.reply_to(msg,explain(value))
        except Exception as exc:
            print("Grammar auto:",exc)
        return ContinueHandling()
