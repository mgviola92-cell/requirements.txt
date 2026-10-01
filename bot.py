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
