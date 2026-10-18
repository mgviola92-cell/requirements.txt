from core import db_work
from core.customization import message_text as _custom_text, setting_value as _custom_setting, bank_text as _custom_bank
"""Daily Challenge: persistent groups, random daily missions, scheduled auto-post.
Register once immediately after TeleBot creation, before all other handlers.
"""
import threading
import time
import hashlib
from datetime import datetime,timedelta
from telebot.handler_backends import ContinueHandling
from database.daily_challenge import (
    initialize_daily_challenge, register_group, active_groups, previous_card, delivery_failed, delivery_ready,
    record_message, overview, claim, get_card_id, set_card_id, today,
    missions_for, mission_state, MMT, personal_overview, personal_claim, active_cycle,
)
from ui.text_cards import daily as card, send_card, edit_card, TextCard

TEMP_CARD_SECONDS = 60

def _delete_later(bot, chat_id, message_id, delay=None):
    if delay is None: delay = _custom_setting('cfg.features.daily_challenge.TEMP_CARD_SECONDS', TEMP_CARD_SECONDS)
    def remove():
        try: bot.delete_message(chat_id, message_id)
        except Exception as exc: print("Daily temporary cleanup:", exc)
    timer = threading.Timer(delay, remove)
    timer.daemon = True
    timer.start()


_lock=threading.RLock()
_last_refresh={}
_ready=False
_registered=False
DAILY_WAKE=db_work.signal('daily_groups','daily_cards','owner_customizations')

def register_daily_challenge(bot):
    global _ready, _registered
    if _registered: return _ready
    try:
        _ready=initialize_daily_challenge()
    except Exception as exc:
        print('Daily Challenge init error:',exc)
        return False
    _registered=True

    def publish(chat_id, force=False):
        if not _ready: return False
        from features.owner_operations import feature_allowed
        day=today()
        now=time.monotonic()
        with _lock:
            key=(chat_id,day)
            if not force and now-_last_refresh.get(key,0)<30: return False
            _last_refresh[key]=now
        try:
            if not delivery_ready(chat_id):return False
            existing=get_card_id(chat_id,day)
            if not existing and not feature_allowed('game:daily_challenge',chat_id):return False
            s=overview(chat_id,day=day)
            s['chat_id']=chat_id
            if existing:
                try:
                    edit_card(bot,TextCard(card(s)),chat_id,existing)
                except Exception as exc:
                    # Editing an unchanged card is normal, not a reason to spam another.
                    if 'message is not modified' in str(exc).lower():return True
                    if not any(t in str(exc).lower() for t in ('message to edit not found','message_id_invalid','message not found','there is no text in the message','message has no text')):
                        raise
                    print('Daily Challenge edit error:',exc)
                else:
                    return True
                # Only send a replacement if an existing message was deleted or invalid.
            sent=send_card(bot,chat_id,card(s),caption=_custom_text('msg.features.daily_challenge.publish.d2c45eae88', '🎯 GROUP DAILY CHALLENGE | /dailygroupclaim 1-3', {}))
            set_card_id(chat_id,sent.message_id,day)
            if existing:
                try:bot.delete_message(chat_id,existing)
                except Exception:pass
            try:bot.pin_chat_message(chat_id,sent.message_id,disable_notification=True)
            except Exception as exc:print('Daily Challenge pin unavailable:',exc)
            old=previous_card(chat_id,day)
            if old:
                try:bot.unpin_chat_message(chat_id,old)
                except Exception:pass
            return True
        except Exception as exc:
            print('Daily Challenge publish error:',exc)
            try:delivery_failed(chat_id,exc)
            except Exception:pass
            # Retain the short in-process throttle; durable retry backs off auto posts.
            return False

    def ensure_main(chat_id):
        day=today()
        if not get_card_id(chat_id,day) and post_time_reached(chat_id):
            publish(chat_id,force=True)
        day=active_cycle(chat_id)
        existing=get_card_id(chat_id,day)
        if not existing:return
        try:
            snapshot=overview(chat_id,day=day)
            snapshot['chat_id']=chat_id
            try:edit_card(bot,TextCard(card(snapshot)),chat_id,existing)
            except Exception as exc:
                if 'message is not modified' not in str(exc).lower():
                    if any(t in str(exc).lower() for t in ('message to edit not found','message_id_invalid','message not found','there is no text in the message','message has no text')):
                        if day==today():publish(chat_id,force=True)
                        else:
                            replacement=send_card(bot,chat_id,card(snapshot),
                                caption=_custom_text('msg.features.daily_challenge.ensure_main.d2c45eae88', '🎯 GROUP DAILY CHALLENGE | /dailygroupclaim 1-3', {}))
                            set_card_id(chat_id,replacement.message_id,day)
                            try:bot.delete_message(chat_id,existing)
                            except Exception:pass
                            try:bot.pin_chat_message(chat_id,replacement.message_id,disable_notification=True)
                            except Exception as error:print('Daily recovery pin:',error)
                        return
                    print('Daily recovery check:',exc)
            info=bot.get_chat(chat_id)
            pinned=getattr(getattr(info,'pinned_message',None),'message_id',None)
            if pinned!=existing:
                try:bot.pin_chat_message(chat_id,existing,disable_notification=True)
                except Exception as exc:print('Daily repin unavailable:',exc)
        except Exception as exc:print('Daily recovery error:',exc)

    def random_post_minute(chat_id, day):
        # One reproducible random minute in the morning half of the Myanmar calendar day.
        # The chosen minute stays the same across Render restarts.
        seed=f'daily-post:{chat_id}:{day.isoformat()}'.encode()
        return int.from_bytes(hashlib.sha256(seed).digest()[:8], 'big') % (12 * 60)

    def post_time_reached(chat_id, now=None):
        now=now or datetime.now(MMT)
        return now.hour*60+now.minute >= random_post_minute(chat_id,now.date())

    def daily_auto_loop():
        # Cache completed daily posts in memory. Rebuild on startup/day rollover;
        # durable card IDs still prevent duplicates after crashes.
        posted=set();cache_day=None
        while True:
            DAILY_WAKE.clear();wait=60
            try:
                now=datetime.now(MMT);day=now.date()
                if cache_day!=day:posted.clear();cache_day=day
                midnight=now.replace(hour=0,minute=0,second=0,microsecond=0)
                next_at=(midnight+timedelta(days=1)).timestamp()
                for chat_id in active_groups():
                    if chat_id in posted:continue
                    due=(midnight+timedelta(minutes=random_post_minute(chat_id,day))).timestamp()
                    if due>now.timestamp():next_at=min(next_at,due);continue
                    if get_card_id(chat_id,day):posted.add(chat_id);continue
                    from core.startup_safety import AUTO_POSTS
                    if AUTO_POSTS.allow('daily',chat_id) and publish(chat_id,force=True):posted.add(chat_id)
                    else:next_at=min(next_at,time.time()+60)
                wait=db_work.delay(next_at)
            except Exception as exc:print('Daily auto scheduler error:',exc)
            DAILY_WAKE.wait(wait)

    threading.Thread(target=daily_auto_loop,daemon=True,name='daily_challenge_scheduler').start()

    @bot.message_handler(commands=['daily','dailychallenge'])
    def daily_command(message):
        if message.chat.type not in ('group','supergroup') or not _ready: return
        try:
            register_group(message.chat.id)
            # Recover deleted/unpinned main card without changing its mission cycle.
            ensure_main(message.chat.id)
            snapshot=personal_overview(message.chat.id,message.from_user.id)
            sent=send_card(bot,message.chat.id,card(snapshot),
                caption=_custom_text('msg.features.daily_challenge.daily_command.f22d1476f5', '🎯 Your Daily Challenge | /dailyclaim 1, 2 or 3', {}),
                reply_to_message_id=message.message_id)
            _delete_later(bot,message.chat.id,sent.message_id)
        except Exception as exc:
            print('Daily temporary card error:',exc)
        finally:
            _delete_later(bot,message.chat.id,message.message_id)

    @bot.message_handler(commands=['dailygroupclaim'])
    def group_claim_command(message):
        if message.chat.type not in ('group','supergroup') or not _ready:return
        try:
            register_group(message.chat.id)
            try:idx=int((message.text or '').split()[1])
            except (IndexError,ValueError):
                result='Usage: /dailygroupclaim 1 (or 2 / 3)'
            else:
                state,pts=claim(message.chat.id,message.from_user.id,idx,active_cycle(message.chat.id))
                result={'ok':_custom_text('msg.features.daily_challenge.group_claim_command.b81cf383b5', '🎁 Group mission {idx}: +{pts} Points!', {'idx': f'{idx}', 'pts': f'{pts}'}),
                    'locked':_custom_text('msg.features.daily_challenge.group_claim_command.79dad83037', '🔒 Group objective and your contribution must be completed.', {}),
                    'claimed':_custom_text('msg.features.daily_challenge.group_claim_command.0d30bb31ff', '✅ You already claimed this group mission.', {}),
                    'invalid':'Choose 1, 2 or 3.'}[state]
            sent=bot.reply_to(message,result)
            _delete_later(bot,message.chat.id,sent.message_id)
        except Exception as exc:print('Daily group claim error:',exc)
        finally:_delete_later(bot,message.chat.id,message.message_id)

    @bot.message_handler(commands=['dailyclaim'])
    def daily_claim_command(message):
        if message.chat.type not in ('group','supergroup') or not _ready:return
        register_group(message.chat.id)
        try:
            try: idx=int((message.text or '').split()[1])
            except (IndexError,ValueError):
                result='Usage: /dailyclaim 1 (or 2 / 3)'
            else:
                try: state,pts=personal_claim(message.chat.id,message.from_user.id,idx)
                except Exception as exc:
                    print('Daily claim error:',exc)
                    result='Database error. Try again later.'
                else:
                    result={'ok':_custom_text('msg.features.daily_challenge.daily_claim_command.9e47ddb05c', '🎁 Mission {idx}: +{pts} Points!', {'idx': f'{idx}', 'pts': f'{pts}'}),
                        'locked':_custom_text('msg.features.daily_challenge.daily_claim_command.430e8cd55a', '🔒 Finish your personal mission first.', {}),
                        'claimed':_custom_text('msg.features.daily_challenge.daily_claim_command.edf5c63e9a', '✅ You already claimed this mission today.', {}),
                        'invalid':'Choose mission 1, 2 or 3.'}[state]
                    # Group card must not be affected by personal reward claims.
            sent=bot.reply_to(message,result)
            _delete_later(bot,message.chat.id,sent.message_id)
        except Exception as exc:print('Daily claim response error:',exc)
        finally:_delete_later(bot,message.chat.id,message.message_id)

    @bot.message_handler(func=lambda m:True,content_types=['text'])
    def daily_activity(message):
        if not _ready or message.chat.type not in ('group','supergroup') or not message.from_user or message.from_user.is_bot:
            return ContinueHandling()
        try:
            register_group(message.chat.id)
            if record_message(message.chat.id,message.from_user.id,message.text):
                # Record activity immediately, but do not post before today's
                # random scheduled minute. Refresh an already-posted card.
                if get_card_id(message.chat.id) or post_time_reached(message.chat.id):
                    publish(message.chat.id)
        except Exception as exc:print('Daily activity error:',exc)
        return ContinueHandling()
    return True
