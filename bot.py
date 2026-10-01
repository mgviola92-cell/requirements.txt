import telebot
print("TEST 1 - bot.py started")
import time
import random
import yt_dlp
import os
import threading
from telebot.types import ChatPermissions

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# ကိုယ်ပေါ်စေချင်တဲ့ အီမိုဂျီများကို ဒီထဲမှာ စိုက်ကြိုက် ပြောင်းလဲနိုင်ပါတယ်
EMOJIS = ["🔥", "✨", "🎉", "💥", "🎯", "🌟", "🚀", "⚡", "🍀", "💎"]

# Cooldown စနစ်နှင့် Stop စနစ်အတွက် မှတ်ဉာဏ်သိမ်းဆည်းရန်နေရာ
last_called_time = 0
is_stopped = False

# 🎯 လူခေါ်စာများကိုပဲ သီးသန့် အချိန်ကိုက် လိုက်ဖျက်ပေးမည့် စနစ်
def delay_delete_message(chat_id, message_id, delay_seconds):
    def delete_task():
        time.sleep(delay_seconds)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            print(f"Auto Delete Error: {e}")
    threading.Thread(target=delete_task).start()

# --- 🛑 လူခေါ်ခြင်းကို ကြားဖြတ်ရပ်တန့်မည့် လုပ်ဆောင်ချက် (/stop) ---
@bot.message_handler(commands=['stop', 'နား'])
def stop_mention(message):
    global is_stopped
    if message.chat.type in ['group', 'supergroup']:
        is_stopped = True
        bot.reply_to(message, "🛑 ရပ်လိုက်ပြီ စောက်အမျိုးမျိုးပဲ မသာကောင်")

# --- ၁။ လူခေါ်သည့် လုပ်ဆောင်ချက် (All Mention Function) ---
@bot.message_handler(commands=['start', 'all', 'everyone', 'လာကြစမ်း'])
def mention_all_users(message):
    global last_called_time, is_stopped

    if message.chat.type in ['group', 'supergroup']:
        chat_id = message.chat.id

     # Admin ရိုက်လိုက်တဲ့ /လာကြစမ်း command ကို
        # 60 စက္ကန့်နောက် ဖျက်မယ်
        delay_delete_message(
            message.chat.id,
            message.message_id,
            80
        )

        # ⏱️ ၄၀ စက္ကန့် Cooldown တွက်ချက်ခြင်း
        current_time = time.time()
        if last_called_time != 0 and (current_time - last_called_time) < 140:
            remaining_time = int(140 - (current_time - last_called_time))

            if remaining_time > 60:
                bot.reply_to(message, "⏳ လူခေါ်တာမပြီးသေးဘဲ လီးမို့ထပ်ခေါ်နေတာလား ဖြတ်ထိုးလိုက်ရ စောက်တောသား ⏳")
            else:
                bot.reply_to(message, f"⏳ ဆက်တိုက်ခေါ်လို့ မရဘူး စောက်ရူးကောင် ငါလည်း ငြောင်းတတ်တယ် နောက်ထပ် {remaining_time} စက္ကန့် စောင့်ပြီးမှဆက်ခေါ် ကမကလ")
            return

        # လူခေါ်ခြင်း အသစ်စတင်တိုင်း Stop အလံကို ပုံမှန်ပြန်လုပ်ခြင်း
        is_stopped = False
        last_called_time = current_time

        user_text = message.text.split(maxsplit=1)
        if len(user_text) > 1:
            input_line = user_text[1]
        else:
            input_line = "တောသားတွေလာကြစမ်း"

        try:
            chat_admins = bot.get_chat_administrators(chat_id)

            user_list = []
            for admin in chat_admins:
                if not admin.user.is_bot:
                    user_list.append(admin.user.id)

            for _ in range(30):
                if is_stopped:
                    break

                hidden_mentions = ""
                for u_id in user_list:
                    hidden_mentions += f"<a href='tg://user?id={u_id}'>​</a>"

                random_emojis = "".join(random.choices(EMOJIS, k=5))
                final_message = f"{input_line}\n{random_emojis}{hidden_mentions}"

                sent_msg = bot.send_message(chat_id, final_message, parse_mode='HTML')

                # 🎯 လူခေါ်စာစောင်များကိုပဲ သီးသန့် ၁ မိနစ်ပြည့်ရင် ဖျက်ခိုင်းထားပါသည်
                delay_delete_message(chat_id, sent_msg.message_id, 60)
                time.sleep(2)

        except Exception as e:
            print(f"Error caught inside loop: {e}")

        if not is_stopped:
            try:
                time.sleep(1.0)
                finish_time = time.time()
                remaining_cooldown = int(120 - (finish_time - last_called_time))
                if remaining_cooldown > 60:
                    remaining_cooldown = 60

                custom_finish_message = f"ခေါ်ပြီးဘီ လီးဖစ်နေလား (နောက်ထပ် {remaining_cooldown} စက္ကန့် စောင့်ဦး)"
                finish_msg = bot.send_message(chat_id, custom_finish_message)

                # 🎯 Finish Message ကိုပါ ၁ မိနစ်ပြည့်လျှင် ပြန်ဖျက်ခိုင်းခြင်း
                delay_delete_message(chat_id, finish_msg.message_id, 60)
            except Exception as e:
                print(f"Error sending finish message: {e}")

    else:
        bot.reply_to(message, "This command can only be used in Telegram Groups.")

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
@bot.message_handler(commands=["တိတ်စမ်း"])
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
@bot.message_handler(commands=["ဖွင့်လိုက်"])
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

GAME_DELETE_TIME = 80
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
    "tails": "အမြီး"
}


def flip_coin():
    return random.choice([
        "ခေါင်း",
        "အမြီး"
    ])


def find_coin_games_for_user(chat_id, user):

    games = []

    for game_id, game in coin_games.items():

        if game["chat_id"] != chat_id:
            continue

        # Player 1
        if user.id == game["challenger_id"]:

            games.append(
                (game_id, game, "challenger")
            )

        # Player 2 - ID နဲ့ရှာ
        elif (
            game["target_id"] is not None
            and user.id == game["target_id"]
        ):

            games.append(
                (game_id, game, "target")
            )

        # Player 2 - Username နဲ့ရှာ
        elif (
            game["target_username"]
            and user.username
            and user.username.lower()
            == game["target_username"].lower()
        ):

            games.append(
                (game_id, game, "target")
            )

    return games


@bot.message_handler(commands=["coin"])
def coin_command(message):

    # Command message ကို 80 sec နောက်ဖျက်
    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    args = message.text.split()

    # -----------------------------------------------------
    # /coin
    # -----------------------------------------------------

    if len(args) == 1:

        # Reply လုပ်ထားရင် Reply target ကိုယူ
        if message.reply_to_message:

            target = message.reply_to_message.from_user
            challenger = message.from_user

            if target.is_bot:

                reply_game_message(
                    message,
                    "❌ Bot ကို Coin challenge လုပ်လို့မရပါဘူး။"
                )

                return

            if target.id == challenger.id:

                reply_game_message(
                    message,
                    "😂 ကိုယ့်ကိုယ်ကို challenge လုပ်လို့မရဘူး။"
                )

                return

            # Group ထဲမှာပဲ User vs User
            if message.chat.type not in [
                "group",
                "supergroup"
            ]:

                reply_game_message(
                    message,
                    "❌ လူချင်း Coin ကစားတာကို "
                    "Group ထဲမှာပဲ သုံးပါ။"
                )

                return

            # Challenger မှာ game ရှိပြီးသားလား
            for game in coin_games.values():

                if (
                    game["chat_id"] == message.chat.id
                    and game["challenger_id"]
                    == challenger.id
                ):

                    reply_game_message(
                        message,
                        "⚠️ မင်းမှာ Coin game "
                        "တစ်ခုရှိပြီးသားပါ။"
                    )

                    return

            # Username ရှိရင် သိမ်းမယ်
            target_username = None

            if target.username:
                target_username = target.username.lower()

            # Unique game ID
            game_id = (
                f"coin_{message.chat.id}_"
                f"{challenger.id}_{target.id}"
            )

            coin_games[game_id] = {

                "chat_id": message.chat.id,

                "challenger_id": challenger.id,

                # Reply target ဖြစ်လို့ ID ကို တိုက်ရိုက်သိတယ်
                "target_id": target.id,

                "target_username": target_username,

                "challenger_choice": None,

                "target_choice": None,

                "created": time.time()
            }

            target_name = target.first_name or "Player 2"

            reply_game_message(
                message,
                f"🪙 COIN CHALLENGE!\n\n"
                f"👤 {challenger.first_name}\n"
                f"⚔️ vs {target_name}\n\n"
                f"နှစ်ယောက်လုံးက\n"
                f"🔴 ခေါင်း / 🔵 အမြီး\n"
                f"ထဲက တစ်ခုရွေးပါ။\n\n"
                f"🔒 Choice message ကို "
                f"{GAME_DELETE_TIME} စက္ကန့်နောက် ဖျက်မယ်။\n"
                f"နှစ်ယောက်လုံးရွေးပြီးမှ Result ပြမယ်။"
            )

            return

        # Reply မဟုတ်ဘူးဆိုရင် Help
        reply_game_message(
            message,
            "🪙 COIN FLIP\n\n"
            "🤖 Bot နဲ့ကစားရန်\n"
            "/coin ခေါင်း\n"
            "/coin အမြီး\n\n"
            "👥 သူငယ်ချင်းနဲ့ကစားရန်\n"
            "/coin @username\n\n"
            "👤 Username ရှိ/မရှိ မလိုပါဘူး။\n"
            "သူ့ message ကို Reply လုပ်ပြီး /coin လို့လည်း "
            "Challenge လုပ်နိုင်ပါတယ်။"
        )

        return

    choice = args[1].strip().lower()

    # -----------------------------------------------------
    # COIN VS BOT
    # -----------------------------------------------------

    if choice in COIN_ALIASES:

        player_choice = COIN_ALIASES[choice]

        result = flip_coin()

        if player_choice == result:

            result_text = "🎉 မင်းမှန်တယ်!"

        else:

            result_text = "😂 မမှန်ဘူး!"

        reply_game_message(
            message,
            f"🪙 COIN FLIP\n\n"
            f"👤 မင်း — {player_choice}\n"
            f"🪙 Coin — {result}\n\n"
            f"{result_text}"
        )

        return

    # -----------------------------------------------------
    # COIN VS USERNAME
    # -----------------------------------------------------

    if choice.startswith("@"):

        if message.chat.type not in [
            "group",
            "supergroup"
        ]:

            reply_game_message(
                message,
                "❌ လူချင်း Coin ကစားတာကို "
                "Group ထဲမှာပဲ သုံးပါ။"
            )

            return

        target_username = (
            choice[1:].strip().lower()
        )

        challenger = message.from_user

        if not target_username:

            reply_game_message(
                message,
                "❌ Username ထည့်ပေးပါ။"
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
                "လုပ်လို့မရဘူး။"
            )

            return

        # Same challenger already playing
        for game in coin_games.values():

            if (
                game["chat_id"] == message.chat.id
                and game["challenger_id"]
                == challenger.id
            ):

                reply_game_message(
                    message,
                    "⚠️ မင်းမှာ Coin game "
                    "တစ်ခုရှိပြီးသားပါ။"
                )

                return

        game_id = (
            f"coin_{message.chat.id}_"
            f"{challenger.id}_{target_username}"
        )

        coin_games[game_id] = {

            "chat_id": message.chat.id,

            "challenger_id": challenger.id,

            "target_id": None,

            "target_username": target_username,

            "challenger_choice": None,

            "target_choice": None,

            "created": time.time()
        }

        reply_game_message(
            message,
            f"🪙 COIN CHALLENGE!\n\n"
            f"👤 {challenger.first_name}\n"
            f"⚔️ vs @{target_username}\n\n"
            f"နှစ်ယောက်လုံးက\n"
            f"🔴 ခေါင်း / 🔵 အမြီး\n"
            f"ထဲက တစ်ခုရွေးပါ။\n\n"
            f"🔒 Choice message ကို "
            f"{GAME_DELETE_TIME} စက္ကန့်နောက် ဖျက်မယ်။\n"
            f"နှစ်ယောက်လုံးရွေးပြီးမှ Result ပြမယ်။"
        )

        return

    # -----------------------------------------------------
    # INVALID
    # -----------------------------------------------------

    reply_game_message(
        message,
        "❌ Coin command မမှန်ပါ။\n\n"
        "/coin ခေါင်း\n"
        "/coin အမြီး\n"
        "/coin @username\n\n"
        "သို့မဟုတ်\n"
        "သူ့ message ကို Reply လုပ်ပြီး /coin"
    )


@bot.message_handler(
    func=lambda message:
    message.text
    and message.text.strip().lower()
    in [
        "ခေါင်း",
        "အမြီး",
        "heads",
        "tails"
    ]
)
def coin_player_choice(message):

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:
        return

    games = find_coin_games_for_user(
        message.chat.id,
        message.from_user
    )

    if not games:
        return

    if len(games) > 1:
        return

    game_id, game, player_type = games[0]

    choice = COIN_ALIASES[
        message.text.strip().lower()
    ]

    # -----------------------------------------------------
    # CHOICE MESSAGE = 80 SEC နောက်မှ DELETE
    # -----------------------------------------------------

    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    # -----------------------------------------------------
    # PLAYER 1
    # -----------------------------------------------------

    if player_type == "challenger":

        if game["challenger_choice"] is not None:
            return

        game["challenger_choice"] = choice

        send_game_message(
            message.chat.id,
            "🔒 Player 1 choice သိမ်းထားပြီ။"
        )

    # -----------------------------------------------------
    # PLAYER 2
    # -----------------------------------------------------

    else:

        if game["target_choice"] is not None:
            return

        game["target_choice"] = choice

        # Username နဲ့ဝင်လာခဲ့ရင်
        # အခု user ရဲ့ ID ကိုပါ သိမ်းမယ်
        game["target_id"] = (
            message.from_user.id
        )

        send_game_message(
            message.chat.id,
            "🔒 Player 2 choice သိမ်းထားပြီ။"
        )

    # -----------------------------------------------------
    # BOTH CHOSE
    # -----------------------------------------------------

    if (
        game["challenger_choice"] is not None
        and game["target_choice"] is not None
    ):

        result = flip_coin()

        p1 = game["challenger_choice"]

        p2 = game["target_choice"]

        p1_correct = (
            p1 == result
        )

        p2_correct = (
            p2 == result
        )

        if p1_correct and p2_correct:

            result_text = (
                "🤝 နှစ်ယောက်လုံးမှန်တယ်!"
            )

        elif p1_correct:

            result_text = (
                "🏆 Player 1 နိုင်တယ်!"
            )

        elif p2_correct:

            result_text = (
                "🏆 Player 2 နိုင်တယ်!"
            )

        else:

            result_text = (
                "😂 နှစ်ယောက်လုံး မမှန်ဘူး!"
            )

        send_game_message(
            message.chat.id,
            f"🪙 COIN RESULT\n\n"
            f"👤 Player 1 — {p1}\n"
            f"👤 Player 2 — {p2}\n\n"
            f"🪙 Coin — {result}\n\n"
            f"{result_text}"
        )

        del coin_games[game_id]


# =========================================================
# 2. RPS
# =========================================================

rps_games = {}

RPS_ALIASES = {

    "ကျောက်": "ကျောက်",

    "ကျောက်တုံး": "ကျောက်",

    "rock": "ကျောက်",

    "စာရွက်": "စာရွက်",

    "paper": "စာရွက်",

    "ကတ်ကြေး": "ကတ်ကြေး",

    "scissors": "ကတ်ကြေး"
}


def rps_winner(player1, player2):

    # SAME = DRAW
    if player1 == player2:
        return "draw"

    if (
        player1 == "ကျောက်"
        and player2 == "ကတ်ကြေး"
    ):
        return "p1"

    if (
        player1 == "စာရွက်"
        and player2 == "ကျောက်"
    ):
        return "p1"

    if (
        player1 == "ကတ်ကြေး"
        and player2 == "စာရွက်"
    ):
        return "p1"

    return "p2"


def find_rps_games_for_user(chat_id, user):

    games = []

    for game_id, game in rps_games.items():

        if game["chat_id"] != chat_id:
            continue

        if user.id == game["challenger_id"]:

            games.append(
                (game_id, game, "challenger")
            )

        elif game["target_id"] is not None:

            if user.id == game["target_id"]:

                games.append(
                    (game_id, game, "target")
                )

        elif (
            game["target_username"]
            and user.username
            and user.username.lower()
            == game["target_username"].lower()
        ):

            games.append(
                (game_id, game, "target")
            )

    return games


@bot.message_handler(commands=["rps"])
def rps_command(message):

    # Command message = 2 minutes
    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    args = message.text.split()

    # -----------------------------------------------------
    # REPLY CHALLENGE
    # -----------------------------------------------------

    if (
        len(args) == 1
        and message.reply_to_message
    ):

        target = (
            message.reply_to_message.from_user
        )

        challenger = message.from_user

        if target.is_bot:

            reply_game_message(
                message,
                "❌ Bot ကို challenge "
                "လုပ်လို့မရပါ။"
            )

            return

        if target.id == challenger.id:

            reply_game_message(
                message,
                "😂 ကိုယ့်ကိုယ်ကို challenge "
                "လုပ်လို့မရဘူး။"
            )

            return

        for game in rps_games.values():

            if (
                game["chat_id"] == message.chat.id
                and game["challenger_id"]
                == challenger.id
            ):

                reply_game_message(
                    message,
                    "⚠️ မင်းမှာ RPS game "
                    "ရှိပြီးသားပါ။"
                )

                return

        game_id = (
            f"rps_reply_{message.chat.id}_"
            f"{challenger.id}_{target.id}"
        )

        rps_games[game_id] = {

            "chat_id": message.chat.id,

            "challenger_id": challenger.id,

            "target_id": target.id,

            "target_username": None,

            "challenger_choice": None,

            "target_choice": None,

            "created": time.time()
        }

        reply_game_message(
            message,
            f"✊ RPS CHALLENGE!\n\n"
            f"👤 {challenger.first_name}\n"
            f"⚔️ vs {target.first_name}\n\n"
            f"🪨 ကျောက် / ကျောက်တုံး\n"
            f"📄 စာရွက်\n"
            f"✂️ ကတ်ကြေး\n\n"
            f"တစ်ခုစီရွေးပါ။\n\n"
            f"🔒 Choice ကို ချက်ချင်းဖျက်မယ်။\n"
            f"နှစ်ယောက်လုံးရွေးပြီးမှ Result ပြမယ်။"
        )

        return

    # -----------------------------------------------------
    # /rps
    # -----------------------------------------------------

    if len(args) == 1:

        reply_game_message(
            message,
            "✊ RPS\n\n"
            "🤖 Bot နဲ့ကစားရန်\n"
            "/rps ကျောက်\n"
            "/rps စာရွက်\n"
            "/rps ကတ်ကြေး\n\n"
            "🪨 `ကျောက်` နဲ့ `ကျောက်တုံး` "
            "နှစ်ခုလုံးရပါတယ်။\n\n"
            "👥 Username ရှိရင်\n"
            "/rps @username\n\n"
            "👤 Username မရှိရင်\n"
            "သူ့ message ကို Reply → /rps"
        )

        return

    choice = args[1].strip().lower()

    # -----------------------------------------------------
    # RPS VS BOT
    # -----------------------------------------------------

    if choice in RPS_ALIASES:

        player_choice = RPS_ALIASES[choice]

        bot_choice = random.choice([
            "ကျောက်",
            "စာရွက်",
            "ကတ်ကြေး"
        ])

        result = rps_winner(
            player_choice,
            bot_choice
        )

        if result == "draw":

            result_text = "🤝 သရေကျတယ်!"

        elif result == "p1":

            result_text = "🏆 မင်းနိုင်တယ်!"

        else:

            result_text = "🤖 Bot နိုင်တယ်!"

        reply_game_message(
            message,
            f"✊ RPS RESULT\n\n"
            f"👤 မင်း — {player_choice}\n"
            f"🤖 Bot — {bot_choice}\n\n"
            f"{result_text}"
        )

        return

    # -----------------------------------------------------
    # RPS VS USERNAME
    # -----------------------------------------------------

    if choice.startswith("@"):

        if message.chat.type not in [
            "group",
            "supergroup"
        ]:

            reply_game_message(
                message,
                "❌ လူချင်း RPS ကို Group ထဲမှာပဲ ကစားပါ။"
            )

            return

        target_username = (
            choice[1:].strip().lower()
        )

        challenger = message.from_user

        if not target_username:

            reply_game_message(
                message,
                "❌ Username ထည့်ပေးပါ။"
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
                "လုပ်လို့မရဘူး။"
            )

            return

        for game in rps_games.values():

            if (
                game["chat_id"] == message.chat.id
                and game["challenger_id"]
                == challenger.id
            ):

                reply_game_message(
                    message,
                    "⚠️ မင်းမှာ RPS game "
                    "ရှိပြီးသားပါ။"
                )

                return

        game_id = (
            f"rps_username_{message.chat.id}_"
            f"{challenger.id}_{target_username}"
        )

        rps_games[game_id] = {

            "chat_id": message.chat.id,

            "challenger_id": challenger.id,

            "target_id": None,

            "target_username": target_username,

            "challenger_choice": None,

            "target_choice": None,

            "created": time.time()
        }

        reply_game_message(
            message,
            f"✊ RPS CHALLENGE!\n\n"
            f"👤 {challenger.first_name}\n"
            f"⚔️ vs @{target_username}\n\n"
            f"🪨 ကျောက် / ကျောက်တုံး\n"
            f"📄 စာရွက်\n"
            f"✂️ ကတ်ကြေး\n\n"
            f"🔒 Choice ကို ချက်ချင်းဖျက်မယ်။\n"
            f"နှစ်ယောက်လုံးရွေးပြီးမှ Result ပြမယ်။"
        )

        return

    reply_game_message(
        message,
        "❌ RPS command မမှန်ပါ။"
    )


@bot.message_handler(
    func=lambda message:
    message.text
    and message.text.strip().lower()
    in [
        "ကျောက်",
        "ကျောက်တုံး",
        "rock",
        "စာရွက်",
        "paper",
        "ကတ်ကြေး",
        "scissors"
    ]
)
def rps_player_choice(message):

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:
        return

    games = find_rps_games_for_user(
        message.chat.id,
        message.from_user
    )

    if not games:
        return

    if len(games) > 1:
        return

    game_id, game, player_type = games[0]

    normalized_choice = RPS_ALIASES[
        message.text.strip().lower()
    ]

    # CHOICE = IMMEDIATELY DELETE

    try:

        bot.delete_message(
            message.chat.id,
            message.message_id
        )

    except Exception as e:

        print(
            f"RPS Choice Delete Error: {e}"
        )

    # -----------------------------------------------------
    # PLAYER 1
    # -----------------------------------------------------

    if player_type == "challenger":

        if game["challenger_choice"] is not None:
            return

        game["challenger_choice"] = (
            normalized_choice
        )

        send_game_message(
            message.chat.id,
            "🔒 Player 1 choice သိမ်းထားပြီ။"
        )

    # -----------------------------------------------------
    # PLAYER 2
    # -----------------------------------------------------

    else:

        if game["target_choice"] is not None:
            return

        game["target_choice"] = (
            normalized_choice
        )

        game["target_id"] = (
            message.from_user.id
        )

        send_game_message(
            message.chat.id,
            "🔒 Player 2 choice သိမ်းထားပြီ။"
        )

    # -----------------------------------------------------
    # BOTH CHOSE
    # -----------------------------------------------------

    if (
        game["challenger_choice"] is not None
        and game["target_choice"] is not None
    ):

        p1 = game["challenger_choice"]

        p2 = game["target_choice"]

        result = rps_winner(
            p1,
            p2
        )

        if result == "draw":

            result_text = (
                "🤝 သရေကျတယ်!"
            )

        elif result == "p1":

            result_text = (
                "🏆 Player 1 နိုင်တယ်!"
            )

        else:

            result_text = (
                "🏆 Player 2 နိုင်တယ်!"
            )

        send_game_message(
            message.chat.id,
            f"✊ RPS RESULT\n\n"
            f"👤 Player 1 — {p1}\n"
            f"👤 Player 2 — {p2}\n\n"
            f"{result_text}"
        )

        del rps_games[game_id]


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
            "🎱 မေးခွန်းထည့်ပြီးမေးဟ လီလား\n\n"
            "ဥပမာ\n"
            "/8ball ဒီနေ့ကံကောင်းမလား?"
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
# 4. GUESS - MULTIPLAYER
# =========================================================

guess_games = {}


@bot.message_handler(commands=["guess", "ခန့်မှန်း"])
def guess_command(message):

    if message.chat.type not in ["group", "supergroup"]:
        reply_game_message(
            message,
            "❌ Group ထဲမှာပဲ Guess Game ကစားလို့ရပါတယ်။"
        )
        return

    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    # Game တစ်ခုကို Group တစ်ခုအတွက်ပဲထားမယ်
    chat_id = message.chat.id

    # လက်ရှိ game ရှိပြီးသားဆိုရင် အသစ်မစ
    if chat_id in guess_games:

        reply_game_message(
            message,
            "🎯 Guess Game ကစားနေပြီးသားပါ။\n\n"
            "👥 Group ထဲက ဘယ်သူမဆို ဝင်ခန့်မှန်းလို့ရပါတယ်။\n"
            "🏆 တစ်ယောက်မှန်သွားရင် Game ပြီးပါပြီ။"
        )

        return

    # Game အသစ်
    guess_games[chat_id] = {

        "number": random.randint(
            1,
            100
        ),

        "tries": 0,

        "created": time.time()
    }

    reply_game_message(
        message,
        "🎯 GUESS GAME စပြီ!\n\n"
        "1 ကနေ 100 အတွင်းက number "
        "တစ်ခု ငါရွေးထားပြီ။\n\n"
        "👥 Group ထဲက ဘယ်သူမဆို ဝင်ခန့်မှန်းလို့ရတယ်။\n"
        "🔢 1 ကနေ 100 အတွင်းက number ပို့ပါ။\n\n"
        "🏆 အရင်ဆုံးမှန်တဲ့သူက Winner!"
    )


@bot.message_handler(
    func=lambda message:
    message.text
    and message.text.strip().isdigit()
)
def guess_number(message):

    chat_id = message.chat.id

    # ဒီ Group မှာ Guess Game မရှိရင်
    # ပုံမှန် number message အနေနဲ့ပဲထားမယ်
    if chat_id not in guess_games:
        return

    try:

        number = int(
            message.text.strip()
        )

    except:

        return

    if number < 1 or number > 100:

        reply_game_message(
            message,
            "❌ 1 ကနေ 100 အတွင်းက number ပဲ ပို့ပါ။"
        )

        return

    # Guess message ကို ဖျက်မယ်
    delay_delete_message(
        message.chat.id,
        message.message_id,
        GAME_DELETE_TIME
    )

    game = guess_games[chat_id]

    # Group တစ်ခုလုံးရဲ့ total attempts
    game["tries"] += 1

    target = game["number"]

    # =====================================================
    # CORRECT
    # =====================================================

    if number == target:

        winner = message.from_user

        # Username ရှိရင် @username
if winner.username:
    winner_display = f"@{winner.username}"
else:
    # Username မရှိရင် Telegram First Name
    winner_display = winner.first_name or "Unknown User"

            winner_display = (
                f"<a href='tg://user?id={winner.id}'>"
                f"{winner_name}"
                f"</a>"
            )

        reply_game_message(
            message,
            f"🎯 CORRECT!\n\n"
            f"🏆 Number က {target} ပါ!\n"
            f"📊 {game['tries']} ကြိမ်နဲ့ မှန်သွားပြီ!\n\n"
            f"👑 Winner — {winner_display}"
        )

        # Game ပြီးသွားပြီ
        del guess_games[chat_id]

        return

    # =====================================================
    # TOO LOW
    # =====================================================

    if number < target:

        reply_game_message(
            message,
            "📈 ပိုကြီးတဲ့ number ဖြစ်တယ်။"
        )

    # =====================================================
    # TOO HIGH
    # =====================================================

    else:

        reply_game_message(
            message,
            "📉 ပိုသေးတဲ့ number ဖြစ်တယ်။"
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
    # RPS
    # -----------------------------------------------------

    expired_rps = []

    for game_id, game in rps_games.items():

        if (
            now - game["created"]
            > GAME_DELETE_TIME
        ):

            expired_rps.append(
                game_id
            )

    for game_id in expired_rps:

        del rps_games[game_id]

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
        "📢 /start — Members ခေါ်ရန်\n"
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

        # =================================================
        # 🚨 TEXT SPAM CHECK
        # =================================================

        count = check_spam(
            chat_id,
            user_id,
            "text",
            message.message_id
        )

        if count >= SPAM_LIMIT:

            # Spam window ထဲက message အားလုံးဖျက်
            delete_spam_messages(
                chat_id,
                user_id,
                "text"
            )

            # User ကို Mute
            mute_user(
                chat_id,
                user_id,
                name,
                "စိတ်အေးအေးထား ငါလိုးမတောသားး"
            )

            return

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
