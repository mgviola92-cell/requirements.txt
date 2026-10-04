"""Telegram wiring. Call register_daily_challenge(bot) before polling starts."""
import hashlib,time,threading
from telebot.handler_backends import ContinueHandling
from database.daily_challenge import (initialize_daily_challenge,record_message,overview,claim,
  get_card_id,set_card_id,today,MISSIONS)
from ui.daily_challenge_card import card
_lock=threading.RLock();_last_refresh={};_ready=False

def register_daily_challenge(bot):
    global _ready
    try:_ready=initialize_daily_challenge()
    except Exception as exc:
        print('Daily Challenge database init error:',exc);_ready=False

    def publish(chat_id, force=False):
        if not _ready:return
        now=time.monotonic()
        with _lock:
            key=(chat_id,today())
            if not force and now-_last_refresh.get(key,0)<30:return
            _last_refresh[key]=now
        try:
            s=overview(chat_id);s['chat_id']=chat_id
            current=get_card_id(chat_id)
            if current:
                try:
                    from telebot.types import InputMediaPhoto
                    bot.edit_message_media(InputMediaPhoto(card(s)),chat_id,current)
                    return
                except Exception as exc:print('Daily card edit retry:',exc)
            sent=bot.send_photo(chat_id,card(s),caption='🎯 DAILY CHALLENGE  |  /dailyclaim 1-3')
            set_card_id(chat_id,sent.message_id)
            try:bot.pin_chat_message(chat_id,sent.message_id,disable_notification=True)
            except Exception:pass
        except Exception as exc:print('Daily publish error:',exc)

    @bot.message_handler(commands=['daily','dailychallenge'])
    def daily_command(message):
        if message.chat.type not in ('group','supergroup') or not _ready:return
        publish(message.chat.id,force=True)
        s=overview(message.chat.id,message.from_user.id)
        details='\n'.join(f'{i}. {"Claimed" if i in s["claimed"] else "Ready" if s["total"]>=m[0] and s["users"]>=m[1] and s["mine"]>=m[2] else "Locked"} (your {s["mine"]}/{m[2]})' for i,m in enumerate(MISSIONS,1))
        bot.reply_to(message,'🎯 Your Daily Missions:\n'+details+'\nUse /dailyclaim 1, 2 or 3')

    @bot.message_handler(commands=['dailyclaim'])
    def daily_claim_command(message):
        if message.chat.type not in ('group','supergroup') or not _ready:return
        try:idx=int((message.text or '').split()[1])
        except (IndexError,ValueError):
            bot.reply_to(message,'Usage: /dailyclaim 1 (or 2 / 3)');return
        try:state,pts=claim(message.chat.id,message.from_user.id,idx)
        except Exception as exc:
            print('Daily claim error:',exc);bot.reply_to(message,'Database error. Try again later.');return
        response={'ok':f'🎁 Mission {idx}: +{pts} Points!','locked':'🔒 Group goal or your own participation not complete.',
                  'claimed':'✅ You have already claimed this mission today.','invalid':'Choose mission 1, 2 or 3.'}[state]
        bot.reply_to(message,response)

    @bot.message_handler(func=lambda m: True,content_types=['text'])
    def daily_activity(message):
        if not _ready or message.chat.type not in ('group','supergroup') or not message.from_user or message.from_user.is_bot:return ContinueHandling()
        try:
            if record_message(message.chat.id,message.from_user.id,message.text):
                publish(message.chat.id)
        except Exception as exc:print('Daily activity error:',exc)
        return ContinueHandling()
    return _ready
