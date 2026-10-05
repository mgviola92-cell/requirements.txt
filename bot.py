import telebot
print("TEST 1 - bot.py started")
import time
import random
import secrets
import yt_dlp
import os
import threading
import json
import html
import urllib.request
import urllib.parse
from features.daily_challenge import register_daily_challenge
from telebot.types import ChatPermissions
from telebot.handler_backends import ContinueHandling
from config.ranks import RANKS, get_rank_data, get_rank_title, get_rank_progress
from database.db import DATABASE_URL, get_db_connection
from database.member_registry import (
    initialize_member_registry,
    remember_member,
    get_known_member_ids,
)
from database.players import (
    player_stats,
    player_stats_lock,
    get_player_stats,
    add_game_result,
    initialize_player_stats,
)

from core.rewards import (
    GAME_REWARDS,
    get_reward,
    apply_game_result,
    apply_custom_game_result,
)

from core.sessions import (
    start_session,
    end_session,
    get_session,
    get_session_data,
    update_session,
    has_session,
    can_start_session,
)

from core.cooldowns import (
    get_remaining_cooldown,
    cooldown_ready,
    set_cooldown,
    set_random_cooldown,
    check_and_start_cooldown,
    check_and_start_random_cooldown,
    clear_cooldown,
)

from core.timers import (
    schedule_task,
    cancel_task,
    has_task,
    get_task_remaining,
    reschedule_task,
)

from core.keyboards import (
    single_button,
    two_buttons,
    vote_keyboard,
    accept_decline_keyboard,
    boss_attack_keyboard,
    speed_tap_keyboard,
    claim_keyboard,
    pagination_keyboard,
)

from core.permissions import (
    is_user_admin,
    can_pin_messages,
    can_delete_messages,
    safe_pin_message,
    safe_unpin_message,
    safe_delete_message,
)

from core.asset_manager import (
    get_asset_path,
    list_images,
    random_asset,
    random_asset_avoiding_recent,
    count_assets,
    asset_exists,
)

from ui.card_generator import (
    create_card,
    open_image,
    resize_cover,
    add_background_image,
    draw_panel,
    draw_text,
    draw_progress_bar,
    paste_image,
    card_to_bytes,
    save_card,
)

from ui.rank_card import (
    generate_rank_card,
    generate_rank_card_bytes,
)

from ui.leaderboard_card import (
    generate_leaderboard_card,
    generate_leaderboard_card_bytes,
)

from games.emoji_guess import (
    EMOJI_GUESS_TIME,
    get_random_question,
    start_emoji_game,
    get_emoji_game,
    check_emoji_answer,
    get_emoji_hint,
    get_emoji_time_left,
    end_emoji_game,
)

from database.used_questions import (
    init_used_questions_db,
    mark_question_used,
    get_used_question_ids,
    get_recent_question_ids,
    reset_used_questions,
)

from games.math_battle import (
    TIMES as MATH_ROUND_TIMES,
    start as start_math_battle,
    snapshot as get_math_battle,
    set_message as set_math_message,
    answer as answer_math_battle,
    advance as advance_math_battle,
    stop as stop_math_battle,
)
from ui.math_battle_card import round_card as math_round_card, result_card as math_result_card
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

from games.word_chain import (
    IDLE_SECONDS as WORD_CHAIN_IDLE_SECONDS,
    get_game as get_word_chain_game,
    start_game as start_word_chain_game,
    set_message_id as set_word_chain_message_id,
    submit as submit_word_chain,
    finish as finish_word_chain,
)
from core.rewards import add_bonus_points
from ui.word_chain_card import status_card as word_chain_status_card
from ui.word_chain_card import result_card as word_chain_result_card

from games.speed_tap import (
    SPEED_TAP_PENDING_MIN,
    SPEED_TAP_PENDING_MAX,
    SPEED_TAP_WAIT_MIN,
    SPEED_TAP_WAIT_MAX,
    SPEED_TAP_ACTIVE_TIME,
    create_speed_tap_game,
    get_speed_tap_game,
    set_speed_tap_pending_message_id,
    set_speed_tap_message_id,
    start_speed_tap_wait,
    activate_speed_tap,
    register_speed_tap,
    expire_speed_tap,
    end_speed_tap_game,
    get_speed_tap_state,
)

from features.speed_tap_auto import (
    configure_speed_tap_auto,
    record_speed_tap_activity,
)

from games.boss_raid import (
    RAID_DURATION as BOSS_RAID_DURATION,
    start_raid as start_boss_raid,
    get_raid as get_boss_raid,
    set_message_id as set_boss_raid_message_id,
    attack as attack_boss_raid,
    finish_raid as finish_boss_raid,
    top_fighters as boss_top_fighters,
    ending_line as boss_ending_line,
    claim_ending as claim_boss_raid_ending,
)

from ui.boss_raid_card import (
    get_boss_artwork,
    live_card as generate_boss_live_card,
    visual_stage as get_boss_visual_stage,
    result_card as generate_boss_result_card,
)


from games.team_battle import (
    start_battle as start_team_battle,
    get_battle as get_team_battle,
    set_message_id as set_team_battle_message_id,
    finish_battle as finish_team_battle,
    member_ids as team_battle_member_ids,
    hype_line as team_battle_hype_line,
    set_update_listener as set_team_battle_update_listener,
)
from ui.team_battle_card import generate_team_battle_card

from ui.speed_tap_card import (
    get_speed_tap_background,
    generate_speed_tap_pending_card_bytes,
    generate_speed_tap_wait_card_bytes,
    generate_speed_tap_go_card_bytes,
    generate_speed_tap_result_card_bytes,
    generate_speed_tap_timeout_card_bytes,
)

# =========================================================
# 😀 EMOJI GUESS QUESTION SELECTOR
# Neon used-question + recent-history tracking
# =========================================================

def get_next_emoji_question(chat_id):

    GAME_TYPE = "emoji_guess"
    RECENT_LIMIT = 150

    # -----------------------------------------
    # 1. Current cycle ထဲမှာ မေးပြီးသား IDs
    # -----------------------------------------

    used_ids = get_used_question_ids(
        chat_id,
        GAME_TYPE
    )

    question = get_random_question(
        exclude_ids=used_ids
    )

    if not question:
        return None

    # -----------------------------------------
    # 2. get_random_question() က available
    # မရှိရင် full pool ကို fallback လုပ်တယ်။
    #
    # ပြန်ရလာတဲ့ ID က used ထဲရှိနေတယ်ဆို
    # current pool ကုန်ပြီလို့ဆိုလိုတယ်။
    # -----------------------------------------

    if question["id"] in used_ids:

        recent_ids = set(
            get_recent_question_ids(
                chat_id,
                GAME_TYPE,
                limit=RECENT_LIMIT
            )
        )

        # Current cycle ကိုပဲ reset
        # Permanent history မပျက်ဘူး
        reset_used_questions(
            chat_id,
            GAME_TYPE
        )

        # New cycle မှာ recent 150 ကိုရှောင်
        question = get_random_question(
            exclude_ids=recent_ids
        )

        if not question:
            return None

    return question
    

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

register_daily_challenge(bot)


# =========================================================
# 🔴🔵 TEAM BATTLE — RED vs BLUE
# Permanent game rewards stay unchanged; positive earned points are mirrored
# into the temporary active battle score by core.rewards.
# =========================================================
_team_battle_edit_lock = threading.RLock()
_team_battle_last_edit = {}

def _team_battle_caption(battle, stage="live"):
    red = int(battle.get("scores", {}).get("red", 0))
    blue = int(battle.get("scores", {}).get("blue", 0))
    if stage == "final":
        if red > blue:
            return "🏁 TEAM BATTLE FINAL — 🔴 RED TEAM WINS!"
        if blue > red:
            return "🏁 TEAM BATTLE FINAL — 🔵 BLUE TEAM WINS!"
        return "🏁 TEAM BATTLE FINAL — 🤝 DRAW!"
    if stage == "half":
        return "⚔️ TEAM BATTLE — HALF-TIME"
    return "⚔️ TEAM BATTLE — RED vs BLUE"

def _team_battle_replace_card(battle, stage):
    chat_id = battle["chat_id"]
    old_id = battle.get("message_id")
    try:
        sent = bot.send_photo(
            chat_id,
            generate_team_battle_card(battle, stage),
            caption=_team_battle_caption(battle, stage),
        )
        safe_pin_message(bot, chat_id, sent.message_id, disable_notification=True)
        set_team_battle_message_id(chat_id, battle["id"], sent.message_id, stage)
        if old_id and old_id != sent.message_id:
            safe_unpin_message(bot, chat_id, old_id)
            safe_delete_message(bot, chat_id, old_id)
        return sent.message_id
    except Exception as exc:
        print("Team Battle card replace error:", exc)
        return None

def _team_battle_live_update(battle):
    chat_id = battle["chat_id"]
    mid = battle.get("message_id")
    if not mid or battle.get("finished"):
        return
    now = time.monotonic()
    with _team_battle_edit_lock:
        last = _team_battle_last_edit.get(chat_id, 0.0)
        if now - last < 1.5:
            return
        _team_battle_last_edit[chat_id] = now
    try:
        bot.edit_message_media(
            InputMediaPhoto(
                generate_team_battle_card(battle, battle.get("stage", "live")),
                caption=_team_battle_caption(battle, battle.get("stage", "live")),
            ),
            chat_id=chat_id,
            message_id=mid,
        )
    except Exception as exc:
        print("Team Battle live edit error:", exc)

def _team_battle_member_mention(chat_id, uid):
    try:
        member = bot.get_chat_member(chat_id, uid)
        user = member.user
        name = html.escape(user.first_name or user.username or "Player")
        return f'<a href="tg://user?id={uid}">{name}</a>'
    except Exception:
        return "Player"

def _team_battle_hype(chat_id, battle_id):
    battle = get_team_battle(chat_id)
    if not battle or battle["id"] != battle_id or battle.get("finished"):
        return
    ids = team_battle_member_ids(battle)
    if ids:
        picks = random.sample(ids, min(len(ids), random.randint(1, min(4, len(ids)))))
        mentions = " ".join(_team_battle_member_mention(chat_id, uid) for uid in picks)
        try:
            msg = bot.send_message(
                chat_id,
                f"⚡ <b>TEAM BATTLE UPDATE</b>\n\n{mentions}\n{team_battle_hype_line()}",
                parse_mode="HTML",
            )
            threading.Timer(35, lambda: safe_delete_message(bot, chat_id, msg.message_id)).start()
        except Exception as exc:
            print("Team Battle hype error:", exc)
    remaining = max(0, battle["ends_at"] - time.time())
    if remaining > 70:
        schedule_task(
            min(random.randint(55, 105), max(20, remaining - 20)),
            _team_battle_hype,
            chat_id,
            battle_id,
            task_id=f"team_battle_hype:{chat_id}",
            replace=True,
        )

def _team_battle_half(chat_id, battle_id):
    battle = get_team_battle(chat_id)
    if not battle or battle["id"] != battle_id or battle.get("finished"):
        return
    _team_battle_replace_card(battle, "half")

def _team_battle_final(chat_id, battle_id):
    battle = finish_team_battle(chat_id, battle_id)
    if not battle:
        return
    _team_battle_replace_card(battle, "final")
    cancel_task(f"team_battle_hype:{chat_id}")
    _team_battle_last_edit.pop(chat_id, None)

set_team_battle_update_listener(_team_battle_live_update)

@bot.message_handler(commands=["teambattle"])
def team_battle_command(message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if not is_user_admin(bot, message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Team Battle ကို Admin ပဲ စနိုင်ပါတယ်။")
        return
    started, battle = start_team_battle(message.chat.id)
    if not started:
        bot.reply_to(message, "⚔️ Team Battle က လက်ရှိ run နေပါတယ်။")
        return
    try:
        sent = bot.send_photo(
            message.chat.id,
            generate_team_battle_card(battle, "live"),
            caption=_team_battle_caption(battle, "live"),
        )
        set_team_battle_message_id(message.chat.id, battle["id"], sent.message_id, "live")
        safe_pin_message(bot, message.chat.id, sent.message_id, disable_notification=True)
    except Exception as exc:
        print("Team Battle start card error:", exc)
        return

    half_delay = max(1, battle["half_at"] - time.time())
    final_delay = max(2, battle["ends_at"] - time.time())
    schedule_task(
        half_delay, _team_battle_half, message.chat.id, battle["id"],
        task_id=f"team_battle_half:{message.chat.id}", replace=True,
    )
    schedule_task(
        final_delay, _team_battle_final, message.chat.id, battle["id"],
        task_id=f"team_battle_final:{message.chat.id}", replace=True,
    )
    schedule_task(
        random.randint(45, 80), _team_battle_hype, message.chat.id, battle["id"],
        task_id=f"team_battle_hype:{message.chat.id}", replace=True,
    )


try:
    initialize_member_registry()
except Exception as exc:
    print(f"Member registry init error: {exc}")

# =========================================================
# 👥 GROUP MEMBER REGISTRY MIDDLEWARE
# Remembers non-bot users the bot actually sees in each group.
# This is not online-status tracking. Data persists in Neon.
# =========================================================
@bot.message_handler(
    func=lambda message: True,
    content_types=[
        "text", "audio", "document", "animation", "game", "photo",
        "sticker", "video", "video_note", "voice", "contact",
        "location", "venue", "poll", "dice", "new_chat_members"
    ],
)
def member_registry_middleware(message):
    try:
        if message.chat.type in ("group", "supergroup"):
            seen = []
            if message.from_user and not message.from_user.is_bot:
                seen.append(message.from_user)
            if getattr(message, "reply_to_message", None):
                u = getattr(message.reply_to_message, "from_user", None)
                if u and not u.is_bot:
                    seen.append(u)
            for u in (getattr(message, "new_chat_members", None) or []):
                if u and not u.is_bot:
                    seen.append(u)
            used = set()
            for u in seen:
                if u.id in used:
                    continue
                used.add(u.id)
                remember_member(
                    message.chat.id, u.id,
                    username=getattr(u, "username", None),
                    first_name=getattr(u, "first_name", None),
                    last_name=getattr(u, "last_name", None),
                )
    except Exception as exc:
        print(f"Member registry activity error: {exc}")
    return ContinueHandling()

# Activity tracker runs first, then allows ordinary game/command handlers.
# Commands, bot messages and private chats do not count as group activity.
@bot.message_handler(func=lambda message: True, content_types=["text"])
def speed_tap_activity_middleware(message):
    try:
        if (
            message.chat.type in ("group", "supergroup")
            and message.from_user
            and not message.from_user.is_bot
            and message.text
            and not message.text.lstrip().startswith("/")
        ):
            record_speed_tap_activity(
                message.chat.id,
                message.from_user.id,
            )
    except Exception as exc:
        print(f"Speed Tap activity error: {exc}")
    return ContinueHandling()


# =========================================================
# 🚨 EARLY TEXT SPAM MIDDLEWARE
# Exact rule: 5 non-command text messages from one user inside 10 seconds
# -> delete that burst + temporary mute immediately on message #5.
# Runs before ordinary game/text handlers so handler order cannot hide messages.
# =========================================================
_text_spam_lock = threading.RLock()
_text_spam_events = {}
TEXT_SPAM_LIMIT = 5
TEXT_SPAM_WINDOW = 10.0
TEXT_SPAM_MUTE_SECONDS = 45


@bot.message_handler(func=lambda message: True, content_types=["text"])
def early_text_spam_middleware(message):
    if (
        message.chat.type not in ("group", "supergroup")
        or not message.from_user
        or message.from_user.is_bot
        or not message.text
        or message.text.lstrip().startswith("/")
    ):
        return ContinueHandling()

    try:
        # Admins are intentionally exempt, matching the existing moderation policy.
        if is_admin(message):
            return ContinueHandling()
    except Exception:
        pass

    now = time.monotonic()
    key = (message.chat.id, message.from_user.id)

    with _text_spam_lock:
        recent = [
            item for item in _text_spam_events.get(key, [])
            if now - item[0] <= TEXT_SPAM_WINDOW
        ]
        recent.append((now, message.message_id))
        _text_spam_events[key] = recent
        hit_limit = len(recent) >= TEXT_SPAM_LIMIT
        burst_ids = [item[1] for item in recent] if hit_limit else []
        if hit_limit:
            _text_spam_events[key] = []

    if not hit_limit:
        return ContinueHandling()

    for mid in burst_ids:
        try:
            bot.delete_message(message.chat.id, mid)
        except Exception:
            pass

    try:
        bot.restrict_chat_member(
            message.chat.id,
            message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=int(time.time() + TEXT_SPAM_MUTE_SECONDS),
        )
        warning = bot.send_message(
            message.chat.id,
            f"🔇 {message.from_user.first_name or 'User'} — 10 စက္ကန့်အတွင်း စာ 5 စောင် ဆက်တိုက်ပို့လို့ "
            f"{TEXT_SPAM_MUTE_SECONDS} စက္ကန့် Mute လုပ်ထားပါတယ်။",
        )
        delay_delete_message(message.chat.id, warning.message_id, 8)
    except Exception as exc:
        print(f"Early Text Spam Mute Error: {exc}")

    # Stop other text handlers for the triggering 5th spam message.
    return None


# ကိုယ်ပေါ်စေချင်တဲ့ အီမိုဂျီများကို ဒီထဲမှာ စိုက်ကြိုက် ပြောင်းလဲနိုင်ပါတယ်
EMOJIS = [
    "🔥", "✨", "🎉", "💥", "🎯", "🌟", "🚀", "⚡", "🍀", "💎",
    "🌈", "🦋", "🌸", "🌺", "🌻", "🌙", "☀️", "⭐", "💫", "☄️",
    "🎊", "🎈", "🎁", "🎀", "🎵", "🎶", "🎸", "🎧", "🥁", "🎺",
    "⚽", "🏀", "🏆", "🥇", "🎮", "🕹️", "🎲", "🧩", "♟️", "🎳",
    "🍎", "🍓", "🍒", "🍉", "🍊", "🍋", "🥭", "🍍", "🥝", "🍇",
    "🍔", "🍕", "🍟", "🌮", "🍩", "🍪", "🍫", "🍿", "🧋", "☕",
    "🐶", "🐱", "🐼", "🦊", "🐯", "🦁", "🐸", "🐧", "🦄", "🐝",
    "🌊", "🌴", "🌵", "🍁", "🍂", "🌿", "☘️", "🌱", "🌲", "🏔️",
    "❤️", "🧡", "💛", "💚", "💙", "💜", "🤍", "🩵", "🩷", "💖",
    "😎", "🥳", "🤩", "😺", "🙌", "👏", "🤝", "💪", "🫶", "✌️",
]

# Mention cooldown/stop state is isolated per group.
# This prevents one group's /လာကြစမ်း or /stop from affecting another group.
mention_last_called = {}
mention_stopped = {}
mention_state_lock = threading.RLock()

# 🎯 လူခေါ်စာများကိုပဲ သီးသန့် အချိန်ကိုက် လိုက်ဖျက်ပေးမည့် စနစ်
def delay_delete_message(
    chat_id,
    message_id,
    delay_seconds
):
    def delete_task():
        try:
            bot.delete_message(
                chat_id,
                message_id
            )
        except Exception as e:
            print(
                f"Auto Delete Error: {e}"
            )

    task_id = (
        f"delete:"
        f"{chat_id}:"
        f"{message_id}"
    )

    return schedule_task(
        delay_seconds,
        delete_task,
        task_id=task_id,
        replace=True
    )

# --- 🛑 လူခေါ်ခြင်းကို ကြားဖြတ်ရပ်တန့်မည့် လုပ်ဆောင်ချက် (/stop) ---
@bot.message_handler(commands=['stop', 'နား'])
def stop_mention(message):
    if message.chat.type in ['group', 'supergroup']:
        with mention_state_lock:
            mention_stopped[message.chat.id] = True
        bot.reply_to(message, "🛑 ရပ်လိုက်ပြီ စောက်အမျိုးမျိုးပဲ မသာကောင်")


MENTION_COOLDOWN = 140
MENTION_ROUNDS = 30
MENTION_ROUND_DELAY = 2.0
MENTION_BATCH_SIZE = 35


def _mention_cooldown_check(message):
    chat_id = message.chat.id
    now = time.time()

    with mention_state_lock:
        last_called = mention_last_called.get(chat_id, 0)
        elapsed = now - last_called if last_called else MENTION_COOLDOWN

        if elapsed < MENTION_COOLDOWN:
            remaining = max(1, int(MENTION_COOLDOWN - elapsed))
            return False, remaining

        mention_last_called[chat_id] = now
        mention_stopped[chat_id] = False

    return True, 0


def _send_mention_cooldown_notice(message, remaining_time):
    if remaining_time > 60:
        notice = bot.reply_to(
            message,
            "⏳ လူခေါ်တာမပြီးသေးဘဲ လီးမို့ထပ်ခေါ်နေတာလား ဖြတ်ထိုးလိုက်ရ စောက်တောသား ⏳"
        )
    else:
        notice = bot.reply_to(
            message,
            f"⏳ ဆက်တိုက်ခေါ်လို့ မရဘူး စောက်ရူးကောင် ငါလည်း ငြောင်းတတ်တယ် "
            f"နောက်ထပ် {remaining_time} စက္ကန့် စောင့်ပြီးမှဆက်ခေါ် ကမကလ"
        )

    delay_delete_message(message.chat.id, notice.message_id, 15)


def _mention_is_stopped(chat_id):
    with mention_state_lock:
        return mention_stopped.get(chat_id, False)


def _send_mention_rounds(chat_id, user_ids, input_line):
    # Telegram text/entity limits အတွက် member များရင် batch ခွဲမယ်။
    # အရင် behavior အတိုင်း 30 rounds ပြန်ခေါ်မယ်။
    batches = [
        user_ids[i:i + MENTION_BATCH_SIZE]
        for i in range(0, len(user_ids), MENTION_BATCH_SIZE)
    ]

    for round_no in range(MENTION_ROUNDS):
        if _mention_is_stopped(chat_id):
            break

        for batch in batches:
            if _mention_is_stopped(chat_id):
                break

            hidden_mentions = "".join(
                f"<a href='tg://user?id={uid}'>\u200b</a>"
                for uid in batch
            )
            random_emojis = " ".join(random.sample(EMOJIS, k=8))

            # Agreed styling: စာနဲ့ emoji row ကြား blank line 2 ကြောင်း။
            final_message = (
                f"{html.escape(input_line)}\n\n\n"
                f"{random_emojis}\n"
                f"{hidden_mentions}"
            )

            sent_msg = bot.send_message(
                chat_id,
                final_message,
                parse_mode='HTML'
            )
            delay_delete_message(chat_id, sent_msg.message_id, 60)

        if round_no < MENTION_ROUNDS - 1 and not _mention_is_stopped(chat_id):
            time.sleep(MENTION_ROUND_DELAY)


def _send_common_mention_finish(chat_id):
    if _mention_is_stopped(chat_id):
        return

    with mention_state_lock:
        started_at = mention_last_called.get(chat_id, time.time())

    remaining_cooldown = int(
        MENTION_COOLDOWN - (time.time() - started_at)
    )
    remaining_cooldown = max(0, min(60, remaining_cooldown))

    finish_msg = bot.send_message(
        chat_id,
        f"ခေါ်ပြီးဘီ လီးဖစ်နေလား (နောက်ထပ် {remaining_cooldown} စက္ကန့် စောင့်ဦး)"
    )
    delay_delete_message(chat_id, finish_msg.message_id, 60)


# --- 👥 Known-member mention ---
@bot.message_handler(commands=['all', 'everyone', 'လာကြစမ်း'])
def mention_all_users(message):
    if message.chat.type not in ('group', 'supergroup'):
        bot.reply_to(message, "This command can only be used in Telegram Groups.")
        return

    chat_id = message.chat.id
    delay_delete_message(chat_id, message.message_id, 80)

    ready, remaining = _mention_cooldown_check(message)
    if not ready:
        _send_mention_cooldown_notice(message, remaining)
        return

    parts = (message.text or "").split(maxsplit=1)
    input_line = parts[1].strip() if len(parts) > 1 else "တောသားတွေလာကြစမ်း"

    try:
        # Admins ကို registry ထဲသေချာထည့်ထားပြီး known members နဲ့ပေါင်းမယ်။
        admins = bot.get_chat_administrators(chat_id)
        admin_ids = []

        for item in admins:
            if item.user.is_bot:
                continue
            admin_ids.append(item.user.id)
            try:
                remember_member(
                    chat_id,
                    item.user.id,
                    username=item.user.username,
                    first_name=item.user.first_name,
                    last_name=item.user.last_name,
                )
            except Exception:
                pass

        known_ids = get_known_member_ids(chat_id, limit=5000)

        user_list = []
        seen_ids = set()
        for uid in list(known_ids) + admin_ids:
            if uid in seen_ids:
                continue
            seen_ids.add(uid)
            user_list.append(uid)

        if not user_list:
            notice = bot.reply_to(
                message,
                "❌ ခေါ်လို့ရမယ့် member data မရှိသေးပါဘူး။"
            )
            delay_delete_message(chat_id, notice.message_id, 15)
            return

        _send_mention_rounds(chat_id, user_list, input_line)

        if not _mention_is_stopped(chat_id):
            time.sleep(1.0)
            _send_common_mention_finish(chat_id)

    except Exception as exc:
        print(f"Known-member mention error: {exc}")
        try:
            notice = bot.reply_to(
                message,
                "❌ Member တွေကို ခေါ်တဲ့အချိန် Error ဖြစ်သွားတယ်။"
            )
            delay_delete_message(chat_id, notice.message_id, 15)
        except Exception:
            pass


# =========================================================
# 👮 ADMIN-ONLY MENTION TARGET
# /admincall /အက်မင်ခေါ် [optional text]
# Uses the SAME cooldown/round/finish behavior as /လာကြစမ်း,
# but mentions admins only.
# =========================================================
@bot.message_handler(commands=["admincall", "အက်မင်ခေါ်"])
def mention_admins_only(message):
    if message.chat.type not in ("group", "supergroup"):
        bot.reply_to(message, "❌ Group ထဲမှာပဲ သုံးလို့ရပါတယ်။")
        return

    chat_id = message.chat.id
    delay_delete_message(chat_id, message.message_id, 80)

    ready, remaining = _mention_cooldown_check(message)
    if not ready:
        _send_mention_cooldown_notice(message, remaining)
        return

    try:
        admins = bot.get_chat_administrators(chat_id)
        admin_ids = [
            item.user.id
            for item in admins
            if not item.user.is_bot
        ]

        if not admin_ids:
            notice = bot.reply_to(
                message,
                "❌ ခေါ်လို့ရမယ့် Admin မတွေ့ပါဘူး။"
            )
            delay_delete_message(chat_id, notice.message_id, 15)
            return

        parts = (message.text or "").split(maxsplit=1)
        input_line = (
            parts[1].strip()
            if len(parts) > 1
            else "အက်မင်တို့ ခဏလာကြည့်ပေးပါဦး 👮"
        )

        _send_mention_rounds(chat_id, admin_ids, input_line)

        if not _mention_is_stopped(chat_id):
            time.sleep(1.0)
            _send_common_mention_finish(chat_id)

    except Exception as exc:
        print(f"Admin mention error: {exc}")
        try:
            notice = bot.reply_to(
                message,
                "❌ Admin တွေကို ခေါ်လို့မရသေးပါဘူး။"
            )
            delay_delete_message(chat_id, notice.message_id, 15)
        except Exception:
            pass


# --- 🎵 သီချင်းတောင်းသည့် လုပ်ဆောင်ချက် (/play /ဖွင့်) ---

@bot.message_handler(commands=['play', 'ဖွင့်'])
def play_music(message):
    print("🔥 PLAY COMMAND RECEIVED")
    
    try:

        # -----------------------------------------
        # 🎵 သီချင်းနာမည် ယူ
        # -----------------------------------------

        user_text = message.text.split(maxsplit=1)

        if len(user_text) <= 1:

            bot.reply_to(
                message,
                "❌ သီချင်းနာမည်ထည့်ပေးပါ။\n"
                "ဥပမာ - /play Alan Walker Faded"
            )

            return

        # အရေးကြီးဆုံး — [1] ဖြစ်ရမယ်
        song_name = user_text[1].strip()

        reply_msg = bot.reply_to(
            message,
            f"🎵 '{song_name}' ပို့ပေးမယ်။ ခဏစောင့်ပါ..."
        )

        # -----------------------------------------
        # ⚙️ yt-dlp settings
        # -----------------------------------------

        ydl_opts = {
            'format': 'bestaudio/best',

            'outtmpl': 'song.%(ext)s',

            'default_search': 'ytsearch1',

            'noplaylist': True,

            'quiet': False,

            'no_warnings': False,
        }

        # -----------------------------------------
        # ⬇️ Download
        # -----------------------------------------

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            print(
                f"🎵 Searching: {song_name}"
            )

            ydl.download([song_name])

        # -----------------------------------------
        # 🔎 Download လုပ်ထားတဲ့ file ရှာ
        # -----------------------------------------

        audio_file = None

        possible_files = [
            "song.mp3",
            "song.m4a",
            "song.webm",
            "song.opus"
        ]

        for filename in possible_files:

            if os.path.exists(filename):

                audio_file = filename
                break

        # -----------------------------------------
        # ❌ File မတွေ့ရင်
        # -----------------------------------------

        if audio_file is None:

            print(
                "❌ Download ပြီးပေမယ့် audio file မတွေ့ပါ။"
            )

            bot.send_message(
                message.chat.id,
                "❌ သီချင်း download မအောင်မြင်ဘူး။\n"
                "Console မှာ Error ကိုကြည့်ပါ။"
            )

            return

        # -----------------------------------------
        # 🎧 Telegram ကို ပို့
        # -----------------------------------------

        print(
            f"✅ Audio found: {audio_file}"
        )

        with open(audio_file, "rb") as audio:

            bot.send_audio(
                message.chat.id,
                audio,
                caption="🎧 သီချင်းရပြီ။ နားထောင်တော့"
            )

        # -----------------------------------------
        # 🗑️ File ဖျက်
        # -----------------------------------------

        try:

            os.remove(audio_file)

            print(
                f"🗑️ Deleted: {audio_file}"
            )

        except Exception as e:

            print(
                f"⚠️ File delete error: {e}"
            )

        # -----------------------------------------
        # 🗑️ Waiting message ဖျက်
        # -----------------------------------------

        try:

            bot.delete_message(
                message.chat.id,
                reply_msg.message_id
            )

        except:

            pass

    # -----------------------------------------
    # ❌ ERROR
    # -----------------------------------------

    except Exception as e:

        print(
            "\n================================="
        )

        print(
            f"❌ DOWNLOAD ERROR: {e}"
        )

        print(
            "=================================\n"
        )

        try:

            bot.reply_to(
                message,
                "❌ သီချင်း download မအောင်မြင်ဘူး။\n"
                "Console မှာ Error အစစ်ကိုကြည့်ပါ။"
            )

        except:

            pass

# --- ၃။ ဖျော်ဖြေရေးစနစ်များ (Entertainment Functions) ---

# 🎲 အန်စာတုံး လှိမ့်ဂိမ်းရလဒ်ပြစနစ် (/dice)
@bot.message_handler(commands=['dice', 'အန်စာတုံး'])
def roll_dice(message):
    try:
        user_name = message.from_user.first_name
        dice_msg = bot.send_dice(message.chat.id, emoji='🎲')
        dice_value = dice_msg.dice.value

        time.sleep(3)
        bot.reply_to(dice_msg, f"🎲 တောသား <b>{user_name}</b> ရဲ့ အန်စာတုံးရလဒ်ကတော့ <b>{dice_value} မှတ်</b> ဖြစ်ပါတယ်။", parse_mode='HTML')
    except Exception as e:
        print(f"Dice Error: {e}")

# 🎰 ကာစီနို စလော့ဂိမ်းရလဒ်ပြစနစ် (/slot)
@bot.message_handler(commands=['slot', 'စလော့'])
def roll_slot(message):
    try:
        user_name = message.from_user.first_name
        slot_msg = bot.send_dice(message.chat.id, emoji='🎰')
        slot_value = slot_msg.dice.value

        time.sleep(2)
        # 🎯 ဤနေရာတွင် Jackpot ကျမည့် ဂဏန်းတန်ဖိုးများကို ကွက်တိ ဖြည့်သွင်းပေးထားပါသည်
        if slot_value in [1, 22, 43, 64]:
            result_text = "🎰 <b>JACKPOT!!! LUCK 999%!!!</b> လုံးဝ ပုံတူကျတယ် စောက်ရူးရေ ပေါက်သွားပြီ။"
        else:
            result_text = "🎰 မပေါက်ပါဘူး တောသားရာ၊ နောက်တစ်ယောက်ဆက်လှည့်"

        bot.reply_to(slot_msg, f"👤 <b>{user_name}</b>\n{result_text}", parse_mode='HTML')
    except Exception as e:
        print(f"Slot Error: {e}")

# ❤️ ချစ်ခြင်းမေတ္တာ တွက်ချက်စနစ် (/love @user1 @user2)
@bot.message_handler(commands=['love', 'တွဲပေး'])
def love_calculator(message):
    try:
        love_percentage = random.randint(1, 100)
        user_text = message.text.split(maxsplit=1)

        if len(user_text) > 1:
            targets = str (user_text[1])
            response_text = f"❤️ <b>တွက်ချက်မှုရလဒ် -</b>\n\n💞 {targets} တို့နှစ်ယောက်ရဲ့ လိုက်ဖက်ညီမှု ရာခိုင်နှုန်းကတော့ <b>{love_percentage}%</b> ဖစ်ပါတယ် တောသားတို့ရေ။"
        else:
            response_text = f"❤️ ကျေးဇူးပြု၍ မိမိတွက်ချက်လိုသော နာမည် (၂) ခုကို ရိုက်ပေးပါဗျာ။\nဥပမာ - `/love ကောင်လေး ကောင်မလေး` သို့မဟုတ် `/love @သူငယ်ချင်း၁ @သူငယ်ချင်း၂`"

        bot.send_message(message.chat.id, response_text, parse_mode='HTML')
    except Exception as e:
        print(f"Love Calc Error: {e}")
# =========================================================
# 🛡️ GROUP MANAGEMENT SYSTEM
# =========================================================

# ဆဲစာ / မသင့်တော်သော စကားလုံးများ
BAN_WORDS = [
    "လီး",
    "စောက်ဖုတ်",
    "ငါလိုးမသား",
    "ကိုမေကိုလိုး" ,
    "မအေလိုး" ,
    "ဖေလိုးမ" ,
    "စပ့" ,
    "စပ" ,
    "ဇိုးခြောက်" ,
    "ဖာသည်" ,
    "ဖာသယ်" ,
    "ဖာပျက်" ,
    "ကုလား" ,

]

# ---------------------------------------------------------
# 👮 Admin စစ်တဲ့ function
# ---------------------------------------------------------
def is_admin(message):
    if message.chat.type not in ["group", "supergroup"]:
        return False

    try:
        member = bot.get_chat_member(
            message.chat.id,
            message.from_user.id
        )

        return member.status in ["administrator", "creator"]

    except Exception as e:
        print(f"Admin Check Error: {e}")
        return False


# ---------------------------------------------------------
# 🚫 BAN
# အသုံးပြုပုံ: target user ကို Reply လုပ်ပြီး /ban
# ---------------------------------------------------------
@bot.message_handler(commands=["ဘမ်း"])
def ban_user(message):

    if message.chat.type not in ["group", "supergroup"]:
        bot.reply_to(message, "❌ Group ထဲမှာပဲ သုံးလို့ရပါတယ်။")
        return

    if not is_admin(message):
        bot.reply_to(message, "❌ တောသားကများ အက်မင်မဟုတ်ရင် လီးပဲရမယ်")
        return

    if not message.reply_to_message:
        bot.reply_to(
            message,
            "❌ Ban လုပ်ချင်တဲ့ user ရဲ့ message ကို Reply လုပ်ပြီး /ban ရိုက်ပါ။"
        )
        return

    target = message.reply_to_message.from_user

    try:
        bot.ban_chat_member(
            message.chat.id,
            target.id
        )

        bot.reply_to(
            message,
            f"🚫 {target.first_name} စောက်တောသား အားအားယားယား အာချောင်နေတာ ဘမ်းပြီ လစ်တော့"
        )

    except Exception as e:
        print(f"Ban Error: {e}")
        bot.reply_to(
            message,
            "❌ Ban လုပ်လို့မရပါဘူး။ Bot ကို Admin ပေးထားပြီး Ban Users permission ရှိ/မရှိ စစ်ပါ။"
        )


# ---------------------------------------------------------
# 🔓 UNBAN
# အသုံးပြုပုံ: user message ကို Reply လုပ်ပြီး /unban
# ---------------------------------------------------------
@bot.message_handler(commands=["မဘမ်း"])
def unban_user(message):

    if message.chat.type not in ["group", "supergroup"]:
        bot.reply_to(message, "❌ Group ထဲမှာပဲ သုံးလို့ရပါတယ်။")
        return

    if not is_admin(message):
        bot.reply_to(message, "❌ တောသားကများ အက်မင်မဟုတ်ရင် လီးပဲရမယ်။")
        return

    if not message.reply_to_message:
        bot.reply_to(
            message,
            "❌ Unban လုပ်ချင်တဲ့ user ရဲ့ message ကို Reply လုပ်ပြီး /unban ရိုက်ပါ။"
        )
        return

    target = message.reply_to_message.from_user

    try:
        bot.unban_chat_member(
            message.chat.id,
            target.id,
            only_if_banned=True
        )

        bot.reply_to(
            message,
            f"🔓 {target.first_name} တောသား သနားလို့နော်"
        )

    except Exception as e:
        print(f"Unban Error: {e}")
        bot.reply_to(
            message,
            "❌ Unban လုပ်လို့မရပါဘူး။ Bot permission ကို စစ်ပါ။"
        )


# ---------------------------------------------------------
# 🔇 MUTE
# အသုံးပြုပုံ: user message ကို Reply လုပ်ပြီး /mute
# ---------------------------------------------------------
@bot.message_handler(commands=["တိတ်စမ်း", "မြု"])
def mute_user(message):

    if message.chat.type not in ["group", "supergroup"]:
        bot.reply_to(message, "❌ Group ထဲမှာပဲ သုံးလို့ရပါတယ်။")
        return

    if not is_admin(message):
        bot.reply_to(message, "❌  တောသားအက်ကများ အက်မင်မဟုတ်ရင် လီးပဲရမယ်")
        return

    if not message.reply_to_message:
        bot.reply_to(
            message,
            "❌ စာမထောက်ဘဲ မင်းမေလင်ကို တိတ်စမ်း လုပ်ရမာလား တောသား"
        )
        return

    target = message.reply_to_message.from_user

    try:
        permissions = ChatPermissions(
            can_send_messages=False
        )

        bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=permissions
        )

        bot.reply_to(
            message,
            f"🔇 {target.first_name} ကို Mute လိုက်ပြီ စောက်ပေါစောက်ရမ်းစကားများတယ်။"
        )

    except Exception as e:
        print(f"Mute Error: {e}")
        bot.reply_to(
            message,
            "❌ Mute လုပ်လို့မရဘူး မင်းဘော့ကို Admin ရာထူးနဲ့ Permissions မပေးထားလို့ အလုပ်မလုပ်ဘူး စောက်ရူးရဲ့။"
        )


# ---------------------------------------------------------
# 🔊 UNMUTE
# အသုံးပြုပုံ: user message ကို Reply လုပ်ပြီး /unmute
# ---------------------------------------------------------
@bot.message_handler(commands=["ဖွင့်လိုက်", "မမြု"])
def unmute_user(message):

    if message.chat.type not in ["group", "supergroup"]:
        bot.reply_to(message, "❌ Group ထဲမှာပဲ သုံးလို့ရပါတယ်။")
        return

    if not is_admin(message):
        bot.reply_to(message, "❌  တောသားအက်ကများ အက်မင်မဟုတ်ရင် လီးပဲရမယ်")
        return

    if not message.reply_to_message:
        bot.reply_to(
            message,
            "❌ စာမထောက်ဘဲ မင်းမေလင်ကို ပြန်ဖွင့် ရမာလား တောသား"
        )
        return

    target = message.reply_to_message.from_user

    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )

        bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=permissions
        )

        bot.reply_to(
            message,
            f"🔊 {target.first_name} စကားပြန်ပြောခွင့် ပေးလိုက်ပြီ တောသား လိမ္မာအောင်နေတော့။"
        )

    except Exception as e:
        print(f"Unmute Error: {e}")
        bot.reply_to(
            message,
            "❌ Unmute လုပ်လို့မရပါဘူး။ Bot permission ကို စစ်ပါ။"
        )


# =========================================================
# NEW 11 FUNCTIONS - FINAL VERSION
# =========================================================

GAME_DELETE_TIME = 120
INFO_DELETE_TIME = 180
WELCOME_DELETE_TIME = 240

BOT_START_TIME = time.time()


# =========================================================
# AUTO DELETE HELPERS
# =========================================================

def send_game_message(chat_id, text, **kwargs):
    try:
        sent = bot.send_message(
            chat_id,
            text,
            **kwargs
        )

        delay_delete_message(
            chat_id,
            sent.message_id,
            GAME_DELETE_TIME
        )

        return sent

    except Exception as e:
        print(f"Game Message Error: {e}")
        return None


def reply_game_message(message, text, **kwargs):
    try:
        sent = bot.reply_to(
            message,
            text,
            **kwargs
        )

        delay_delete_message(
            message.chat.id,
            sent.message_id,
            GAME_DELETE_TIME
        )

        return sent

    except Exception as e:
        print(f"Game Reply Error: {e}")
        return None


def send_info_message(chat_id, text, **kwargs):
    try:
        sent = bot.send_message(
            chat_id,
            text,
            **kwargs
        )

        delay_delete_message(
            chat_id,
            sent.message_id,
            INFO_DELETE_TIME
        )

        return sent

    except Exception as e:
        print(f"Info Message Error: {e}")
        return None


def reply_info_message(message, text, **kwargs):
    try:
        sent = bot.reply_to(
            message,
            text,
            **kwargs
        )

        delay_delete_message(
            message.chat.id,
            sent.message_id,
            INFO_DELETE_TIME
        )

        return sent

    except Exception as e:
        print(f"Info Reply Error: {e}")
        return None


# =========================================================
# 1. COIN
# =========================================================

coin_games = {}

COIN_ALIASES = {
    "ခေါင်း": "ခေါင်း",
    "heads": "ခေါင်း",

    "အမြီး": "အမြီး",
    "tails": "အမြီး",
}


# =========================================================
# 🪙 FLIP COIN
# =========================================================

def flip_coin():
    # OS-backed unbiased 50/50 bit. Independent from the bot's normal PRNG state.
    return "ခေါင်း" if secrets.randbelow(2) == 0 else "အမြီး"


# =========================================================
# 🔎 FIND ACTIVE COIN GAME FOR USER
# =========================================================

def find_coin_games_for_user(
    chat_id,
    user
):
    games = []

    for game_id, game in list(
        coin_games.items()
    ):
        if game["chat_id"] != chat_id:
            continue

        # -----------------------------------------
        # Player 1
        # -----------------------------------------

        if user.id == game["challenger_id"]:
            games.append(
                (
                    game_id,
                    game,
                    "challenger",
                )
            )
            continue

        # -----------------------------------------
        # Player 2 - ID known
        # -----------------------------------------

        if (
            game["target_id"] is not None
            and user.id == game["target_id"]
        ):
            games.append(
                (
                    game_id,
                    game,
                    "target",
                )
            )
            continue

        # -----------------------------------------
        # Player 2 - username challenge
        # -----------------------------------------

        if (
            game["target_username"]
            and user.username
            and user.username.lower()
            == game["target_username"].lower()
        ):
            games.append(
                (
                    game_id,
                    game,
                    "target",
                )
            )

    return games


# =========================================================
# 🧹 DOES USER ALREADY HAVE COIN GAME?
# =========================================================

def user_has_coin_game(
    chat_id,
    user_id=None,
    username=None
):
    username = (
        username.lower()
        if username
        else None
    )

    for game in coin_games.values():

        if game["chat_id"] != chat_id:
            continue

        if (
            user_id is not None
            and (
                game["challenger_id"] == user_id
                or game["target_id"] == user_id
            )
        ):
            return True

        if (
            username
            and game["target_username"]
            and game["target_username"].lower()
            == username
        ):
            return True

    return False


# =========================================================
# 🪙 /coin COMMAND
# =========================================================

@bot.message_handler(commands=["coin"])
def coin_command(message):

    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME,
    )

    args = message.text.split()

    # =====================================================
    # /coin
    #
    # Reply -> PvP challenge
    # No reply -> Help
    # =====================================================

    if len(args) == 1:

        # -----------------------------------------
        # REPLY CHALLENGE
        # -----------------------------------------

        if message.reply_to_message:

            target = (
                message.reply_to_message.from_user
            )

            challenger = message.from_user

            if target.is_bot:
                reply_game_message(
                    message,
                    "❌ Bot ကို Coin challenge "
                    "လုပ်လို့မရပါဘူး။",
                )
                return

            if target.id == challenger.id:
                reply_game_message(
                    message,
                    "😂 ကိုယ့်ကိုယ်ကို challenge "
                    "လုပ်လို့မရဘူး။",
                )
                return

            if message.chat.type not in (
                "group",
                "supergroup",
            ):
                reply_game_message(
                    message,
                    "❌ လူချင်း Coin ကစားတာကို "
                    "Group ထဲမှာပဲ သုံးပါ။",
                )
                return

            # -------------------------------------
            # Player တစ်ယောက်မှာ active Coin
            # game တစ်ခုထက်ပိုမရှိစေရ
            # -------------------------------------

            if user_has_coin_game(
                message.chat.id,
                user_id=challenger.id,
                username=challenger.username,
            ):
                reply_game_message(
                    message,
                    "⚠️ မင်းမှာ Coin game "
                    "တစ်ခုရှိပြီးသားပါ။",
                )
                return

            if user_has_coin_game(
                message.chat.id,
                user_id=target.id,
                username=target.username,
            ):
                reply_game_message(
                    message,
                    "⚠️ အဲဒီ Player က Coin game "
                    "တစ်ခုကစားနေပြီးသားပါ။",
                )
                return

            target_username = (
                target.username.lower()
                if target.username
                else None
            )

            game_id = (
                f"coin_{message.chat.id}_"
                f"{challenger.id}_{target.id}_"
                f"{int(time.time())}"
            )

            coin_games[game_id] = {
                "chat_id": message.chat.id,

                "challenger_id": challenger.id,

                "target_id": target.id,

                "target_username":
                    target_username,

                "challenger_choice": None,
                "target_choice": None,

                "created": time.time(),
            }

            target_name = (
                target.first_name
                or "Player 2"
            )

            reply_game_message(
                message,
                f"🪙 COIN CHALLENGE!\n\n"
                f"👤 {challenger.first_name}\n"
                f"⚔️ vs {target_name}\n\n"
                f"နှစ်ယောက်လုံးက\n"
                f"🔴 ခေါင်း / 🔵 အမြီး\n"
                f"ထဲက တစ်ခုရွေးပါ။\n\n"
                f"နှစ်ယောက်လုံးရွေးပြီးမှ "
                f"Result ပြမယ်။",
            )

            return

        # -----------------------------------------
        # HELP
        # -----------------------------------------

        reply_game_message(
            message,
            "🪙 COIN FLIP\n\n"
            "🤖 Bot နဲ့ကစားရန်\n"
            "/coin ခေါင်း\n"
            "/coin အမြီး\n\n"
            "👥 သူငယ်ချင်းနဲ့ကစားရန်\n"
            "/coin @username\n\n"
            "👤 Username ရှိ/မရှိ မလိုပါဘူး။\n"
            "သူ့ message ကို Reply လုပ်ပြီး "
            "/coin လို့လည်း Challenge "
            "လုပ်နိုင်ပါတယ်။",
        )

        return

    choice = args[1].strip().lower()

    # =====================================================
    # 🤖 COIN VS BOT
    # =====================================================

    if choice in COIN_ALIASES:

        player_choice = (
            COIN_ALIASES[choice]
        )

        result = flip_coin()

        if player_choice == result:

            result_text = (
                "🎉 မင်းမှန်တယ်! +5 Points"
            )

            apply_game_result(
                message.chat.id,
                message.from_user.id,
                "coin",
                "win",
            )

        else:

            result_text = (
                "😂 မမှန်ဘူး! -1 Point"
            )

            apply_game_result(
                message.chat.id,
                message.from_user.id,
                "coin",
                "loss",
            )

        reply_game_message(
            message,
            f"🪙 COIN FLIP\n\n"
            f"👤 မင်း — {player_choice}\n"
            f"🪙 Coin — {result}\n\n"
            f"{result_text}",
        )

        return

    # =====================================================
    # 👥 COIN VS @USERNAME
    # =====================================================

    if choice.startswith("@"):

        if message.chat.type not in (
            "group",
            "supergroup",
        ):
            reply_game_message(
                message,
                "❌ လူချင်း Coin ကစားတာကို "
                "Group ထဲမှာပဲ သုံးပါ။",
            )
            return

        target_username = (
            choice[1:]
            .strip()
            .lower()
        )

        challenger = message.from_user

        if not target_username:
            reply_game_message(
                message,
                "❌ Username ထည့်ပေးပါ။",
            )
            return

        if (
            challenger.username
            and challenger.username.lower()
            == target_username
        ):
            reply_game_message(
                message,
                "😂 ကိုယ့်ကိုယ်ကို challenge "
                "လုပ်လို့မရဘူး။",
            )
            return

        if user_has_coin_game(
            message.chat.id,
            user_id=challenger.id,
            username=challenger.username,
        ):
            reply_game_message(
                message,
                "⚠️ မင်းမှာ Coin game "
                "တစ်ခုရှိပြီးသားပါ။",
            )
            return

        if user_has_coin_game(
            message.chat.id,
            username=target_username,
        ):
            reply_game_message(
                message,
                "⚠️ အဲဒီ Player က Coin game "
                "တစ်ခုကစားနေပြီးသားပါ။",
            )
            return

        game_id = (
            f"coin_{message.chat.id}_"
            f"{challenger.id}_"
            f"{target_username}_"
            f"{int(time.time())}"
        )

        coin_games[game_id] = {
            "chat_id": message.chat.id,

            "challenger_id":
                challenger.id,

            # Username challenge ဖြစ်လို့
            # target ရွေးတဲ့အချိန်မှ ID သိမယ်
            "target_id": None,

            "target_username":
                target_username,

            "challenger_choice": None,
            "target_choice": None,

            "created": time.time(),
        }

        reply_game_message(
            message,
            f"🪙 COIN CHALLENGE!\n\n"
            f"👤 {challenger.first_name}\n"
            f"⚔️ vs @{target_username}\n\n"
            f"နှစ်ယောက်လုံးက\n"
            f"🔴 ခေါင်း / 🔵 အမြီး\n"
            f"ထဲက တစ်ခုရွေးပါ။\n\n"
            f"နှစ်ယောက်လုံးရွေးပြီးမှ "
            f"Result ပြမယ်။",
        )

        return

    # =====================================================
    # ❌ INVALID COMMAND
    # =====================================================

    reply_game_message(
        message,
        "❌ Coin command မမှန်ပါ။\n\n"
        "/coin ခေါင်း\n"
        "/coin အမြီး\n"
        "/coin @username\n\n"
        "သို့မဟုတ်\n"
        "သူ့ message ကို Reply လုပ်ပြီး /coin",
    )


# =========================================================
# 👤 PLAYER CHOICE HANDLER
# =========================================================

@bot.message_handler(
    func=lambda message:
        message.text
        and message.text.strip().lower()
        in (
            "ခေါင်း",
            "အမြီး",
            "heads",
            "tails",
        )
)
def coin_player_choice(message):

    if message.chat.type not in (
        "group",
        "supergroup",
    ):
        return

    games = find_coin_games_for_user(
        message.chat.id,
        message.from_user,
    )

    if not games:
        return

    # Player ကို active Coin game
    # တစ်ခုတည်းပဲရှိအောင် အပေါ်မှာ
    # ကာထားပြီးသား။
    if len(games) != 1:
        return

    game_id, game, player_type = (
        games[0]
    )

    choice = COIN_ALIASES[
        message.text.strip().lower()
    ]

    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME,
    )

    # =====================================================
    # PLAYER 1
    # =====================================================

    if player_type == "challenger":

        if (
            game["challenger_choice"]
            is not None
        ):
            return

        game["challenger_choice"] = choice

        send_game_message(
            message.chat.id,
            "🔒 Player 1 choice ပြီးပြီ။",
        )

    # =====================================================
    # PLAYER 2
    # =====================================================

    else:

        if (
            game["target_choice"]
            is not None
        ):
            return

        game["target_choice"] = choice

        # Username challenge ဖြစ်ခဲ့ရင်
        # အခု ID အစစ်ကို သိမ်းမယ်။
        game["target_id"] = (
            message.from_user.id
        )

        send_game_message(
            message.chat.id,
            "🔒 Player 2 choice ပြီးပြီ။",
        )

    # =====================================================
    # BOTH PLAYERS READY?
    # =====================================================

    if (
        game["challenger_choice"]
        is None
        or game["target_choice"]
        is None
    ):
        return

    result = flip_coin()

    p1 = game["challenger_choice"]
    p2 = game["target_choice"]

    p1_correct = (
        p1 == result
    )

    p2_correct = (
        p2 == result
    )

    # =====================================================
    # BOTH CORRECT = DRAW
    # =====================================================

    if p1_correct and p2_correct:

        result_text = (
            "🤝 နှစ်ယောက်လုံးမှန်တယ်!\n"
            "Points မတိုး/မနုတ်ပါ။"
        )

        apply_game_result(
            message.chat.id,
            game["challenger_id"],
            "coin",
            "draw",
        )

        apply_game_result(
            message.chat.id,
            game["target_id"],
            "coin",
            "draw",
        )

    # =====================================================
    # PLAYER 1 WINS
    # =====================================================

    elif p1_correct:

        result_text = (
            "🏆 Player 1 နိုင်တယ်!\n"
            "Player 1 +5 Points\n"
            "Player 2 -1 Point"
        )

        apply_game_result(
            message.chat.id,
            game["challenger_id"],
            "coin",
            "win",
        )

        apply_game_result(
            message.chat.id,
            game["target_id"],
            "coin",
            "loss",
        )

    # =====================================================
    # PLAYER 2 WINS
    # =====================================================

    elif p2_correct:

        result_text = (
            "🏆 Player 2 နိုင်တယ်!\n"
            "Player 2 +5 Points\n"
            "Player 1 -1 Point"
        )

        apply_game_result(
            message.chat.id,
            game["challenger_id"],
            "coin",
            "loss",
        )

        apply_game_result(
            message.chat.id,
            game["target_id"],
            "coin",
            "win",
        )

    # =====================================================
    # BOTH WRONG = BOTH LOSE
    # =====================================================

    else:

        result_text = (
            "😂 နှစ်ယောက်လုံး မမှန်ဘူး!\n"
            "နှစ်ယောက်လုံး -1 Point"
        )

        apply_game_result(
            message.chat.id,
            game["challenger_id"],
            "coin",
            "loss",
        )

        apply_game_result(
            message.chat.id,
            game["target_id"],
            "coin",
            "loss",
        )

    send_game_message(
        message.chat.id,
        f"🪙 COIN RESULT\n\n"
        f"👤 Player 1 — {p1}\n"
        f"👤 Player 2 — {p2}\n\n"
        f"🪙 Coin — {result}\n\n"
        f"{result_text}",
    )

    coin_games.pop(
        game_id,
        None,
    )     


# =========================================================
# RPS REMOVED
# =========================================================

# =========================================================
# 3. 8 BALL - 200 RESPONSES
# =========================================================

EIGHT_BALL_MESSAGES = [

    " ဟုတ်တယ်။",
    " မဟုတ်ဘူး။",
    " ဖြစ်နိုင်တယ်။",
    " ဖြစ်နိုင်ချေများတယ်။",
    " ဖြစ်နိုင်ချေနည်းတယ်။",
    " အခုတော့ မသေချာသေးဘူး။",
    " နောက်မှ ပြန်မေး။",
    " အချိန်ကပဲ အဖြေပေးလိမ့်မယ်။",
    " အခြေအနေကောင်းတယ်။",
    " အခြေအနေမကောင်းသေးဘူး။",
    " Yes ဘက်ကို ပိုနီးတယ်။",
    " No ဘက်ကို ပိုနီးတယ်။",
    " မျှော်လင့်လို့ရတယ်။",
    " အရမ်းမမျှော်လင့်နဲ့။",
    " ကံကောင်းရင် ဖြစ်မယ်။",
    " ကံပေါ်မူတည်တယ်။",
    " ဒီမေးခွန်းက ခက်တယ်။",
    " ငါတောင် မသေချာဘူး။",
    " နည်းနည်းစောင့်ကြည့်ဦး။",
    " ဒီတစ်ခါတော့ အဖြေက မရှင်းဘူး။"
]

EIGHT_BALL_BASE = [

    "မေးခွန်းက စိတ်ဝင်စားစရာပဲ",
    "အခြေအနေကို ကြည့်ရမယ်",
    "ကံကြမ္မာက ဆုံးဖြတ်လိမ့်မယ်",
    "ဒီကိစ္စက မလွယ်ဘူး",
    "နည်းနည်းစောင့်ကြည့်",
    "အခုတော့ အချိန်မကျသေးဘူး",
    "မင်းရဲ့ကံကို စမ်းကြည့်",
    "ဒီအဖြေကို မှတ်ထား",
    "အရမ်းမစဉ်းစားနဲ့",
    "အရမ်းလည်း မမျှော်လင့်နဲ့",
    "ဒီတစ်ခါတော့ ဒီလိုပဲ",
    "ငါ့ဘောလုံးက ဒီလိုပြောတယ်",
    "အဖြေက လျှို့ဝှက်နေတယ်",
    "ကံကြမ္မာက စောင့်နေတယ်",
    "မေးခွန်းကို ပြန်စဉ်းစားဦး",
    "ဒီကိစ္စကို အေးအေးဆေးဆေးကြည့်",
    "အဖြေက မကြာခင်ပေါ်လာမယ်",
    "အခုတော့ ခန့်မှန်းလို့ပဲရတယ်",
    "မင်းကံကို မေးကြည့်",
    "အခြေအနေပြောင်းနိုင်တယ်"
]

EIGHT_BALL_ENDINGS = [

    "😂 ငါလည်း မသေချာဘူး",
    "🤣 ဒီဘောလုံးတောင် စိတ်ရှုပ်နေပြီ",
    "😎 ဒီအဖြေကို ယုံချင်ယုံ",
    "🤨 ငါ့ကိုတော့ မအပြစ်တင်နဲ့",
    "😂 ထပ်မေးလည်း ဖြစ်နိုင်တယ်",
    "🤣 မေးခွန်းက ငါ့ကိုတောင် ဒုက္ခပေးတယ်",
    "😏 အဖြေကတော့ အဲ့လိုပဲ",
    "🤡 ကံကြမ္မာရဲ့ decision ပဲ",
    "💀 အဖြေကြားပြီး စိတ်မပျက်နဲ့",
    "🔥 ဒီအဖြေက နည်းနည်းကြမ်းတယ်",
    "🙃 ဘာပဲဖြစ်ဖြစ် အဖြေတော့ ရပြီ",
    "😂 အဲ့ဒါပဲ ငါပြောနိုင်တယ်",
    "🤣 နောက်တစ်ခါမှ ထပ်မေး",
    "😈 ဒီအဖြေမှာ နည်းနည်းလျှို့ဝှက်ချက်ရှိတယ်",
    "🤔 ငါတောင် ပြန်စဉ်းစားနေတယ်",
    "😎 ဒီနေ့အတွက် ဒီလောက်ပဲ",
    "😂 မင်းကလည်း မေးခွန်းတွေများတယ်",
    "🤣 8 Ball ကို မနှိပ်စက်နဲ့",
    "🗿 အဖြေက အဖြေပါပဲ",
    "🎯 တိတိကျကျ ပြောလိုက်ပြီ"
]

for base in EIGHT_BALL_BASE:

    for ending in EIGHT_BALL_ENDINGS:

        if len(EIGHT_BALL_MESSAGES) >= 200:
            break

        EIGHT_BALL_MESSAGES.append(
            f" {base} — {ending}"
        )

    if len(EIGHT_BALL_MESSAGES) >= 200:
        break

EIGHT_BALL_MESSAGES = (
    EIGHT_BALL_MESSAGES[:200]
)


@bot.message_handler(commands=["8ball", "ဗေဒင်"])
def eight_ball_command(message):

    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    parts = message.text.split(
        maxsplit=1
    )

    if len(parts) == 1:

        reply_game_message(
            message,
            "🎱 မေးခွန်းထည့်ပြီးမေးဟ လီလားး\n\n"
            "ဥပမာ\n"
            "/ဗေဒင် ရီးဇားဟောင်းပြန်လာမှာလား?"
        )

        return

    answer = random.choice(
        EIGHT_BALL_MESSAGES
    )

    reply_game_message(
        message,
        f"🎱 8 BALL\n\n"
        f"❓ {parts[1]}\n\n"
        f"{answer}"
    )


# =========================================================
# 4. GUESS - MULTIPLAYER + RANK / POINT SYSTEM
# =========================================================

guess_games = {}


# ---------------------------------------------------------
# /guess COMMAND
# ---------------------------------------------------------

@bot.message_handler(commands=["guess", "ခန့်မှန်း"])
def guess_command(message):

    # Group ထဲမှာပဲ ကစားခွင့်
    if message.chat.type not in [
        "group",
        "supergroup"
    ]:

        reply_game_message(
            message,
            "❌ Group ထဲမှာပဲ Guess Game ကစားလို့ရပါတယ်။"
        )

        return

    # /guess command ကို auto delete
    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    chat_id = message.chat.id

    # -----------------------------------------------------
    # Game တစ်ခုရှိပြီးသားလား
    # -----------------------------------------------------

    if chat_id in guess_games:

        reply_game_message(
            message,
            "🎯 Guess Game ကစားနေပြီးသားပါ။\n\n"
            "👥 Group ထဲက ဘယ်သူမဆို ဝင်ခန့်မှန်းလို့ရပါတယ်။\n"
            "🏆 တစ်ယောက်မှန်သွားရင် Game ပြီးပါပြီ။"
        )

        return

    # -----------------------------------------------------
    # Game အသစ်စ
    # -----------------------------------------------------

    guess_games[chat_id] = {

        "number":
            random.randint(
                1,
                100
            ),

        "tries":
            0,

        "created":
            time.time()
    }

    reply_game_message(
        message,

        "🎯 GUESS GAME စပြီ!\n\n"

        "1 ကနေ 100 အတွင်းက number "
        "တစ်ခု ငါရွေးထားပြီ။\n\n"

        "👥 Group ထဲက ဘယ်သူမဆို "
        "ဝင်ခန့်မှန်းလို့ရတယ်။\n"

        "🔢 1 ကနေ 100 အတွင်းက "
        "number ပို့ပါ။\n\n"

        "🏆 အရင်ဆုံးမှန်တဲ့သူက Winner!\n"

        "⭐ Winner = +10 Points"
    )


# ---------------------------------------------------------
# NUMBER ANSWER HANDLER
# ---------------------------------------------------------

@bot.message_handler(
    func=lambda message:

        message.text
        is not None

        and message.text
        .strip()
        .isdigit()
)
def guess_number(message):

    chat_id = message.chat.id

    # Guess game မရှိရင်
    # ပုံမှန် number message အဖြစ်ထား
    if chat_id not in guess_games:
        return

    # -----------------------------------------------------
    # Number ပြောင်း
    # -----------------------------------------------------

    try:

        number = int(
            message.text.strip()
        )

    except (
        TypeError,
        ValueError
    ):

        return

    # -----------------------------------------------------
    # 1 - 100 Check
    # -----------------------------------------------------

    if (
        number < 1
        or number > 100
    ):

        reply_game_message(
            message,
            "❌ 1 ကနေ 100 အတွင်းက number ပဲ ပို့ပါ။"
        )

        return

    # User ရဲ့ number message ကို
    # game delete time နောက်မှဖျက်
    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    # Race safety အတွက်
    # game ကို ပြန်ယူ
    game = guess_games.get(
        chat_id
    )

    if not game:
        return

    # Guess count
    game["tries"] += 1

    target = game["number"]

    # =====================================================
    # ✅ CORRECT
    # =====================================================

    if number == target:

        winner = (
            message.from_user
        )

        # Username ရှိရင် @username
        if winner.username:

            winner_display = (
                f"@{winner.username}"
            )

        # Username မရှိရင် First Name
        else:

            winner_display = (
                winner.first_name
                or "Unknown User"
            )

        # -----------------------------------------
        # 🏆 RANK / POINT SYSTEM
        # -----------------------------------------

        try:
            apply_game_result(
                chat_id,
                winner.id,
                "guess",
                "win",
            )
        except Exception as e:
            print(
                f"Guess Point Error: {e}"
            )


        # -------------------------------------------------
        # Winner Result
        # -------------------------------------------------

        reply_game_message(
            message,

            "🎯 CORRECT!\n\n"

            f"🏆 Number က {target} ပါ!\n"

            f"📊 {game['tries']} ကြိမ်နဲ့ "
            "မှန်သွားပြီ!\n\n"

            f"👑 Winner — {winner_display}\n"

            "⭐ +10 Points"
        )

        # Game ပိတ်
        guess_games.pop(
            chat_id,
            None
        )

        return

    # =====================================================
    # 📈 TOO LOW
    # =====================================================

    if number < target:

        reply_game_message(
            message,
            "📈 ပိုကြီးတဲ့ number ဖြစ်တယ်။"
        )

    # =====================================================
    # 📉 TOO HIGH
    # =====================================================

    else:

        reply_game_message(
            message,
            "📉 ပိုသေးတဲ့ number ဖြစ်တယ်။"
        )


# =========================================================
# 🧠 TRIVIA - ONLINE + LOCAL FALLBACK
# =========================================================

TRIVIA_TIME = 180
TRIVIA_QUESTION_DELETE_TIME = TRIVIA_TIME + 60

trivia_games = {}
trivia_starting_chats = set()
trivia_used_questions = set()
trivia_session_token = None
trivia_lock = threading.Lock()


def make_trivia_question_key(source, question_text, correct_answer):
    return (
        f"{source}|"
        f"{str(question_text).strip()}|"
        f"{str(correct_answer).strip()}"
    )


def delete_trivia_answer_message(message):
    try:
        bot.delete_message(
            message.chat.id,
            message.message_id
        )
    except Exception:
        pass


def send_trivia_result(chat_id, text):
    try:
        sent = bot.send_message(
            chat_id,
            text
        )

        delay_delete_message(
            chat_id,
            sent.message_id,
            INFO_DELETE_TIME
        )

        return sent

    except Exception as e:
        print(
            f"Trivia Result Send Error: {e}"
        )
        return None


# ---------------------------------------------------------
# SESSION TOKEN
# ---------------------------------------------------------

def get_trivia_session_token():
    global trivia_session_token

    try:
        url = (
            "https://opentdb.com/"
            "api_token.php?command=request"
        )

        with urllib.request.urlopen(
            url,
            timeout=8
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        if data.get("response_code") == 0:

            trivia_session_token = (
                data.get("token")
            )

            return trivia_session_token

    except Exception as e:

        print(
            f"Trivia Token Error: {e}"
        )

    trivia_session_token = None

    return None


def reset_trivia_session_token():
    global trivia_session_token

    if not trivia_session_token:
        return False

    try:

        encoded_token = (
            urllib.parse.quote(
                trivia_session_token
            )
        )

        url = (
            "https://opentdb.com/"
            "api_token.php?command=reset"
            f"&token={encoded_token}"
        )

        with urllib.request.urlopen(
            url,
            timeout=8
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        if data.get("response_code") == 0:
            return True

    except Exception as e:

        print(
            f"Trivia Token Reset Error: {e}"
        )

    trivia_session_token = None

    return False


# ---------------------------------------------------------
# ONLINE QUESTION
# ---------------------------------------------------------

def get_online_trivia_question():
    global trivia_session_token

    # Duplicate / token error ဖြစ်ရင်
    # အများဆုံး 4 ကြိမ် ထပ်စမ်းမယ်
    for _ in range(4):

        try:

            if not trivia_session_token:
                get_trivia_session_token()

            token_part = ""

            if trivia_session_token:

                token_part = (
                    "&token="
                    + urllib.parse.quote(
                        trivia_session_token
                    )
                )

            url = (
                "https://opentdb.com/"
                "api.php?amount=1"
                "&type=multiple"
                "&encode=url3986"
                f"{token_part}"
            )

            with urllib.request.urlopen(
                url,
                timeout=10
            ) as response:

                data = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

            response_code = (
                data.get("response_code")
            )

            # Invalid Token
            if response_code == 3:

                trivia_session_token = None
                get_trivia_session_token()

                continue

            # Questions ကုန်သွားရင်
            if response_code == 4:

                if not reset_trivia_session_token():

                    trivia_session_token = None
                    get_trivia_session_token()

                continue

            if response_code != 0:
                return None

            results = data.get(
                "results",
                []
            )

            if not results:
                return None

            q = results[0]

            question_text = (
                html.unescape(
                    urllib.parse.unquote(
                        q["question"]
                    )
                )
            )

            correct_answer = (
                html.unescape(
                    urllib.parse.unquote(
                        q["correct_answer"]
                    )
                )
            )

            incorrect_answers = [

                html.unescape(
                    urllib.parse.unquote(
                        answer
                    )
                )

                for answer in
                q["incorrect_answers"]
            ]

            question_key = (
                make_trivia_question_key(
                    "online",
                    question_text,
                    correct_answer
                )
            )

            # မေးပြီးသား question ဆို
            # နောက်တစ်ခုထပ်ယူ
            if (
                question_key
                in trivia_used_questions
            ):
                continue

            answers = (
                incorrect_answers
                + [correct_answer]
            )

            random.shuffle(
                answers
            )

            correct_index = (
                answers.index(
                    correct_answer
                )
            )

            return {

                "question":
                    question_text,

                "answers":
                    answers,

                "correct_index":
                    correct_index,

                "question_key":
                    question_key,

                "source":
                    "online"
            }

        except Exception as e:

            print(
                f"Trivia Online Error: {e}"
            )

            return None

    return None


# ---------------------------------------------------------
# LOCAL DATABASE
# ---------------------------------------------------------

def load_local_trivia_questions():

    file_path = (
        "trivia_questions.json"
    )

    if not os.path.exists(
        file_path
    ):
        return []

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )

        if isinstance(
            data,
            list
        ):
            return data

    except Exception as e:

        print(
            f"Trivia Local DB Error: {e}"
        )

    return []


def get_local_trivia_question():

    questions = (
        load_local_trivia_questions()
    )

    if not questions:
        return None

    valid_questions = []

    for item in questions:

        if not isinstance(
            item,
            dict
        ):
            continue

        question_text = (
            str(
                item.get(
                    "question",
                    ""
                )
            ).strip()
        )

        answers = (
            item.get(
                "answers"
            )
        )

        try:

            correct_index = int(
                item.get(
                    "correct_index"
                )
            )

        except (
            TypeError,
            ValueError
        ):
            continue

        if not question_text:
            continue

        if (
            not isinstance(
                answers,
                list
            )
            or len(answers) != 4
        ):
            continue

        if correct_index not in range(4):
            continue

        answers = [

            str(answer)

            for answer
            in answers
        ]

        correct_answer = (
            answers[
                correct_index
            ]
        )

        question_key = (
            make_trivia_question_key(
                "local",
                question_text,
                correct_answer
            )
        )

        valid_questions.append({

            "question":
                question_text,

            "answers":
                answers,

            "correct_index":
                correct_index,

            "question_key":
                question_key,

            "source":
                "local"
        })

    if not valid_questions:
        return None

    available = [

        item

        for item
        in valid_questions

        if item[
            "question_key"
        ]
        not in trivia_used_questions
    ]

    # Local question အားလုံး
    # မေးပြီးသွားရင်
    # local keys တွေပဲ reset
    if not available:

        local_keys = {

            item[
                "question_key"
            ]

            for item
            in valid_questions
        }

        trivia_used_questions.difference_update(
            local_keys
        )

        available = (
            valid_questions
        )

    return dict(
        random.choice(
            available
        )
    )


def get_trivia_question():

    # 50% Online / 50% Local
    source = random.choice([
        "online",
        "local"
    ])

    # =====================================
    # ONLINE ကို random ရွေးမိရင်
    # =====================================

    if source == "online":

        question = (
            get_online_trivia_question()
        )

        if question:

            print(
                "🌐 Trivia Source: ONLINE"
            )

            return question

        # Online မရရင် Local fallback
        print(
            "⚠️ Online Trivia unavailable. "
            "Using Local Trivia."
        )

        question = (
            get_local_trivia_question()
        )

        if question:

            print(
                "📁 Trivia Source: LOCAL"
            )

            return question

        return None

    # =====================================
    # LOCAL ကို random ရွေးမိရင်
    # =====================================

    else:

        question = (
            get_local_trivia_question()
        )

        if question:

            print(
                "📁 Trivia Source: LOCAL"
            )

            return question

        # Local file မရရင် Online fallback
        print(
            "⚠️ Local Trivia unavailable. "
            "Using Online Trivia."
        )

        question = (
            get_online_trivia_question()
        )

        if question:

            print(
                "🌐 Trivia Source: ONLINE"
            )

            return question

        return None


# ---------------------------------------------------------
# TRANSLATION
# ---------------------------------------------------------

def translate_to_myanmar(text):

    if not text:
        return text

    text = str(
        text
    )

    # မြန်မာစာ ဖြစ်ပြီးသားဆို
    # ထပ်ဘာသာမပြန်
    if any(
        "\u1000"
        <= char
        <= "\u109F"

        for char
        in text
    ):
        return text

    try:

        encoded_text = (
            urllib.parse.quote(
                text
            )
        )

        url = (
            "https://api.mymemory.translated.net/"
            "get"
            f"?q={encoded_text}"
            "&langpair=en|my"
        )

        with urllib.request.urlopen(
            url,
            timeout=8
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        translated = (

            data.get(
                "responseData",
                {}
            )

            .get(
                "translatedText"
            )
        )

        if translated:

            return (
                html.unescape(
                    translated
                )
            )

    except Exception as e:

        print(
            f"Trivia Translation Error: {e}"
        )

    return text


def translate_trivia_question(
    question
):

    result = dict(
        question
    )

    result[
        "question"
    ] = translate_to_myanmar(
        question[
            "question"
        ]
    )

    result[
        "answers"
    ] = [

        translate_to_myanmar(
            answer
        )

        for answer
        in question[
            "answers"
        ]
    ]

    return result


# ---------------------------------------------------------
# FORMAT QUESTION
# ---------------------------------------------------------

def format_trivia_message(
    game,
    remaining
):
    """Readable text-only Trivia layout."""
    letters = ["A", "B", "C", "D"]

    remaining = max(0, int(remaining))
    minutes = remaining // 60
    seconds = remaining % 60

    lines = [
        "🧠  TRIVIA CHALLENGE",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "❓ မေးခွန်း",
        str(game.get("question", "")).strip(),
        "",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for index, answer in enumerate(game.get("answers", [])[:4]):
        lines.append(f"{letters[index]})  {str(answer).strip()}")
        lines.append("")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━",
        f"⏳ ကျန်ချိန်  {minutes:02d}:{seconds:02d}",
        "",
        "💬 ဖြေဆိုရန် — A / B / C / D ထဲက တစ်လုံးပဲ ပို့ပါ။",
        "👤 လူတစ်ယောက် တစ်ကြိမ်ပဲ ဖြေနိုင်ပါတယ်။",
        "🏆 ပထမဆုံးအဖြေမှန်သူ  +10 Points",
    ])

    return "\n".join(lines)



# ---------------------------------------------------------
# COUNTDOWN
# ---------------------------------------------------------

def trivia_countdown(
    chat_id,
    message_id
):

    while True:

        current_game = None

        with trivia_lock:

            game = (
                trivia_games.get(
                    chat_id
                )
            )

            if not game:
                return

            if (
                game[
                    "message_id"
                ]
                != message_id
            ):
                return

            remaining = int(
                game[
                    "end_time"
                ]
                - time.time()
            )

            if remaining <= 0:

                current_game = (
                    trivia_games.pop(
                        chat_id,
                        None
                    )
                )

            else:

                game_snapshot = (
                    dict(
                        game
                    )
                )

                game_snapshot[
                    "answers"
                ] = list(
                    game[
                        "answers"
                    ]
                )

        # ---------------------------------
        # TIME UP
        # ---------------------------------

        if current_game is not None:

            try:

                # Question ကို
                # TIME UP စာအဖြစ်
                # မပြောင်းဘူး
                #
                # Timer 00:00 ပဲထားမယ်

                bot.edit_message_text(

                    format_trivia_message(
                        current_game,
                        0
                    ),

                    chat_id,
                    message_id
                )

            except Exception as e:

                if (
                    "message is not modified"
                    not in str(e).lower()
                ):

                    print(
                        "Trivia Final "
                        f"Timer Error: {e}"
                    )

            # TIME UP ကို
            # စာအသစ်နဲ့ပို့
            send_trivia_result(

                chat_id,

                "⏰ TIME UP!\n\n"

                "❌ ၃ မိနစ်အတွင်း "
                "ဘယ်သူမှ "
                "အဖြေမမှန်ပါဘူး။\n\n"

                f"✅ အဖြေမှန် — "
                f"{current_game['correct_letter']}. "
                f"{current_game['answers'][current_game['correct_index']]}\n\n"

                "🧠 နောက် Trivia ကို "
                "/trivia နဲ့ စနိုင်ပါပြီ။"
            )

            return

        # ---------------------------------
        # TIMER UPDATE
        # ---------------------------------

        try:

            bot.edit_message_text(

                format_trivia_message(
                    game_snapshot,
                    remaining
                ),

                chat_id,
                message_id
            )

        except Exception as e:

            if (
                "message is not modified"
                not in str(e).lower()
            ):

                print(
                    "Trivia Countdown "
                    f"Error: {e}"
                )

        # နောက်ဆုံး 30 sec မှာ
        # 5 sec ခြား update
        #
        # ပုံမှန် 10 sec ခြား

        if remaining <= 30:
            sleep_time = 5
        else:
            sleep_time = 10

        time.sleep(
            sleep_time
        )


# ---------------------------------------------------------
# /trivia COMMAND
# ---------------------------------------------------------

@bot.message_handler(
    commands=[
        "trivia"
    ]
)
def trivia_command(
    message
):

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:

        reply_game_message(

            message,

            "❌ Group ထဲမှာပဲ "
            "Trivia ကစားလို့ရပါတယ်။"
        )

        return

    chat_id = (
        message.chat.id
    )

    # /trivia command message ကို
    # ပုံမှန် game delete time
    # နဲ့ဖျက်မယ်
    #
    # Question ကိုတော့
    # ဒီ timer မသုံးဘူး

    delay_delete_message(

        chat_id,
        message.message_id,
        GAME_DELETE_TIME
    )

    # ---------------------------------
    # Active game / Starting check
    # ---------------------------------

    with trivia_lock:

        active_game = (
            trivia_games.get(
                chat_id
            )
        )

        is_starting = (
            chat_id
            in trivia_starting_chats
        )

        if (
            active_game is None
            and not is_starting
        ):

            trivia_starting_chats.add(
                chat_id
            )

    # ---------------------------------
    # Game ရှိပြီးသား
    # ---------------------------------

    if active_game is not None:

        remaining = max(

            0,

            int(
                active_game[
                    "end_time"
                ]
                - time.time()
            )
        )

        minutes = (
            remaining // 60
        )

        seconds = (
            remaining % 60
        )

        reply_game_message(

            message,

            "⚠️ Trivia Game "
            "ကစားနေပြီးသားပါ။\n\n"

            f"⏳ ကျန်ချိန် — "
            f"{minutes:02d}:"
            f"{seconds:02d}\n\n"

            "လက်ရှိမေးခွန်းကိုပဲ "
            "ဖြေပါ။"
        )

        return

    # ---------------------------------
    # Question ယူနေတုန်း
    # ---------------------------------

    if is_starting:

        reply_game_message(

            message,

            "⏳ Trivia question "
            "ယူနေတုန်းပါ။ "
            "ခဏလေးစောင့်ပါ။"
        )

        return

    try:

        # ---------------------------------
        # Question ယူ
        # ---------------------------------

        question = (
            get_trivia_question()
        )

        if not question:

            reply_game_message(

                message,

                "❌ Trivia question "
                "ရယူလို့မရသေးပါဘူး။\n"

                "ခဏနေပြီး ပြန်စမ်းပါ။"
            )

            return

        # ---------------------------------
        # Myanmar Translation
        # ---------------------------------

        question = (
            translate_trivia_question(
                question
            )
        )

        # ---------------------------------
        # Data validation
        # ---------------------------------

        try:

            correct_index = int(
                question[
                    "correct_index"
                ]
            )

        except (
            KeyError,
            TypeError,
            ValueError
        ):

            reply_game_message(

                message,

                "❌ Trivia question "
                "data မမှန်ပါဘူး။ "
                "ပြန်စမ်းပါ။"
            )

            return

        answers = (
            question.get(
                "answers",
                []
            )
        )

        if (
            correct_index
            not in range(4)
            or len(answers) != 4
        ):

            reply_game_message(

                message,

                "❌ Trivia answer "
                "data မပြည့်စုံပါဘူး။ "
                "ပြန်စမ်းပါ။"
            )

            return

        correct_letter = (

            [
                "A",
                "B",
                "C",
                "D"
            ]

            [
                correct_index
            ]
        )

        # ---------------------------------
        # Game Data
        # ---------------------------------

        game = {

            "question":
                question[
                    "question"
                ],

            "answers":
                answers,

            "correct_index":
                correct_index,

            "correct_letter":
                correct_letter,

            "question_key":
                question.get(
                    "question_key"
                ),

            "end_time":
                time.time()
                + TRIVIA_TIME,

            "attempted_users":
                set(),

            "message_id":
                None,

            "source":
                question.get(
                    "source",
                    "unknown"
                )
        }

        # =================================
        # IMPORTANT FIX
        # =================================
        #
        # ဒီနေရာမှာ
        # reply_game_message()
        # လုံးဝ မသုံးရ
        #
        # အဲဒါက
        # GAME_DELETE_TIME = 120
        # ဖြစ်လို့
        # Trivia question ကို
        # 2 မိနစ်မှာ
        # ဖျက်သွားတယ်
        # =================================

        try:

            sent = bot.reply_to(

                message,

                format_trivia_message(
                    game,
                    TRIVIA_TIME
                )
            )

        except Exception as e:

            print(
                f"Trivia Send Error: {e}"
            )

            return

        game[
            "message_id"
        ] = sent.message_id

        # =================================
        # Trivia = 3 minutes
        #
        # Question message =
        # 4 minutes မှဖျက်
        #
        # ဒါကြောင့်
        # Game မပြီးခင်
        # ပျောက်တော့မယ်မဟုတ်ဘူး
        # =================================

        delay_delete_message(

            chat_id,
            sent.message_id,
            TRIVIA_QUESTION_DELETE_TIME
        )

        # ---------------------------------
        # Save Game
        # ---------------------------------

        with trivia_lock:

            # Safety Check
            # Game နှစ်ခုမဖြစ်အောင်

            if chat_id in trivia_games:

                try:

                    bot.delete_message(
                        chat_id,
                        sent.message_id
                    )

                except Exception:
                    pass

                return

            trivia_games[
                chat_id
            ] = game

            question_key = (
                game.get(
                    "question_key"
                )
            )

            if question_key:

                trivia_used_questions.add(
                    question_key
                )

        # ---------------------------------
        # Start Countdown
        # ---------------------------------

        threading.Thread(

            target=
                trivia_countdown,

            args=(
                chat_id,
                sent.message_id
            ),

            daemon=True

        ).start()

    finally:

        with trivia_lock:

            trivia_starting_chats.discard(
                chat_id
            )


# ---------------------------------------------------------
# TRIVIA ANSWER
# A / B / C / D
# ---------------------------------------------------------

@bot.message_handler(
    func=lambda message:

        message.chat.type
        in [
            "group",
            "supergroup"
        ]

        and message.text
        is not None

        and (
            message.text
            .strip()
            .upper()
        )

        in [
            "A",
            "B",
            "C",
            "D"
        ]
)
def trivia_answer(message):

    chat_id = message.chat.id
    user_id = message.from_user.id

    answer = (
        message.text
        .strip()
        .upper()
    )

    winner_game = None

    # ---------------------------------
    # Answer Check
    # ---------------------------------

    with trivia_lock:

        game = trivia_games.get(
            chat_id
        )

        # Trivia game မရှိရင်
        # A/B/C/D message ကို
        # ဒီတိုင်းထားမယ်
        if not game:
            return

        # Time up ဖြစ်ပြီးသားဆို
        # message ကိုလည်း မဖျက်ဘူး
        if (
            time.time()
            >= game["end_time"]
        ):
            return

        # ---------------------------------
        # လူတစ်ယောက် တစ်ခါပဲ
        # ---------------------------------

        if (
            user_id
            in game["attempted_users"]
        ):
            # Message မဖျက်ဘူး
            # Answer ကိုလည်း ထပ်မစစ်ဘူး
            return

        # ဒီ user ဖြေပြီးပြီလို့မှတ်
        game["attempted_users"].add(
            user_id
        )

        # ---------------------------------
        # Correct Answer Check
        # ---------------------------------

        if (
            answer
            == game["correct_letter"]
        ):

            # Winner ရသွားပြီဆို
            # active trivia ကို ပိတ်
            winner_game = (
                trivia_games.pop(
                    chat_id,
                    None
                )
            )

    # =====================================
    # IMPORTANT
    #
    # User ရဲ့ A / B / C / D message ကို
    # ဒီနေရာမှာ လုံးဝ မဖျက်ဘူး
    # =====================================

    # မှားတဲ့ answer ဆို
    # ဘာမှ reply မလုပ်ဘူး
    # သူ့ A/B/C/D message က group ထဲမှာ
    # ဒီတိုင်းကျန်နေမယ်
    if winner_game is None:
        return

    # ---------------------------------
    # WINNER
    # ---------------------------------

    winner = message.from_user

    winner_name = (
        winner.first_name
        or "Unknown"
    )

    # ---------------------------------
    # +10 Points
    # ---------------------------------    


    apply_game_result(
            chat_id,
            winner.id,
            "trivia",
            "win",
        )

    
    # ---------------------------------
    # Winner ကို စာအသစ်နဲ့ပို့
    # Correct answer message ကိုလည်း
    # မဖျက်ဘူး
    # ---------------------------------

    send_trivia_result(

        chat_id,

        "🏆 TRIVIA WINNER!\n\n"

        f"👑 Winner — "
        f"{winner_name}\n\n"

        f"✅ အဖြေမှန် — "
        f"{winner_game['correct_letter']}. "
        f"{winner_game['answers'][winner_game['correct_index']]}\n\n"

        "⭐ +10 Points"
    )
    

# =========================================================
# ⚡ SPEED TAP
# =========================================================

speed_tap_visual_state = {}
speed_tap_visual_lock = threading.RLock()


def clear_speed_tap_visual_state(chat_id):

    with speed_tap_visual_lock:
        speed_tap_visual_state.pop(
            chat_id,
            None,
        )


def get_speed_tap_visual_state(chat_id):

    with speed_tap_visual_lock:
        return speed_tap_visual_state.get(
            chat_id,
            {}
        ).copy()


# =========================================================
# ⚡ /speedtap COMMAND
# =========================================================

@bot.message_handler(commands=["speedtap"])
def speed_tap_command(message=None, auto_chat_id=None):

    auto_mode = auto_chat_id is not None
    if auto_mode:
        chat_id = auto_chat_id
    else:
        if message is None or message.chat.type not in ("group", "supergroup"):
            if message is not None:
                bot.reply_to(message, "❌ Group ထဲမှာပဲ ကစားလို့ရပါတယ်။")
            return False
        chat_id = message.chat.id
        delay_delete_message(
            chat_id, message.message_id, random.randint(5, 10),
        )


    existing_game = get_speed_tap_game(
        chat_id
    )

    # -----------------------------------------
    # Pending ဖြစ်နေပြီးသား
    #
    # schedule အသစ်မလုပ်
    # ∞ card အသစ်လည်းမထုတ်
    # -----------------------------------------

    if existing_game:

        state = existing_game.get(
            "state"
        )

        if state == "pending":
            return

        # -------------------------------------
        # WAIT / GO round တကယ်စနေပြီ
        # -------------------------------------

        try:
            notice = bot.send_message(
                chat_id,
                "⚡ Speed Tap ပွဲက စနေပြီးသားပါ။"
            )

            delay_delete_message(
                chat_id,
                notice.message_id,
                random.randint(5, 10),
            )

        except Exception:
            pass

        return

    # -----------------------------------------
    # Hidden random delay 10–180 sec
    # -----------------------------------------

    pending_seconds = random.randint(
        SPEED_TAP_PENDING_MIN,
        SPEED_TAP_PENDING_MAX,
    )

    created, game = create_speed_tap_game(
        chat_id,
        pending_seconds,
    )

    if not created:
        return

    # -----------------------------------------
    # ∞ card background
    # -----------------------------------------

    pending_background = (
        get_speed_tap_background()
    )

    try:

        pending_card = (
            generate_speed_tap_pending_card_bytes(
                background_path=
                    pending_background,
            )
        )

        pending_message = bot.send_photo(
            chat_id,
            pending_card,
            caption=(
                "⚡ <b>SPEED TAP</b>\n"
                "∞ <b>RANDOM START</b>"
            ),
            parse_mode="HTML",
        )

    except Exception as e:

        print(
            f"Speed Tap Pending Card Error: {e}"
        )

        end_speed_tap_game(
            chat_id
        )

        return

    set_speed_tap_pending_message_id(
        chat_id,
        pending_message.message_id,
    )

    # =====================================================
    # 🌌 RANDOM MOMENT -> WAIT ROUND
    # =====================================================

    def begin_speed_tap_round():

        current_game = get_speed_tap_game(
            chat_id
        )

        if not current_game:
            return

        if current_game.get(
            "state"
        ) != "pending":
            return

        # -------------------------------------
        # ∞ card ဖျက်
        # -------------------------------------

        try:
            bot.delete_message(
                chat_id,
                pending_message.message_id,
            )
        except Exception:
            pass

        # -------------------------------------
        # WAIT length 3–8 sec
        # -------------------------------------

        wait_seconds = random.randint(
            SPEED_TAP_WAIT_MIN,
            SPEED_TAP_WAIT_MAX,
        )

        waiting_game = start_speed_tap_wait(
            chat_id,
            wait_seconds,
        )

        if not waiting_game:
            return

        # -------------------------------------
        # WAIT / GO / RESULT အတွက်
        # background တစ်ပုံတည်းသုံး
        # -------------------------------------

        game_background = (
            get_speed_tap_background()
        )

        with speed_tap_visual_lock:

            speed_tap_visual_state[
                chat_id
            ] = {
                "background_path":
                    game_background,
            }

        # -------------------------------------
        # WAIT card အသစ်
        # -------------------------------------

        try:

            wait_card = (
                generate_speed_tap_wait_card_bytes(
                    wait_seconds=
                        wait_seconds,
                    background_path=
                        game_background,
                )
            )

            game_message = bot.send_photo(
                chat_id,
                wait_card,
                caption=(
                    "⚡ <b>SPEED TAP</b>\n"
                    "⏳ WAIT... GO ပေါ်လာမှနှိပ်!"
                ),
                parse_mode="HTML",
                reply_markup=
                    speed_tap_keyboard(
                        chat_id,
                        active=True,
                    ),
            )

        except Exception as e:

            print(
                f"Speed Tap WAIT Card Error: {e}"
            )

            clear_speed_tap_visual_state(
                chat_id
            )

            end_speed_tap_game(
                chat_id
            )

            return

        set_speed_tap_message_id(
            chat_id,
            game_message.message_id,
        )

        # =====================================
        # ⏰ ACTIVE ROUND TIMEOUT
        # =====================================

        def speed_tap_timeout():

            expired_game = expire_speed_tap(
                chat_id
            )

            if not expired_game:
                return

            visual = (
                get_speed_tap_visual_state(
                    chat_id
                )
            )

            background_path = visual.get(
                "background_path"
            )

            try:

                timeout_card = (
                    generate_speed_tap_timeout_card_bytes(
                        background_path=
                            background_path,
                    )
                )

                media = (
                    telebot.types.InputMediaPhoto(
                        media=timeout_card,
                        caption=(
                            "⏰ <b>TIME'S UP!</b>\n"
                            "ဘယ်သူမှ အချိန်မီ "
                            "မနှိပ်လိုက်ဘူး 😴"
                        ),
                        parse_mode="HTML",
                    )
                )

                bot.edit_message_media(
                    media=media,
                    chat_id=chat_id,
                    message_id=
                        game_message.message_id,
                    reply_markup=
                        speed_tap_keyboard(
                            chat_id,
                            active=False,
                        ),
                )

                delay_delete_message(
                    chat_id,
                    game_message.message_id,
                    90,
                )

            except Exception as e:
                print(
                    f"Speed Tap Timeout Error: {e}"
                )

            clear_speed_tap_visual_state(
                chat_id
            )

            end_speed_tap_game(
                chat_id
            )

        # =====================================
        # 🟢 WAIT -> GO
        # =====================================

        def speed_tap_go():

            current_game = (
                get_speed_tap_game(
                    chat_id
                )
            )

            if not current_game:
                return

            if current_game.get(
                "state"
            ) != "waiting":
                return

            visual = (
                get_speed_tap_visual_state(
                    chat_id
                )
            )

            background_path = visual.get(
                "background_path"
            )

            # ---------------------------------
            # GO card ကို Telegram မှာ
            # အရင်တကယ်ပြ
            # ---------------------------------

            try:

                go_card = (
                    generate_speed_tap_go_card_bytes(
                        background_path=
                            background_path,
                    )
                )

                media = (
                    telebot.types.InputMediaPhoto(
                        media=go_card,
                        caption=(
                            "🟢 <b>GO! GO! GO!</b>\n"
                            "⚡ TAP NOW!"
                        ),
                        parse_mode="HTML",
                    )
                )

                bot.edit_message_media(
                    media=media,
                    chat_id=chat_id,
                    message_id=
                        game_message.message_id,
                    reply_markup=
                        speed_tap_keyboard(
                            chat_id,
                            active=True,
                        ),
                )

            except Exception as e:

                print(
                    f"Speed Tap GO Card Error: {e}"
                )

                clear_speed_tap_visual_state(
                    chat_id
                )

                end_speed_tap_game(
                    chat_id
                )

                return

            # ---------------------------------
            # IMPORTANT:
            #
            # GO card update အောင်မြင်ပြီးမှ
            # reaction timer စ
            # ---------------------------------

            active_game = activate_speed_tap(
                chat_id,
                active_time=
                    SPEED_TAP_ACTIVE_TIME,
            )

            if not active_game:
                return

            schedule_task(
                SPEED_TAP_ACTIVE_TIME,
                speed_tap_timeout,
                task_id=
                    f"speedtap_timeout:{chat_id}",
                replace=True,
            )

        # -------------------------------------
        # WAIT -> GO schedule
        # -------------------------------------

        schedule_task(
            wait_seconds,
            speed_tap_go,
            task_id=
                f"speedtap_go:{chat_id}",
            replace=True,
        )

    # -----------------------------------------
    # Hidden 10–180 sec random start
    # -----------------------------------------

    schedule_task(
        pending_seconds,
        begin_speed_tap_round,
        task_id=
            f"speedtap_pending:{chat_id}",
        replace=True,
    )
    return True


# =========================================================
# ⚡ SPEED TAP CALLBACK
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
        bool(call.data)
        and call.data.startswith(
            "speedtap:"
        )
)
def speed_tap_callback(call):

    parts = call.data.split(":")

    if len(parts) != 3:

        bot.answer_callback_query(
            call.id,
            "❌ Invalid Speed Tap."
        )

        return

    try:

        callback_chat_id = int(
            parts[1]
        )

    except ValueError:

        bot.answer_callback_query(
            call.id,
            "❌ Invalid Speed Tap."
        )

        return

    action = parts[2]

    if action == "closed":

        bot.answer_callback_query(
            call.id,
            "🏁 ဒီ round ပြီးသွားပြီ။"
        )

        return

    if action != "tap":

        bot.answer_callback_query(
            call.id,
            "❌ Invalid action."
        )

        return

    if (
        call.message.chat.id
        != callback_chat_id
    ):

        bot.answer_callback_query(
            call.id,
            "❌ ဒီ game မဟုတ်ပါ။"
        )

        return

    chat_id = callback_chat_id
    user_id = call.from_user.id

    user_name = (
        call.from_user.first_name
        or call.from_user.username
        or "Player"
    )

    result = register_speed_tap(
        chat_id,
        user_id,
        user_name,
    )

    status = result.get(
        "status"
    )

    # -----------------------------------------
    # No game
    # -----------------------------------------

    if status == "no_game":

        bot.answer_callback_query(
            call.id,
            "🏁 Game ပြီးသွားပြီ။"
        )

        return

    # -----------------------------------------
    # Pending
    # Normally pending card မှာ button မရှိ
    # safety fallback ပဲ
    # -----------------------------------------

    if status == "pending":

        bot.answer_callback_query(
            call.id,
            "∞ စောင့်ကြည့်ဦး 👀"
        )

        return

    # -----------------------------------------
    # WAIT phase - too early
    #
    # Exact remaining time မပြ
    # -----------------------------------------

    if status == "too_early":

        bot.answer_callback_query(
            call.id,
            "😏 စောသေးတယ်! GO ကိုစောင့်ဦး"
        )

        return

    # -----------------------------------------
    # Finished
    # -----------------------------------------

    if status == "finished":

        bot.answer_callback_query(
            call.id,
            "🏁 တခြားသူ အရင်နှိပ်သွားပြီ။"
        )

        return

    # -----------------------------------------
    # Expired
    # -----------------------------------------

    if status == "expired":

        bot.answer_callback_query(
            call.id,
            "⏰ အချိန်ကုန်သွားပြီ။"
        )

        return

    if status != "winner":
        return

    # =====================================================
    # 🏆 WINNER
    # =====================================================

    reaction_ms = int(
        result.get(
            "reaction_ms",
            0,
        )
    )

    reward_points = int(
        result.get(
            "reward_points",
            0,
        )
    )

    jackpot_bonus = int(
        result.get(
            "jackpot_bonus",
            0,
        )
    )

    cancel_task(
        f"speedtap_timeout:{chat_id}"
    )

    cancel_task(
        f"speedtap_go:{chat_id}"
    )

    cancel_task(
        f"speedtap_pending:{chat_id}"
    )

    bot.answer_callback_query(
        call.id,
        "⚡ မင်းအရင်ဆုံးနှိပ်လိုက်တယ်!"
    )

    # -----------------------------------------
    # RANDOM REWARD
    #
    # fixed +10 မဟုတ်တော့
    # win/game stats လည်းတက်မယ်
    # -----------------------------------------

    try:

        apply_custom_game_result(
            chat_id,
            user_id,
            "win",
            reward_points,
        )

    except Exception as e:

        print(
            f"Speed Tap Reward Error: {e}"
        )

    visual = get_speed_tap_visual_state(
        chat_id
    )

    background_path = visual.get(
        "background_path"
    )

    # -----------------------------------------
    # Result card
    # -----------------------------------------

    try:

        result_card = (
            generate_speed_tap_result_card_bytes(
                winner_name=user_name,
                reaction_ms=reaction_ms,
                reward_points=
                    reward_points,
                jackpot_bonus=
                    jackpot_bonus,
                background_path=
                    background_path,
            )
        )

        if jackpot_bonus > 0:

            jackpot_text = (
                f"\n✨ Jackpot Bonus: "
                f"<b>+{jackpot_bonus}</b>"
            )

        else:

            jackpot_text = ""

        media = (
            telebot.types.InputMediaPhoto(
                media=result_card,
                caption=(
                    "⚡ <b>SPEED TAP RESULT</b>\n\n"
                    f"🏆 Winner: "
                    f"<b>{user_name}</b>\n"
                    f"⏱ Reaction: "
                    f"<b>{reaction_ms} ms</b>\n"
                    f"⭐ Reward: "
                    f"<b>+{reward_points} Points</b>"
                    f"{jackpot_text}"
                ),
                parse_mode="HTML",
            )
        )

        bot.edit_message_media(
            media=media,
            chat_id=chat_id,
            message_id=
                call.message.message_id,
            reply_markup=
                speed_tap_keyboard(
                    chat_id,
                    active=False,
                ),
        )

        delay_delete_message(
            chat_id,
            call.message.message_id,
            90,
        )

    except Exception as e:

        print(
            f"Speed Tap Result Card Error: {e}"
        )

    clear_speed_tap_visual_state(
        chat_id
    )

    end_speed_tap_game(
        chat_id
    )

# =========================================================
# 👹 GROUP BOSS RAID — GAME HUD / REACTIONS / DEFEAT PENALTY
# =========================================================
boss_raid_edit_lock=threading.RLock()
boss_raid_last_edit={}
boss_raid_visual_state={}

def boss_raid_text(raid):
    boss=raid["boss"];hp=max(0,raid["hp"]);mx=raid["max_hp"];pct=(hp/mx*100) if mx else 0
    filled=max(0,min(16,int(round(pct/100*16))));bar="🟥"*filled+"⬛"*(16-filled)
    left=max(0,int(raid["ends_at"]-time.time()));mins,secs=divmod(left,60)
    top=boss_top_fighters(raid,3);medals=["🥇","🥈","🥉"]
    rows=[f'{medals[i]} <b>{html.escape(str(p["name"]))}</b>  •  {p["damage"]:,} DMG' for i,p in enumerate(top)]
    while len(rows)<3:rows.append(f'{medals[len(rows)]} —')
    if raid.get("result")=="victory":state="🏆 RAID CLEARED"
    elif raid.get("finished"):state="☠️ PARTY DEFEATED"
    else:state=f'⚔️ PHASE {raid["phase"]}  •  RAID LIVE'
    mod=raid.get("modifier")
    mod_text={"rage":"🔥 RAGE • damage resisted","exposed":"💢 EXPOSED • bonus damage","fortify":"🛡 FORTIFY • heavy defense"}.get(mod)
    if mod_text:state+=f'\n{mod_text} • {raid.get("modifier_hits_left",0)} hits left'
    return (
        f'╔═══ 👹 <b>GROUP BOSS RAID</b> 👹 ═══╗\n'
        f'{boss["emoji"]} <b>{html.escape(boss["name"]).upper()}</b>\n'
        f'🏷 {boss["tier"]}   │   {state}\n'
        f'╚══════════════════════╝\n\n'
        f'❤️ <b>BOSS HP</b>\n{bar}\n<b>{hp:,}</b> / {mx:,}  •  {pct:.1f}%\n\n'
        f'⏳ <b>{mins:02d}:{secs:02d}</b>   ⚔️ <b>{raid["total_damage"]:,}</b> DMG   👥 <b>{len(raid["fighters"])}</b>\n'
        f'━━━━━━━━━━━━━━━━━━━━\n'
        f'🏆 <b>TOP RAIDERS</b>\n'+"\n".join(rows)+
        '\n━━━━━━━━━━━━━━━━━━━━\n'
        +('🔥 <b>ATTACK! ATTACK! ATTACK!</b>\nတားထားတဲ့ cooldown မရှိဘူး။ Boss မလွတ်ခင် ဝိုင်းချ!' if not raid.get("finished") else '🏁 <b>RAID ENDED</b>')
    )

def boss_raid_edit(chat_id,raid,force=False):
    mid=raid.get("message_id")
    if not mid:return
    now=time.monotonic()
    with boss_raid_edit_lock:
        last=boss_raid_last_edit.get(chat_id,0)
        if not force and now-last<1.0:return
        boss_raid_last_edit[chat_id]=now
    try:
        state=boss_raid_visual_state.get(chat_id,{})
        if state:
            bot.edit_message_caption(chat_id=chat_id,message_id=mid,caption=boss_raid_text(raid),parse_mode="HTML",reply_markup=boss_attack_keyboard(raid["id"],disabled=raid.get("finished",False)))
        else:
            bot.edit_message_text(boss_raid_text(raid),chat_id,mid,parse_mode="HTML",reply_markup=boss_attack_keyboard(raid["id"],disabled=raid.get("finished",False)))
    except Exception as ex:
        if "message is not modified" not in str(ex).lower():print("Boss Raid edit error:",ex)

def boss_reaction_message(chat_id,raid,text,kind="phase"):
    boss=raid["boss"];icons={"phase":"🔥","win":"💀","lose":"👑"}
    title={"phase":"BOSS REACTION","win":"BOSS DEFEATED","lose":"BOSS VICTORY"}
    try:
        m=bot.send_message(chat_id,f'{icons[kind]} <b>{title[kind]}</b>\n{boss["emoji"]} <b>{html.escape(boss["name"])}</b>: “{html.escape(text)}”',parse_mode="HTML")
        delay_delete_message(chat_id,m.message_id,45 if kind=="phase" else 75)
    except Exception as ex:print("Boss reaction error:",ex)

def boss_raid_mute_fighters(chat_id,raid):
    until=int(time.time())+45
    try:admins={x.user.id for x in bot.get_chat_administrators(chat_id)}
    except Exception:admins=set()
    muted=0;protected=0
    for uid in raid.get("fighters",{}):
        if uid in admins:protected+=1;continue
        try:
            member=bot.get_chat_member(chat_id,uid)
            if member.status in ("administrator","creator"):
                protected+=1;continue
            mute_permissions=types.ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_topics=False,
            )
            result=bot.restrict_chat_member(
                chat_id,
                uid,
                permissions=mute_permissions,
                until_date=until,
                use_independent_chat_permissions=True,
            )
            if result:muted+=1
            else:print("Boss defeat mute returned False:",uid)
        except Exception as ex:print("Boss defeat mute error:",uid,repr(ex))
    return muted,protected

def boss_raid_finish(chat_id,raid,won):
    owned=claim_boss_raid_ending(chat_id,raid["id"])
    if not owned:return
    raid=owned
    try:end_session(chat_id,"boss_raid")
    except Exception as ex:print("Boss end_session error:",ex)

    line=boss_ending_line(raid)
    muted,protected=(0,0)
    if not won:
        try:muted,protected=boss_raid_mute_fighters(chat_id,raid)
        except Exception as ex:print("Boss penalty error:",ex)

    # IMPORTANT: keep visual state until the live PHOTO caption is finalized.
    state=boss_raid_visual_state.get(chat_id,{})
    art=state.get("art");variant=state.get("variant")
    result_art=get_boss_artwork(raid["boss"]["name"],"normal" if won else "final") or art

    try:boss_raid_edit(chat_id,raid,force=True)
    except Exception as ex:print("Boss final live-card edit error:",ex)

    # Unpin is independent: a failed edit/result render must never leave the raid pinned.
    if raid.get("message_id"):
        try:
            boss_raid_force_unpin(chat_id,raid["message_id"])
        except Exception as ex:print("Boss unpin error:",ex)

    boss_raid_visual_state.pop(chat_id,None)
    boss_raid_last_edit.pop(chat_id,None)

    # Always send a clear result. Visual rendering failure falls back to text.
    title='🏆 <b>RAID VICTORY!</b>' if won else '☠️ <b>PARTY DEFEATED!</b>'
    caption=title+f'\n\n{raid["boss"]["emoji"]} <b>{html.escape(raid["boss"]["name"])}</b>\n“{html.escape(line)}”'
    if won:
        caption+=f'\n\n⚔️ Total Damage: <b>{raid["total_damage"]:,}</b>\n👥 Raiders: <b>{len(raid["fighters"])}</b>'
    else:
        caption+=f'\n\n🔒 45s Penalty\n🤐 Muted: <b>{muted}</b>  •  🛡 Protected: <b>{protected}</b>'

    try:
        card=generate_boss_result_card(raid,won,line,muted,protected,art=result_art,variant=variant,composition=state.get("composition"))
        msg=bot.send_photo(chat_id,card,caption=caption,parse_mode="HTML")
        delay_delete_message(chat_id,msg.message_id,90)
    except Exception as ex:
        print("Boss result card error:",ex)
        try:
            msg=bot.send_message(chat_id,caption,parse_mode="HTML")
            delay_delete_message(chat_id,msg.message_id,90)
        except Exception as fallback_ex:
            print("Boss result fallback error:",fallback_ex)

def boss_raid_force_unpin(chat_id,message_id):
    if not message_id:return
    try:
        if not safe_unpin_message(bot,chat_id,message_id):
            bot.unpin_chat_message(chat_id,message_id)
    except Exception as ex:
        print("Boss force unpin error:",ex)

def boss_raid_timeout(chat_id,raid_id):
    raid=get_boss_raid(chat_id)
    if not raid or raid["id"]!=raid_id:return
    if raid.get("result")=="victory":
        boss_raid_finish(chat_id,raid,True)
        return
    if not raid.get("finished"):
        raid=finish_boss_raid(chat_id,raid_id,"timeout")
    if raid:
        boss_raid_finish(chat_id,raid,False)

@bot.message_handler(commands=['boss','bossraid','raid'])
def boss_raid_command(message):
    if message.chat.type not in ('group','supergroup'):
        bot.reply_to(message,'👹 Boss Raid ကို Group ထဲမှာပဲ ကစားလို့ရပါတယ်။');return
    chat_id=message.chat.id;allowed,blocker=can_start_session(chat_id,"boss_raid")
    if not allowed:
        sent=bot.reply_to(message,f'⏳ {blocker} game/event ရှိနေပါတယ်။');delay_delete_message(chat_id,sent.message_id,15);return
    created,raid=start_boss_raid(chat_id)
    if not created:bot.reply_to(message,'👹 Boss Raid တစ်ခု run နေပြီးသားပါ။');return
    ok,_=start_session(chat_id,"boss_raid",data={"raid_id":raid["id"]},duration=BOSS_RAID_DURATION)
    if not ok:finish_boss_raid(chat_id,raid["id"],"cancelled");return
    art=get_boss_artwork(raid["boss"]["name"],get_boss_visual_stage(raid))
    try:
        live,variant,composition=generate_boss_live_card(raid,art=art)
        sent=bot.send_photo(chat_id,live,caption=boss_raid_text(raid),parse_mode="HTML",reply_markup=boss_attack_keyboard(raid["id"]))
        boss_raid_visual_state[chat_id]={"art":art,"variant":variant,"composition":composition,"stage":get_boss_visual_stage(raid)}
    except Exception as ex:
        print("Boss live card error:",ex)
        sent=bot.send_message(chat_id,boss_raid_text(raid),parse_mode="HTML",reply_markup=boss_attack_keyboard(raid["id"]))
        boss_raid_visual_state[chat_id]={"art":art,"variant":None,"stage":get_boss_visual_stage(raid)}
    set_boss_raid_message_id(chat_id,raid["id"],sent.message_id);raid=get_boss_raid(chat_id)
    safe_pin_message(bot,chat_id,sent.message_id,disable_notification=True);delay_delete_message(chat_id,message.message_id,10)
    schedule_task(BOSS_RAID_DURATION+0.2,boss_raid_timeout,chat_id,raid["id"],task_id=f'boss_timeout:{chat_id}',replace=True)

@bot.callback_query_handler(func=lambda call: bool(call.data) and call.data.startswith("boss:"))
def boss_raid_callback(call):
    parts=call.data.split(":")
    if len(parts)!=3:bot.answer_callback_query(call.id,"❌ Invalid raid.");return
    raid_id,action=parts[1],parts[2]
    if action=="closed":bot.answer_callback_query(call.id,"🏁 ဒီ Raid ပြီးသွားပြီ။");return
    if action!="attack":bot.answer_callback_query(call.id,"❌ Invalid action.");return
    chat_id=call.message.chat.id;name=call.from_user.first_name or call.from_user.username or "Player"
    result=attack_boss_raid(chat_id,raid_id,call.from_user.id,name)
    if result["status"]!="ok":bot.answer_callback_query(call.id,"🏁 ဒီ Raid ပြီးသွားပြီ။");return
    raid=result["raid"]
    note="🛡️ Boss BLOCK!" if result["blocked"] else (f'💥 CRITICAL! -{result["damage"]} HP' if result["crit"] else f'⚔️ -{result["damage"]} HP')
    bot.answer_callback_query(call.id,note)
    # Re-render the same pinned photo only when the boss crosses a visual HP stage.
    # 24 base images become Normal / Damaged / Rage / Final variants at runtime.
    state=boss_raid_visual_state.get(chat_id,{})
    new_stage=get_boss_visual_stage(raid)
    if state and state.get("art") and state.get("stage")!=new_stage and raid.get("message_id") and not raid.get("finished"):
        try:
            stage_art=get_boss_artwork(raid["boss"]["name"],new_stage) or state.get("art")
            live,variant,composition=generate_boss_live_card(raid,art=stage_art,variant=state.get("variant"),composition=state.get("composition"))
            media=types.InputMediaPhoto(live,caption=boss_raid_text(raid),parse_mode="HTML")
            bot.edit_message_media(media=media,chat_id=chat_id,message_id=raid["message_id"],reply_markup=boss_attack_keyboard(raid["id"]))
            state["art"]=stage_art;state["stage"]=new_stage;state["variant"]=variant;state["composition"]=composition
            boss_raid_visual_state[chat_id]=state
            boss_raid_last_edit[chat_id]=time.monotonic()
        except Exception as ex:
            print("Boss visual stage edit error:",ex)
            boss_raid_edit(chat_id,raid,force=raid.get("finished",False))
    else:
        boss_raid_edit(chat_id,raid,force=raid.get("finished",False))
    reaction=result.get("reaction")
    if reaction:boss_reaction_message(chat_id,raid,reaction["text"],"phase")
    event=result.get("event")
    if event:
        try:
            extra=""
            if event.get("hits"):
                extra=f'\nEffect: {event.get("hits")} attacks'
            if event.get("heal"):
                extra=f'\nBoss recovered {event.get("heal")} HP'
            ev=bot.send_message(chat_id,f'<b>{html.escape(event["title"])}</b>\n{html.escape(event["text"])}{extra}',parse_mode="HTML")
            delay_delete_message(chat_id,ev.message_id,28)
        except Exception as ex:print("Boss event message error:",ex)
    if raid.get("finished") and raid.get("result")=="victory":
        cancel_task(f'boss_timeout:{chat_id}');boss_raid_finish(chat_id,raid,True)

# =========================================================
# 😀 EMOJI GUESS
# =========================================================
# 🔤 WORD CHAIN /wordchain en | /wordchain mm | /endwordchain
# =========================================================

# =========================================================
# 🧮 MATH BATTLE — FIVE ROUND INLINE GAME
# =========================================================
math_battle_card_lock = threading.RLock()

def math_battle_keyboard(game):
    kb = InlineKeyboardMarkup(row_width=2)
    opts = game['question']['options']
    for j in range(0, 4, 2):
        row = []
        for k in (j, j+1):
            row.append(InlineKeyboardButton(
                f'{"ABCD"[k]}. {opts[k]}',
                callback_data=f"math:{game['id']}:{game['round']}:{k}",
            ))
        kb.row(*row)
    return kb

def math_battle_deadline_watch(chat_id, game_id, round_index):
    """Independent round-end watchdog (doesn't rely on image countdown edits)."""
    game = get_math_battle(chat_id)
    if not game or game['id'] != game_id or game['round'] != round_index:
        return
    remaining = game['deadline'] - time.monotonic()
    if remaining > 0:
        schedule_task(
            remaining + 0.15, math_battle_deadline_watch,
            chat_id, game_id, round_index,
        )
        return
    math_battle_next(chat_id, game_id, round_index)


def math_battle_arm_deadline(game):
    if game:
        delay = max(0.15, game['deadline'] - time.monotonic() + 0.15)
        schedule_task(
            delay, math_battle_deadline_watch,
            game['chat_id'], game['id'], game['round'],
        )


def math_battle_next(chat_id, game_id, round_index):
    with math_battle_card_lock:
        current = get_math_battle(chat_id)
        if not current or current['id'] != game_id or current['round'] != round_index:
            return
        if time.monotonic() < current['deadline']:
            return
        try:
            status, result = advance_math_battle(chat_id, game_id, round_index)
        except Exception as e:
            print('Math next round error:', e)
            # Do not leave an unresponsive card on screen if question loading fails.
            stop_math_battle(chat_id)
            try:
                bot.send_message(chat_id, '⚠️ Math Battle နောက်တစ်ချီ ဖွင့်မရပါ။ Render Logs မှာ Math next round error ကိုစစ်ပါ။')
            except Exception:
                pass
            return
        if status == 'finished':
            old_id = current.get('message_id')
            if old_id:
                try: bot.delete_message(chat_id, old_id)
                except Exception: pass
            ranked = sorted(result['scores'].items(), key=lambda pair: (-pair[1], pair[0]))
            rewards = {}
            # Tied scores get the same rank reward; each rank group's roll is shared.
            distinct = []
            for _, score in ranked:
                if score not in distinct: distinct.append(score)
            tiers = ((15,25),(10,15),(5,10))
            for tier_index, score in enumerate(distinct[:3]):
                prize = random.randint(*tiers[tier_index])
                if random.random() < 0.05: prize += random.randint(5,15)
                tied_users = [uid for uid, pts in ranked if pts == score]
                for uid in tied_users:
                    try:
                        if tier_index == 0 and uid == tied_users[0]:
                            ok = apply_custom_game_result(chat_id, uid, 'win', prize)
                        else:
                            ok = add_bonus_points(chat_id, uid, prize, reason='math_battle')
                        if ok: rewards[uid] = prize
                    except Exception as e:
                        print('Math reward error:', e)
            try:
                sent=bot.send_photo(chat_id, math_result_card(result, rewards), caption='🏁 MATH BATTLE — FINAL RESULT')
                delay_delete_message(chat_id, sent.message_id, 120)
            except Exception as e:
                print('Math final card error:', e)
            return
        if status != 'next': return
        old_id=current.get('message_id')
        try:
            sent=bot.send_photo(chat_id, math_round_card(result), reply_markup=math_battle_keyboard(result), caption=f"🧮 MATH BATTLE · ROUND {result['round']+1}/5")
            if not set_math_message(chat_id,game_id,result['round'],sent.message_id):
                bot.delete_message(chat_id,sent.message_id)
                return
            if old_id:
                try: bot.delete_message(chat_id,old_id)
                except Exception: pass
            # `result` was captured before set_math_message(), so its
            # message_id is None. Fetch the current round after saving the
            # new photo ID; otherwise rounds 2-5 never start live ticks.
            math_battle_schedule_tick(chat_id, get_math_battle(chat_id))
            math_battle_arm_deadline(get_math_battle(chat_id))
        except Exception as e:
            print('Math round card error:',e)
            stop_math_battle(chat_id)

def math_battle_tick(chat_id, game_id, round_index, message_id):
    """Live countdown in caption only; keeps the photo static to avoid Telegram flicker/reload."""
    with math_battle_card_lock:
        game = get_math_battle(chat_id)
        if not game or game['id'] != game_id or game['round'] != round_index or game['message_id'] != message_id:
            return

        remaining = game['deadline'] - time.monotonic()
        if remaining <= 0:
            math_battle_next(chat_id, game_id, round_index)
            return

        seconds_left = max(0, int(remaining + 0.999))
        caption = (
            f"🧮 MATH BATTLE · ROUND {round_index + 1}/5\n"
            f"⏳ Time left: {seconds_left}s"
        )
        try:
            bot.edit_message_caption(
                caption=caption,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=math_battle_keyboard(game),
            )
        except Exception as e:
            if 'message is not modified' not in str(e).lower():
                print('Math countdown caption edit:', e)

        game = get_math_battle(chat_id)
        if game and game['id'] == game_id and game['round'] == round_index and game['message_id'] == message_id:
            remaining = game['deadline'] - time.monotonic()
            if remaining <= 0:
                math_battle_next(chat_id, game_id, round_index)
            else:
                step = 1 if remaining <= 10 else 5
                schedule_task(
                    min(step, max(.15, remaining)),
                    math_battle_tick,
                    chat_id, game_id, round_index, message_id,
                    task_id=f"math_live:{chat_id}:{game_id}:{round_index}:{time.monotonic_ns()}",
                )

def math_battle_schedule_tick(chat_id, game):
    if not game.get('message_id'): return
    remaining=max(.15,game['deadline']-time.monotonic())
    delay=1 if remaining<=10 else 5
    schedule_task(min(delay,remaining),math_battle_tick,chat_id,game['id'],game['round'],game['message_id'])

@bot.message_handler(commands=['mathbattle','math'])
def math_battle_command(message):
    if message.chat.type not in ('group','supergroup'):
        bot.reply_to(message,'🧮 Math Battle ကို Group ထဲမှာပဲ ကစားလို့ရပါတယ်။')
        return
    chat_id=message.chat.id
    try:
        created,game=start_math_battle(chat_id)
        if not created:
            sent=bot.reply_to(message,f'⏳ {game} game/event ရှိနေပါတယ်။')
            delay_delete_message(chat_id,sent.message_id,20)
            return
        sent=bot.send_photo(chat_id,math_round_card(game),caption='🧮 MATH BATTLE · ROUND 1/5',reply_markup=math_battle_keyboard(game))
        set_math_message(chat_id,game['id'],0,sent.message_id)
        math_battle_schedule_tick(chat_id,get_math_battle(chat_id))
        math_battle_arm_deadline(get_math_battle(chat_id))
        delay_delete_message(chat_id,message.message_id,10)
    except Exception as e:
        print('Math battle start error:',e)
        stop_math_battle(chat_id)

@bot.message_handler(commands=['endmath','stopmath'])
def math_battle_end_command(message):
    if message.chat.type not in ('group','supergroup'): return
    if not is_admin(message):
        bot.reply_to(message,'❌ Admin ပဲ ရပ်နိုင်ပါတယ်။')
        return
    g=stop_math_battle(message.chat.id)
    if g and g.get('message_id'):
        try: bot.delete_message(message.chat.id,g['message_id'])
        except Exception: pass
    bot.reply_to(message,'🛑 Math Battle ရပ်လိုက်ပြီ။' if g else 'Math Battle မရှိပါ။')

@bot.callback_query_handler(func=lambda c: bool(c.data and c.data.startswith('math:')))
def math_battle_callback(call):
    try:
        _,game_id,round_text,index_text=call.data.split(':')
        chat_id=call.message.chat.id
        if call.message.chat.type not in ('group','supergroup'): return
        status,g=answer_math_battle(chat_id,game_id,int(round_text),call.from_user.id,call.from_user.first_name,int(index_text))
        alerts={'stale':'ဒီမေးခွန်းပြီးသွားပါပြီ။','closed':'အချိန်ကုန်ပြီ။',
                'already':'တစ်ချီမှာ တစ်ကြိမ်ပဲ ဖြေလို့ရတယ်။','wrong':'❌ မမှန်ပါ။',
                'late':'မှန်တယ်။ Top 3 ပြည့်သွားပြီ။', 'correct':'✅ မှန်တယ်!'}
        bot.answer_callback_query(call.id,alerts.get(status,'OK'),show_alert=False)
        if status=='correct' and g:
            # Re-arm a deadline watchdog because the first winner reduces the timer to 10s.
            # An older watchdog for this round is harmless (it rechecks the live deadline).
            math_battle_arm_deadline(g)
            # Update immediately when a player scores; first correct activates 10-second grace.
            if time.monotonic()>=g['deadline']:
                math_battle_next(chat_id,game_id,int(round_text))
            elif g.get('message_id'):
                try:
                    bot.edit_message_media(
                        InputMediaPhoto(math_round_card(g),caption=f"🧮 MATH BATTLE · ROUND {g['round']+1}/5"),
                        chat_id=chat_id,message_id=g['message_id'],reply_markup=math_battle_keyboard(g))
                except Exception: pass
    except Exception as e:
        print('Math callback error:',e)
        try: bot.answer_callback_query(call.id,'⚠️ ပြန်စမ်းကြည့်ပါ။')
        except Exception: pass

word_chain_finish_lock = threading.RLock()
word_chain_card_lock = threading.RLock()
WORD_CHAIN_TICK_PREFIX = 'wordchain_live:'


def word_chain_scoreboard(game):
    ranked = sorted(
        game['scores'].items(),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return ranked


def word_chain_status_text(game):
    leaders = word_chain_scoreboard(game)
    standing = "\n".join(
        f"{n}. {game['names'].get(uid, 'Player')}: {score}"
        for n, (uid, score) in enumerate(leaders[:3], 1)
    ) or "No scores yet"
    mode = 'မြန်မာ (space ခြားထားတဲ့ စကားလုံး)' if game['mode'] == 'my' else 'English'
    return (
        f"🔤 WORD CHAIN — {mode}\n\n"
        f"🔗 နောက်ဆုံး: {game['word']}\n"
        f"➡️ ဆက်ရန်: {game['required']}\n"
        f"✅ Valid moves: {game['moves']}\n"
        f"⏳ အဖြေမရှိရင် {WORD_CHAIN_IDLE_SECONDS}s နဲ့ပြီးမယ်\n"
        f"🏁 Round {game['round_seconds'] // 60} မိနစ်\n\n"
        f"🏆 Top 3\n{standing}\n\n"
        "⚠️ တစ်ယောက်တည်း နှစ်ခါဆက်တိုက် မဆက်ရ။"
    )


def word_chain_tick(chat_id, game_id, expected_moves, expected_message_id):
    """Update only the caption countdown; never reload the photo for timer ticks."""
    with word_chain_card_lock:
        game = get_word_chain_game(chat_id)
        if not game or game['id'] != game_id:
            return
        if game['moves'] != expected_moves or game['message_id'] != expected_message_id:
            return

        now = time.monotonic()
        remaining = min(game['idle_deadline'], game['deadline']) - now
        if remaining <= 0:
            reason = 'limit' if now >= game['deadline'] else 'idle'
            word_chain_close(chat_id, game_id, reason)
            return

        seconds_left = max(0, int(remaining + 0.999))
        try:
            bot.edit_message_caption(
                caption=(
                    "🔤 WORD CHAIN — စကားလုံးဆက်ပါ\n"
                    f"⏳ Next answer: {seconds_left}s"
                ),
                chat_id=chat_id,
                message_id=expected_message_id,
            )
        except Exception as error:
            if 'message is not modified' not in str(error).lower():
                print(f'Word Chain Live Caption Error: {error}')

        step = 1 if remaining <= 10 else 5
        schedule_task(
            min(step, max(0.2, remaining)), word_chain_tick,
            chat_id, game_id, expected_moves, expected_message_id,
            task_id=f'{WORD_CHAIN_TICK_PREFIX}{chat_id}:{game_id}:{expected_moves}:{time.monotonic_ns()}',
        )

def word_chain_start_live(chat_id, game):
    if not game or not game.get('message_id'):
        return
    step = 1 if game['idle_deadline'] - time.monotonic() <= 10 else 5
    schedule_task(
        step, word_chain_tick,
        chat_id, game['id'], game['moves'], game['message_id'],
        task_id=f'{WORD_CHAIN_TICK_PREFIX}{chat_id}:{game["id"]}:{game["moves"]}:{time.monotonic_ns()}',
    )


def word_chain_close(chat_id, game_id, reason='timeout'):
    with word_chain_finish_lock:
        ended = finish_word_chain(chat_id, game_id)
        if not ended:
            return False
        old_id = ended.get('message_id')
        if old_id:
            try:
                bot.delete_message(chat_id, old_id)
            except Exception:
                pass
        ranked = word_chain_scoreboard(ended)
        # Competition ranks by DISTINCT word counts: ties share the same rank
        # and the same prize. Zero valid words never receive a prize.
        # One random prize is rolled PER DISTINCT RANK, not per player.
        # Players with equal word counts receive exactly the same prize,
        # including the 5% jackpot bonus (if the rank wins the jackpot).
        prize_ranges = ((15, 25), (10, 15), (5, 10))
        rank_prizes = {}
        reward_rows = []
        previous_count = None
        rank = 0
        for uid, count in ranked:
            if previous_count != count:
                rank += 1
                previous_count = count
                if count > 0 and rank <= len(prize_ranges):
                    minimum, maximum = prize_ranges[rank - 1]
                    base_points = random.randint(minimum, maximum)
                    jackpot_bonus = random.randint(5, 15) if random.random() < 0.05 else 0
                    rank_prizes[rank] = (base_points + jackpot_bonus, jackpot_bonus)
            points, jackpot_bonus = rank_prizes.get(rank, (0, 0)) if count > 0 else (0, 0)
            name = ended['names'].get(uid, 'Player')
            reward_ok = True
            if points:
                try:
                    if rank == 1:
                        reward_ok = bool(apply_custom_game_result(chat_id, uid, 'win', points))
                    else:
                        reward_ok = bool(add_bonus_points(chat_id, uid, points, reason='word_chain'))
                except Exception as error:
                    print(f'Word Chain Reward Error: {error}')
                    reward_ok = False
            reward_rows.append({
                'rank': rank, 'name': name, 'words': count,
                'points': points if reward_ok else 0,
                'jackpot': bool(jackpot_bonus) if reward_ok else False,
                'reward_error': not reward_ok,
            })
        reason_label = {
            'idle': '60 seconds no answer',
            'limit': 'Round time limit',
            'stop': 'Stopped by admin',
        }.get(reason, 'Game ended')
        try:
            result_image = word_chain_result_card(ended, reward_rows, reason_label)
            sent = bot.send_photo(chat_id, result_image, caption='🏁 WORD CHAIN RESULT')
            delay_delete_message(chat_id, sent.message_id, 90)
        except Exception as error:
            print(f'Word Chain Result Card Error: {error}')
            # Keep results accessible if Telegram photo upload fails.
            lines = [
                f"{row['rank']}. {row['name']}: {row['words']} words "
                + (f"(+{row['points']} Points)" if row['points'] else '(no reward)')
                for row in reward_rows[:10]
            ]
            try:
                sent = bot.send_message(
                    chat_id, '🏁 WORD CHAIN END — ' + reason_label + '\n\n'
                    + ('\n'.join(lines) if lines else 'No valid answers.'),
                )
                delay_delete_message(chat_id, sent.message_id, 90)
            except Exception as fallback_error:
                print(f'Word Chain Result Fallback Error: {fallback_error}')
        return True


def word_chain_idle_check(chat_id, game_id, expected_idle):
    game = get_word_chain_game(chat_id)
    if not game or game['id'] != game_id:
        return
    # Ignore stale timers that were scheduled before a valid move.
    if game['idle_deadline'] != expected_idle:
        return
    if time.monotonic() >= game['deadline']:
        word_chain_close(chat_id, game_id, 'limit')
    elif time.monotonic() >= game['idle_deadline']:
        word_chain_close(chat_id, game_id, 'idle')


@bot.message_handler(commands=['wordchain', 'wc'])
def word_chain_command(message):
    if message.chat.type not in ('group', 'supergroup'):
        bot.reply_to(message, 'Group ထဲမှာပဲ ကစားလို့ရပါတယ်။')
        return
    args = (message.text or '').split()
    if len(args) > 1 and args[1].lower() not in ('en', 'english', 'my', 'mm', 'burmese', 'မြန်မာ'):
        bot.reply_to(message, 'အသုံးပြုရန်: /wordchain en သို့မဟုတ် /wordchain mm')
        return
    mode = args[1].lower() if len(args) > 1 else 'en'
    chat_id = message.chat.id
    if get_speed_tap_game(chat_id) or get_emoji_game(chat_id):
        bot.reply_to(message, 'တခြား game ပြီးမှ Word Chain စနိုင်ပါတယ်။')
        return
    created, game = start_word_chain_game(chat_id, mode)
    if not created:
        bot.reply_to(message, f'Game တစ်ခု run နေပြီ: {game}')
        return
    try:
        sent = bot.send_photo(chat_id, word_chain_status_card(game), caption='🔤 WORD CHAIN — စကားလုံးဆက်ပါ')
        set_word_chain_message_id(chat_id, game['id'], sent.message_id)
        word_chain_start_live(chat_id, get_word_chain_game(chat_id))
        schedule_task(
            game['round_seconds'],
            word_chain_close,
            chat_id, game['id'], 'limit',
            task_id=f"wordchain_limit:{chat_id}:{game['id']}",
        )
        schedule_task(
            WORD_CHAIN_IDLE_SECONDS,
            word_chain_idle_check,
            chat_id, game['id'], game['idle_deadline'],
            task_id=f"wordchain_idle:{chat_id}:{game['id']}:0",
        )
        delay_delete_message(chat_id, message.message_id, random.randint(5, 10))
    except Exception as error:
        print(f'Word Chain Start Error: {error}')
        finish_word_chain(chat_id, game['id'])


@bot.message_handler(commands=['endwordchain', 'stopwc'])
def word_chain_stop_command(message):
    game = get_word_chain_game(message.chat.id)
    if not game:
        return
    if not is_user_admin(bot, message.chat.id, message.from_user.id):
        bot.reply_to(message, 'Admin ပဲ ဒီ game ကိုရပ်လို့ရပါတယ်။')
        return
    word_chain_close(message.chat.id, game['id'], 'stop')


@bot.message_handler(
    func=lambda message: (
        message.chat.type in ('group', 'supergroup')
        and bool(message.text)
        and not message.text.startswith('/')
        and bool(get_word_chain_game(message.chat.id))
    )
)
def word_chain_answer(message):
    chat_id = message.chat.id
    game = get_word_chain_game(chat_id)
    if not game:
        return
    result = submit_word_chain(
        chat_id, game['id'], message.from_user.id,
        message.from_user.first_name, message.text,
    )
    if result['status'] == 'expired':
        word_chain_close(chat_id, game['id'], 'idle')
        return
    if result['status'] != 'valid':
        # The Word Chain handler precedes the catch-all group filter.
        # Preserve normal chat moderation even while a game is running.
        ban_word_filter(message)
        return
    delay_delete_message(chat_id, message.message_id, random.randint(30, 45))
    # A valid move refreshes the inactivity deadline.
    new_game = get_word_chain_game(chat_id)
    if not new_game or new_game['id'] != game['id']:
        return
    old_id = result.get('message_id')
    try:
        with word_chain_card_lock:
            latest = get_word_chain_game(chat_id)
            if latest and latest['id'] == game['id'] and latest['moves'] == result['moves']:
                sent = bot.send_photo(
                    chat_id, word_chain_status_card(latest),
                    caption='🔤 WORD CHAIN — စကားလုံးဆက်ပါ',
                )
                set_word_chain_message_id(chat_id, game['id'], sent.message_id)
                if old_id:
                    try:
                        bot.delete_message(chat_id, old_id)
                    except Exception:
                        pass
                word_chain_start_live(chat_id, get_word_chain_game(chat_id))
    except Exception as error:
        print(f'Word Chain Status Error: {error}')
    delay = max(0.1, new_game['idle_deadline'] - time.monotonic())
    schedule_task(
        delay,
        word_chain_idle_check,
        chat_id, game['id'], new_game['idle_deadline'],
        task_id=f"wordchain_idle:{chat_id}:{game['id']}:{new_game['moves']}",
    )


# =========================================================

@bot.message_handler(commands=["emoji", "emojiguess"])
def emoji_guess_command(message):

    if message.chat.type not in [
        "group",
        "supergroup",
    ]:
        bot.reply_to(
            message,
            "❌ Group ထဲမှာပဲ ကစားလို့ရပါတယ်။"
        )
        return

    chat_id = message.chat.id

    # -----------------------------------------
    # Already running
    # -----------------------------------------

    if get_emoji_game(chat_id):
        bot.reply_to(
            message,
            "😀 Emoji Guess game တစ်ပွဲ ကစားနေပြီးသားပါ။"
        )
        return

    # -----------------------------------------
    # Pick next question
    # -----------------------------------------

    question = get_next_emoji_question(
        chat_id
    )

    if not question:
        bot.reply_to(
            message,
            "❌ Emoji question မရသေးပါ။"
        )
        return

    # -----------------------------------------
    # Start game
    # -----------------------------------------

    started, game = start_emoji_game(
        chat_id,
        question,
        duration=EMOJI_GUESS_TIME,
    )

    if not started:
        bot.reply_to(
            message,
            "😀 Emoji Guess game တစ်ပွဲ ကစားနေပြီးသားပါ။"
        )
        return

    # -----------------------------------------
    # Mark question used
    # -----------------------------------------

    mark_question_used(
        chat_id,
        "emoji_guess",
        question["id"],
    )

    # -----------------------------------------
    # Main question message
    # -----------------------------------------

    game_message = bot.send_message(
        chat_id,
        (
            "😀 <b>EMOJI GUESS</b>\n\n"
            f"{question['emojis']}\n\n"
            f"📂 Category: <b>{question['category']}</b>\n"
            f"⏳ Time: <b>{EMOJI_GUESS_TIME}s</b>\n\n"
            "💬 အဖြေကို group ထဲမှာ ရိုက်ပို့ပါ။"
        ),
        parse_mode="HTML",
    )

    # =====================================================
    # ⏳ LIVE COUNTDOWN
    # =====================================================

    def update_emoji_countdown():

        active_game = get_emoji_game(
            chat_id
        )

        if not active_game:
            return

        remaining = int(
            get_emoji_time_left(
                chat_id
            )
        )

        if remaining <= 5:
            return

        try:
            bot.edit_message_text(
                (
                    "😀 <b>EMOJI GUESS</b>\n\n"
                    f"{question['emojis']}\n\n"
                    f"📂 Category: <b>{question['category']}</b>\n"
                    f"⏳ Time: <b>{remaining}s</b>\n\n"
                    "💬 အဖြေကို group ထဲမှာ ရိုက်ပို့ပါ။"
                ),
                chat_id=chat_id,
                message_id=game_message.message_id,
                parse_mode="HTML",
            )

        except Exception as e:
            print(
                f"Emoji Countdown Error: {e}"
            )

        schedule_task(
            5,
            update_emoji_countdown,
            task_id=f"emoji_countdown:{chat_id}",
            replace=True,
        )

    schedule_task(
        5,
        update_emoji_countdown,
        task_id=f"emoji_countdown:{chat_id}",
        replace=True,
    )

    # =====================================================
    # 💡 HINT
    # =====================================================

    def send_emoji_hint():

        active_game = get_emoji_game(
            chat_id
        )

        if not active_game:
            return

        hint = get_emoji_hint(
            chat_id
        )

        if not hint:
            return

        try:
            hint_message = bot.send_message(
                chat_id,
                (
                    "💡 <b>HINT</b>\n\n"
                    f"{hint}"
                ),
                parse_mode="HTML",
            )

            delay_delete_message(
                chat_id,
                hint_message.message_id,
                30,
            )

        except Exception as e:
            print(
                f"Emoji Hint Error: {e}"
            )

    schedule_task(
        30,
        send_emoji_hint,
        task_id=f"emoji_hint:{chat_id}",
        replace=True,
    )

    # =====================================================
    # ⏰ TIMEOUT
    # =====================================================

    def emoji_timeout():

        finished_game = end_emoji_game(
            chat_id
        )

        if not finished_game:
            return

        cancel_task(
            f"emoji_countdown:{chat_id}"
        )

        cancel_task(
            f"emoji_hint:{chat_id}"
        )

        answer = finished_game[
            "display_answer"
        ]

        # Delete old main question
        delay_delete_message(
            chat_id,
            game_message.message_id,
            1,
        )

        try:
            result_message = bot.send_message(
                chat_id,
                (
                    "⏰ <b>TIME'S UP!</b>\n\n"
                    f"✅ Answer: <b>{answer}</b>"
                ),
                parse_mode="HTML",
            )

            # Timeout result stays 90 sec
            delay_delete_message(
                chat_id,
                result_message.message_id,
                90,
            )

        except Exception as e:
            print(
                f"Emoji Timeout Error: {e}"
            )

    schedule_task(
        EMOJI_GUESS_TIME,
        emoji_timeout,
        task_id=f"emoji_timeout:{chat_id}",
        replace=True,
    )


# =========================================================
# 😀 EMOJI GUESS ANSWER HANDLER
# =========================================================

@bot.message_handler(
    func=lambda message:
        message.chat.type in [
            "group",
            "supergroup",
        ]
        and bool(message.text)
        and not message.text.startswith("/")
        and bool(
            get_emoji_game(
                message.chat.id
            )
        )
)
def emoji_guess_answer(message):

    chat_id = message.chat.id
    user_id = message.from_user.id

    result = check_emoji_answer(
        chat_id,
        user_id,
        message.text,
    )

    # -----------------------------------------
    # Wrong answer
    #
    # IMPORTANT:
    # မဖျက်ပါ။
    # Normal chat ကိုပါ မထိပါ။
    # -----------------------------------------

    if result["status"] != "correct":
        return

    # -----------------------------------------
    # Correct answer
    # Stop all timers
    # -----------------------------------------

    cancel_task(
        f"emoji_countdown:{chat_id}"
    )

    cancel_task(
        f"emoji_hint:{chat_id}"
    )

    cancel_task(
        f"emoji_timeout:{chat_id}"
    )

    # -----------------------------------------
    # Delete player's correct answer
    # Random 30–45 sec
    # -----------------------------------------

    delay_delete_message(
        chat_id,
        message.message_id,
        random.randint(30, 45),
    )

    # -----------------------------------------
    # Find main Emoji question message
    # -----------------------------------------

    try:
        active_message_id = None

        # Main question message is the most recent
        # stored Telegram message from this round.
        # We delete it immediately after winner.
        active_message_id = getattr(
            message,
            "_emoji_game_message_id",
            None
        )

    except Exception:
        active_message_id = None

    # -----------------------------------------
    # Winner reward
    # -----------------------------------------

    try:
        apply_game_result(
            chat_id,
            user_id,
            "emoji_guess",
            "win",
        )

    except Exception as e:
        print(
            f"Emoji Reward Error: {e}"
        )

    winner_name = (
        message.from_user.first_name
        or "Player"
    )

    # -----------------------------------------
    # Winner result
    # -----------------------------------------

    try:
        result_message = bot.send_message(
            chat_id,
            (
                "🎉 <b>CORRECT!</b>\n\n"
                f"👤 Winner: <b>{winner_name}</b>\n"
                f"✅ Answer: <b>{result['answer']}</b>\n"
                "🏆 Reward: <b>+10 Points</b>"
            ),
            parse_mode="HTML",
        )

        delay_delete_message(
            chat_id,
            result_message.message_id,
            90,
        )

    except Exception as e:
        print(
            f"Emoji Result Error: {e}"
        )
        

# =========================================================
# 5. RANDOM - 200 RESPONSES
# =========================================================

RANDOM_MESSAGES = [
    "😂 ဒီနံပါတ်ကို ကံကြမ္မာက ရွေးလိုက်တယ်။",
    "🤣 Random က random ပဲကွာ။",
    "😎 ဒီနေ့ lucky number ဖြစ်နိုင်တယ်။",
    "🤨 ဒီ result ကို ဘယ်လိုထင်လဲ?",
    "😂 ငါလည်း ဘာလို့ဒီနံပါတ်လဲ မသိဘူး။",
    "🔥 ဒီနံပါတ်က မဆိုးဘူး။",
    "💀 မြင်ပြီး စိတ်မပျက်နဲ့။",
    "🤣 Calculator မလိုဘူး၊ မှန်တယ်။",
    "😏 ကံကြမ္မာရဲ့ ဆုံးဖြတ်ချက်ပဲ။",
    "🤡 Random ဘုရင်က ဆုံးဖြတ်ပြီးပြီ။",
    "🙃 ဒီနေ့အတွက် ဒီ result ပဲ။",
    "😂 ထပ်ခေါ်ချင်ရင် ထပ်ခေါ်။",
    "😎 ကံကောင်းမယ်ထင်တယ်။",
    "🤔 အဓိပ္ပါယ်ရှိမရှိတော့ မသိဘူး။",
    "🤣 မင်းရွေးတာမဟုတ်ဘူး၊ ကံကြမ္မာရွေးတာ။",
    "😈 ဒီနံပါတ်က နည်းနည်းကြမ်းတယ်။",
    "🔥 ဒီ result ကို မှတ်ထား။",
    "😂 Random machine က အလုပ်လုပ်ပြီးပြီ။",
    "🤣 ဘာပဲဖြစ်ဖြစ် number ရပြီ။",
    "🎯 ဒီနေ့ရဲ့ random result ပါ။"
]

RANDOM_BASE = [
    "ကံကြမ္မာက ဒီနံပါတ်ကို ရွေးလိုက်တယ်",
    "ဒီနေ့အတွက် random result က ဒါပဲ",
    "မင်းရဲ့ random number ရောက်လာပြီ",
    "Number machine က ဆုံးဖြတ်လိုက်ပြီ",
    "ဒီတစ်ခါ random က ဒီလိုထွက်တယ်",
    "မင်းရဲ့ကံကို စမ်းကြည့်",
    "ဒီနေ့ lucky number ဖြစ်နိုင်တယ်",
    "Random ဘုရင်က ဆုံးဖြတ်ပြီးပြီ",
    "ဒီနံပါတ်ကို လက်ခံလိုက်",
    "ကံတရားရဲ့ ဆုံးဖြတ်ချက်က ဒါပဲ",
    "မင်းအတွက် ဒီနံပါတ်ထွက်လာတယ်",
    "ဒီနေ့ random result လာပြီ",
    "ကံက ဒီလိုပြောတယ်",
    "Random universe က ရွေးလိုက်ပြီ",
    "ဒီ result ကို မှတ်ထား",
    "ဒီနံပါတ်နဲ့ ဒီနေ့ဖြတ်သန်း",
    "ကံစမ်းတဲ့အခါ ဒီလိုပဲ",
    "Random က မင်းကို မျက်နှာသာပေးတယ်",
    "ဒီတစ်ခါတော့ ဒီနံပါတ်ပဲ",
    "Random machine ရဲ့ decision က ဒါပဲ"
]

# Base + Reaction ပေါင်းပြီး message အသစ်တွေ ဖန်တီးမယ်
GENERATED_RANDOM_MESSAGES = []

for base in RANDOM_BASE:
    for reaction in RANDOM_MESSAGES:
        GENERATED_RANDOM_MESSAGES.append(
            f"{base} — {reaction}"
        )

# 20 × 20 = 400 ဖြစ်တဲ့အတွက် ပထမ 200 ခုကိုပဲယူမယ်
RANDOM_MESSAGES = GENERATED_RANDOM_MESSAGES[:200]


@bot.message_handler(commands=["random", "ကျပမ်း"])
def random_command(message):

    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    number = random.randint(1, 100)

    reaction = random.choice(RANDOM_MESSAGES)

    reply_game_message(
        message,
        f"🎲 RANDOM RESULT\n\n"
        f"🔢 Number — {number}\n\n"
        f"{reaction}"
    )


# =========================================================
# 6. RULES - 4 MINUTES
# =========================================================

@bot.message_handler(commands=["rules", "စည်းကမ်း"])
def rules_command(message):

    delay_delete_message(
        message.chat.id,
        message.message_id,
        INFO_DELETE_TIME
    )

    reply_info_message(
        message,
        "📜 GROUP RULES\n\n"
        "1️⃣ Spam မလုပ်ရ။\n"
        "2️⃣ Group ကို မနှောင့်ယှက်ရ။\n"
        "3️⃣ မလိုအပ်ဘဲ message အများကြီး မပို့ရ။\n"
        "4️⃣ အခြား members တွေကို လေးစားပါ။\n"
        "5️⃣ Admin တွေရဲ့ moderation ကို လိုက်နာပါ။\n\n"
        "🤖 Bot commands တွေကိုလည်း "
        "စောက်တလွဲသုံးပါနဲ့။"
    )


# =========================================================
# 7. ID - 4 MINUTES
# =========================================================

@bot.message_handler(commands=["id", "အိုင်ဒီ"])
def id_command(message):

    delay_delete_message(
        message.chat.id,
        message.message_id,
        INFO_DELETE_TIME
    )

    chat_id = message.chat.id

    if message.reply_to_message:

        target = (
            message.reply_to_message.from_user
        )

        reply_info_message(
            message,
            f"🆔 USER ID\n"
            f"<code>{target.id}</code>\n\n"
            f"💬 CHAT ID\n"
            f"<code>{chat_id}</code>",
            parse_mode="HTML"
        )

        return

    reply_info_message(
        message,
        f"🆔 USER ID\n"
        f"<code>{message.from_user.id}</code>\n\n"
        f"💬 CHAT ID\n"
        f"<code>{chat_id}</code>",
        parse_mode="HTML"
    )


# =========================================================
# 8. ADMINS - 4 MINUTES
# =========================================================

@bot.message_handler(commands=["admins", "အက်မင်"])
def admins_command(message):

    delay_delete_message(
        message.chat.id,
        message.message_id,
        INFO_DELETE_TIME
    )

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:

        reply_info_message(
            message,
            "❌ Group ထဲမှာပဲ သုံးလို့ရပါတယ်။"
        )

        return

    try:

        admins = bot.get_chat_administrators(
            message.chat.id
        )

        lines = [
            "👮 GROUP ADMINS",
            ""
        ]

        for admin in admins:

            user = admin.user

            if user.is_bot:
                continue

            name = (
                user.first_name
                or "Unknown"
            )

            if user.username:

                lines.append(
                    f"👤 {name} — @{user.username}"
                )

            else:

                lines.append(
                    f"👤 {name}"
                )

        reply_info_message(
            message,
            "\n".join(lines)
        )

    except Exception as e:

        print(
            f"Admins Error: {e}"
        )

        reply_info_message(
            message,
            "❌ Admin list ယူလို့မရပါဘူး။"
        )


# =========================================================
# 9. PING - 4 MINUTES
# =========================================================

@bot.message_handler(commands=["ping"])
def ping_command(message):

    delay_delete_message(
        message.chat.id,
        message.message_id,
        INFO_DELETE_TIME
    )

    start = time.time()

    try:

        msg = bot.reply_to(
            message,
            "🏓 Pinging..."
        )

        ping_ms = int(
            (time.time() - start) * 1000
        )

        delay_delete_message(
            message.chat.id,
            msg.message_id,
            INFO_DELETE_TIME
        )

        bot.edit_message_text(
            f"🏓 PONG!\n\n"
            f"⚡ {ping_ms} ms",
            message.chat.id,
            msg.message_id
        )

    except Exception as e:

        print(
            f"Ping Error: {e}"
        )


# =========================================================
# 10. UPTIME - 4 MINUTES
# =========================================================

@bot.message_handler(commands=["uptime"])
def uptime_command(message):

    delay_delete_message(
        message.chat.id,
        message.message_id,
        INFO_DELETE_TIME
    )

    total_seconds = int(
        time.time() - BOT_START_TIME
    )

    days = total_seconds // 86400

    remaining = total_seconds % 86400

    hours = remaining // 3600

    remaining %= 3600

    minutes = remaining // 60

    seconds = remaining % 60

    parts = []

    if days:
        parts.append(
            f"{days}d"
        )

    if hours:
        parts.append(
            f"{hours}h"
        )

    if minutes:
        parts.append(
            f"{minutes}m"
        )

    parts.append(
        f"{seconds}s"
    )

    reply_info_message(
        message,
        "⏱️ BOT UPTIME\n\n"
        f"🟢 {' '.join(parts)}"
    )


# =========================================================
# 11. WELCOME - 2 MINUTES
# =========================================================

@bot.message_handler(
    content_types=["new_chat_members"]
)
def welcome_new_member(message):

    for user in message.new_chat_members:

        if user.is_bot:
            continue

        name = (
            user.first_name
            or "သူငယ်ချင်း"
        )

        sent = bot.send_message(
            message.chat.id,
            f"👋 Welcome {name}!\n\n"
            f"🎉 Group ထဲကို ကြိုဆိုပါတယ်။\n"
            f"📜 /rules နဲ့ Group Rules ကို "
            f"ကြည့်နိုင်ပါတယ်။"
        )

        delay_delete_message(
            message.chat.id,
            sent.message_id,
            WELCOME_DELETE_TIME
        )


# =========================================================
# GAME CLEANUP
# =========================================================

def clean_new_games():

    now = time.time()

    # -----------------------------------------------------
    # COIN
    # -----------------------------------------------------

    expired_coin = []

    for game_id, game in coin_games.items():

        if (
            now - game["created"]
            > GAME_DELETE_TIME
        ):

            expired_coin.append(
                game_id
            )

    for game_id in expired_coin:

        del coin_games[game_id]

    # -----------------------------------------------------
    # GUESS
    # -----------------------------------------------------

    expired_guess = []

    for key, game in guess_games.items():

        if (
            now - game["created"]
            > 600
        ):

            expired_guess.append(
                key
            )

    for key in expired_guess:

        del guess_games[key]


def new_games_cleanup_loop():

    while True:

        try:

            clean_new_games()

        except Exception as e:

            print(
                f"Game Cleanup Error: {e}"
            )

        time.sleep(60)


threading.Thread(
    target=new_games_cleanup_loop,
    daemon=True
).start()


# =========================================================
# END OF NEW 11 FUNCTIONS
# =========================================================


# =========================================================
# ALL BOT COMMANDS
# /cmds = NEVER AUTO DELETE
# =========================================================

@bot.message_handler(commands=["cmds"])
def commands_list(message):

    bot.send_message(
        message.chat.id,
        "🤖 BOT COMMANDS\n\n"

        "🎮 GAME COMMANDS\n"
        "🎲 /dice — Dice လှိမ့်ရန်\n"
        "🎰 /slot — Slot animation\n"
        "❤️ /love — Love calculator\n"
        "🪙 /coin — Coin Flip\n"
        "✊ /rps — Rock Paper Scissors\n"
        "🎱 /8ball ၊ /ဗေဒင်  — 8 Ball\n"
        "🎯 /guess ၊ /ခန့်မှန်း — Number Guess\n"
        "🎲 /random ၊ /ကျပမ်း — Random Number\n\n"

        "👥 GROUP COMMANDS\n"

        "📢 /all — Members ခေါ်ရန်\n"
        "📢 /everyone — Members ခေါ်ရန်\n"
        "📢 /လာကြစမ်း — Members ခေါ်ရန်\n"
        "🛑 /stop — Mention ရပ်ရန်\n"
        "🛑 /နား — Mention ရပ်ရန်\n\n"

        "🛡️ ADMIN COMMANDS\n"
        "🚫 /ဘမ်း — User Ban\n"
        "🔓 /မဘမ်း — User Unban\n"
        "🔇 /တိတ်စမ်း — User Mute\n"
        "🔊 /ဖွင့်လိုက် — User Unmute\n\n"

        "📋 INFORMATION\n"
        "📜 /rules ၊ /စည်းကမ်း — Group Rules\n"
        "👮 /admins ၊ /အက်မင် — Admin List\n"
        "🆔 /id — User / Chat ID\n"
        "🏓 /ping — Bot Ping\n"
        "⏱️ /uptime — Bot Uptime\n"
        "📋 /cmds — Command List"
    )


# ---------------------------------------------------------
# 🚨 BAN WORD + SPAM FILTER
# ---------------------------------------------------------

warn_count = {}

initialize_player_stats()
init_used_questions_db()

# =========================================================
# ⚠️ MANUAL WARN
# =========================================================

@bot.message_handler(commands=["warn"])
def manual_warn(message):

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:
        bot.reply_to(
            message,
            "❌ Group ထဲမှာပဲ /warn သုံးလို့ရပါတယ်။"
        )
        return

    if not is_admin(message):
        bot.reply_to(
            message,
            "❌ Admin ပဲ /warn သုံးလို့ရပါတယ်။"
        )
        return

    if not message.reply_to_message:
        bot.reply_to(
            message,
            "❌ Warn ပေးချင်တဲ့ user message ကို "
            "Reply လုပ်ပြီး /warn ရိုက်ပါ။"
        )
        return

    target = message.reply_to_message.from_user

    if target.is_bot:
        bot.reply_to(
            message,
            "❌ Bot ကို Warn ပေးစရာမလိုပါဘူး။"
        )
        return

    if target.id == message.from_user.id:
        bot.reply_to(
            message,
            "❌ ကိုယ့်ကိုယ်ကို Warn ပေးလို့မရပါဘူး။"
        )
        return

    key = (
        message.chat.id,
        target.id
    )

    warn_count[key] = (
        warn_count.get(key, 0) + 1
    )

    warns = warn_count[key]

    # 3 WARN = BAN
    if warns >= 3:

        try:
            bot.ban_chat_member(
                message.chat.id,
                target.id
            )

            del warn_count[key]

            reply_info_message(
                message,
                f"🚫 {target.first_name}\n\n"
                f"⚠️ Warn 3/3 ပြည့်သွားပါပြီ။\n"
                f"🚫 Ban လုပ်လိုက်ပြီ။"
            )

        except Exception as e:

            print(
                f"Manual Warn Ban Error: {e}"
            )

            bot.reply_to(
                message,
                "❌ Ban လုပ်လို့မရပါဘူး။ "
                "Bot မှာ Ban Users permission ရှိ/မရှိ စစ်ပါ။"
            )

        return

    reply_info_message(
        message,
        f"⚠️ WARN\n\n"
        f"👤 {target.first_name}\n"
        f"📊 Warn — {warns}/3"
    )


# =========================================================
# 👤 PROFILE - VISUAL RANK CARD
# =========================================================

@bot.message_handler(commands=["profile"])
def profile_command(message):

    user = message.from_user

    stats = get_player_stats(
        message.chat.id,
        user.id
    )

    try:
        # -----------------------------------------
        # Generate visual profile/rank card
        # -----------------------------------------

        rank_image = generate_rank_card_bytes(
            player_name=(
                user.first_name
                or "Player"
            ),
            points=stats["points"],
            wins=stats["wins"],
            games=stats["games"],
            losses=stats["losses"],
            draws=stats["draws"],
        )

        # Telegram file name
        rank_image.name = "profile_rank_card.png"

        sent = bot.send_photo(
            message.chat.id,
            rank_image,
            caption="🏆 PLAYER PROFILE",
            reply_to_message_id=message.message_id,
        )

        # Visual profile card ကို
        # INFO_DELETE_TIME ပြည့်ရင်ဖျက်
        delay_delete_message(
            message.chat.id,
            sent.message_id,
            INFO_DELETE_TIME
        )

    except Exception as e:

        print(
            f"❌ Profile Card Error: {e}"
        )

        # -----------------------------------------
        # Image generate/send error ဖြစ်ရင်
        # အဟောင်း text profile ကို fallback
        # -----------------------------------------

        rank = get_rank_title(
            stats["points"]
        )

        reply_info_message(
            message,
            f"👤 PROFILE\n\n"
            f"👤 {user.first_name}\n"
            f"🏆 Rank — {rank}\n"
            f"💰 Points — {stats['points']}\n"
            f"🎮 Games — {stats['games']}\n"
            f"🥇 Wins — {stats['wins']}\n"
            f"❌ Losses — {stats['losses']}\n"
            f"🤝 Draws — {stats['draws']}"
        )


# =========================================================
# 🏆 RANK - VISUAL LEADERBOARD
# =========================================================

@bot.message_handler(commands=["rank"])
def rank_command(message):

    chat_id = message.chat.id

    players = []

    # -----------------------------------------
    # Player stats snapshot
    # -----------------------------------------

    with player_stats_lock:

        for key, stats in player_stats.items():

            saved_chat_id, user_id = key

            if saved_chat_id != chat_id:
                continue

            # 0 Points + 0 Games player မပြ
            if (
                stats["points"] <= 0
                and stats["games"] <= 0
            ):
                continue

            players.append(
                (
                    user_id,
                    stats.copy()
                )
            )

    # -----------------------------------------
    # Ranking:
    # 1. Points
    # 2. Wins
    # 3. Games
    # -----------------------------------------

    players.sort(
        key=lambda item: (
            item[1]["points"],
            item[1]["wins"],
            item[1]["games"]
        ),
        reverse=True
    )

    if not players:

        reply_info_message(
            message,
            "🏆 Rank data မရှိသေးပါဘူး။\n"
            "Game ကစားပြီး Points ရယူပါ။"
        )

        return

    # Top 10
    players = players[:10]

    leaderboard_players = []

    for user_id, stats in players:

        try:

            member = bot.get_chat_member(
                chat_id,
                user_id
            )

            name = (
                member.user.first_name
                or "Unknown"
            )

        except Exception:

            name = "Unknown"

        leaderboard_players.append(
            {
                "name": name,
                "points": stats["points"],
                "wins": stats["wins"],
                "games": stats["games"],
            }
        )

    try:

        # -------------------------------------
        # Generate visual leaderboard
        # -------------------------------------

        rank_image = (
            generate_leaderboard_card_bytes(
                players=leaderboard_players,
                title="GROUP RANKING",
            )
        )

        rank_image.name = (
            "group_leaderboard.png"
        )

        sent = bot.send_photo(
            chat_id,
            rank_image,
            caption="🏆 GROUP RANKING",
            reply_to_message_id=
                message.message_id,
        )

        delay_delete_message(
            chat_id,
            sent.message_id,
            INFO_DELETE_TIME
        )

    except Exception as e:

        print(
            f"❌ Leaderboard Card Error: {e}"
        )

        # -------------------------------------
        # Image error ဖြစ်ရင် text fallback
        # -------------------------------------

        lines = [
            "🏆 GROUP RANKING",
            ""
        ]

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        for index, player in enumerate(
            leaderboard_players,
            start=1
        ):

            icon = medals.get(
                index,
                f"{index}."
            )

            rank = get_rank_title(
                player["points"]
            )

            lines.append(
                f"{icon} {player['name']}\n"
                f"💰 {player['points']} pts • "
                f"{rank}\n"
                f"🥇 {player['wins']} Wins • "
                f"🎮 {player['games']} Games"
            )

        reply_info_message(
            message,
            "\n\n".join(lines)
        )


# =========================================================
# 🥇 TOP = RANK
# =========================================================

@bot.message_handler(commands=["top"])
def top_command(message):

    rank_command(message)


# Spam records
# key = (type, chat_id, user_id)
# value = [(time, message_id), ...]
spam_count = {}

# =========================================================
# ⚙️ SPAM SETTINGS
# =========================================================

SPAM_LIMIT = 5       # 5 ခုရောက်ရင် Spam
SPAM_TIME = 10       # 10 စက္ကန့်အတွင်း
MUTE_TIME = 45       # 45 စက္ကန့် Mute


# ---------------------------------------------------------
# ⏱️ SPAM CHECK
# ---------------------------------------------------------

def check_spam(chat_id, user_id, key_type, message_id):

    now = time.time()

    key = (key_type, chat_id, user_id)

    if key not in spam_count:
        spam_count[key] = []

    # SPAM_TIME ကျော်သွားတဲ့ message တွေ ဖယ်
    spam_count[key] = [
        item
        for item in spam_count[key]
        if now - item[0] <= SPAM_TIME
    ]

    # လက်ရှိ message ကို မှတ်ထား
    spam_count[key].append(
        (now, message_id)
    )

    return len(spam_count[key])


# ---------------------------------------------------------
# 🗑️ SPAM MESSAGES အားလုံးဖျက်
# ---------------------------------------------------------

def delete_spam_messages(chat_id, user_id, key_type):

    key = (key_type, chat_id, user_id)

    if key not in spam_count:
        return

    # ဖျက်ရမယ့် message ID တွေကို copy ယူထား
    message_ids = [
        item[1]
        for item in spam_count[key]
    ]

    # Spam message အားလုံးဖျက်
    for message_id in message_ids:

        try:
            bot.delete_message(
                chat_id,
                message_id
            )

        except Exception as e:
            print(
                f"⚠️ Spam message delete failed "
                f"{message_id}: {e}"
            )

    # Counter reset
    spam_count[key] = []


# ---------------------------------------------------------
# 🔇 MUTE USER
# ---------------------------------------------------------

def mute_user(chat_id, user_id, name, reason):

    now = time.time()

    permissions = ChatPermissions(
        can_send_messages=False
    )

    bot.restrict_chat_member(
        chat_id,
        user_id,
        permissions=permissions,
        until_date=int(now + MUTE_TIME)
    )

    warning = bot.send_message(
        chat_id,
        f"🔇 {name} {reason}\n"
        f"{MUTE_TIME} စက္ကန့် Mute လိုက်ပါပြီ။"
    )

    delay_delete_message(
        chat_id,
        warning.message_id,
        5
    )


# ---------------------------------------------------------
# 💬 TEXT — BAN WORD + TEXT SPAM
# ---------------------------------------------------------

@bot.message_handler(
    func=lambda message:
        message.chat.type in ["group", "supergroup"]
        and message.text is not None
)
def ban_word_filter(message):

    try:

        # 👑 Admin ကို Filter မလုပ်
        if is_admin(message):
            return

        chat_id = message.chat.id
        user_id = message.from_user.id
        name = message.from_user.first_name

        # Text spam is handled by early_text_spam_middleware().

        # =================================================
        # 🚫 BAN WORD CHECK
        # =================================================

        text = message.text.lower()

        for word in BAN_WORDS:

            if word.lower() in text:

                # မကောင်းတဲ့ message ဖျက်
                try:
                    bot.delete_message(
                        chat_id,
                        message.message_id
                    )
                except:
                    pass

                # Warn count
                key = (chat_id, user_id)

                warn_count[key] = (
                    warn_count.get(key, 0) + 1
                )

                warns = warn_count[key]

                # =================================================
                # 🚫 3 WARNS = BAN
                # =================================================

                if warns >= 3:

                    bot.ban_chat_member(
                        chat_id,
                        user_id
                    )

                    warning = bot.send_message(
                        chat_id,
                        f"🚫 {name} မအေလိုး ၃ ခါရှိနေပြီ လစ်လိုက်တော့"
                        f"\nBan လိုက်ပြီ။"
                    )

                    delay_delete_message(
                        chat_id,
                        warning.message_id,
                        5
                    )

                    del warn_count[key]

                # =================================================
                # ⚠️ WARN 1 / 2
                # =================================================

                else:

                    warning = bot.send_message(
                        chat_id,
                        f"⚠️ {name} မမအေလိုး မဆဲနဲ့..\n"
                        f"Warn: {warns}/3"
                    )

                    delay_delete_message(
                        chat_id,
                        warning.message_id,
                        5
                    )

                break

    except Exception as e:

        print(
            f"Ban Word / Text Spam Error: {e}"
        )


# ---------------------------------------------------------
# 🖼️ STICKER SPAM FILTER
# ---------------------------------------------------------

@bot.message_handler(
    content_types=["sticker"]
)
def sticker_spam_filter(message):

    try:

        # Group / Supergroup မှာပဲအလုပ်လုပ်
        if message.chat.type not in [
            "group",
            "supergroup"
        ]:
            return

        # 👑 Admin ကို Filter မလုပ်
        if is_admin(message):
            return

        chat_id = message.chat.id
        user_id = message.from_user.id
        name = message.from_user.first_name

        # =================================================
        # 🚨 STICKER SPAM CHECK
        # =================================================

        count = check_spam(
            chat_id,
            user_id,
            "sticker",
            message.message_id
        )

        if count >= SPAM_LIMIT:

            # Spam window ထဲက Sticker အားလုံးဖျက်
            delete_spam_messages(
                chat_id,
                user_id,
                "sticker"
            )

            # User ကို Mute
            mute_user(
                chat_id,
                user_id,
                name,
                "Sticker တွေလီးမို့ ဆက်တိုက်ပို့နေတာလားး"
            )

    except Exception as e:

        print(
            f"Sticker Spam Error: {e}"
        )


# =========================================================
# 🛡️ END OF GROUP MANAGEMENT SYSTEM
# =========================================================

# =========================================================
# ⚡ SPEED TAP AUTO-SPAWN WIRING
# =========================================================
def can_auto_spawn_speed_tap(chat_id):
    # Emoji game does not currently create a core session,
    # so check both the session manager and its own game state.
    allowed, _ = can_start_session(chat_id, "speed_tap")
    return bool(
        allowed
        and not get_speed_tap_game(chat_id)
        and not get_emoji_game(chat_id)
    )


def spawn_auto_speed_tap(chat_id):
    if not can_auto_spawn_speed_tap(chat_id):
        return False
    # Reuse the existing pending -> WAIT -> GO -> result flow.
    return bool(speed_tap_command(auto_chat_id=chat_id))


configure_speed_tap_auto(
    spawn_callback=spawn_auto_speed_tap,
    can_spawn_callback=can_auto_spawn_speed_tap,
)

from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot server is running!"

def run_bot():
    print("ဘော့ အလုပ်လုပ်နေပါပြီ။")
    while True:
        try:
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30
            )
        except Exception as e:
            print(f"⚠️ Connection Error: {e}")
            print("🔄 Telegram ကို ပြန်ချိတ်နေပါတယ်...")
            time.sleep(10)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
