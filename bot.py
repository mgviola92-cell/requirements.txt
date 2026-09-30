import telebot
import time
import random
import yt_dlp
import os
import threading

BOT_TOKEN = '8956351614:AAFtAaY7qxcFufuFoxraPBcRku40PpgVwAA'
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

        # ⏱️ ၄၀ စက္ကန့် Cooldown တွက်ချက်ခြင်း
        current_time = time.time()
        if last_called_time != 0 and (current_time - last_called_time) < 100:
            remaining_time = int(100 - (current_time - last_called_time))

            if remaining_time > 40:
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
                remaining_cooldown = int(100 - (finish_time - last_called_time))
                if remaining_cooldown > 40:
                    remaining_cooldown = 40

                custom_finish_message = f"ခေါ်ပြီးဘီ လီးဖစ်နေလား (နောက်ထပ် {remaining_cooldown} စက္ကန့် စောင့်ဦး)"
                finish_msg = bot.send_message(chat_id, custom_finish_message)

                # 🎯 Finish Message ကိုပါ ၁ မိနစ်ပြည့်လျှင် ပြန်ဖျက်ခိုင်းခြင်း
                delay_delete_message(chat_id, finish_msg.message_id, 60)
            except Exception as e:
                print(f"Error sending finish message: {e}")

    else:
        bot.reply_to(message, "This command can only be used in Telegram Groups.")

# --- ၂။ သီချင်းတောင်းသည့် လုပ်ဆောင်ချက် (/play Function) ---
@bot.message_handler(commands=['play', 'ဖွင့်'])
def play_music(message):
    user_text = message.text.split(maxsplit=1)
    if len(user_text) > 1:
        song_name = user_text
        reply_msg = bot.reply_to(message, f"🎵 '{song_name}' ပို့ပေးမယ် ခနစောင့်တောသား")

        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'song.mp3',
                'default_search': 'ytsearch1',
                'noplaylist': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([song_name])

            if os.path.exists('song.mp3'):
                with open('song.mp3', 'rb') as audio:
                    bot.send_audio(message.chat.id, audio, caption="🎧 သီချင်းရပြီ တောသားနားထောင်တော့")
                os.remove('song.mp3')
                bot.delete_message(message.chat.id, reply_msg.message_id)
            else:
                bot.reply_to(message, "❌ မင်းစောက်ပေါသီချင်း ရှာမတွေ့ဘူး")

        except Exception as e:
            print(f"Download Error: {e}")
            bot.reply_to(message, "❌ သီချင်းနာမည် မှားနေတယ် စောက်ရူး သေချာပြန်ရိုက် ဖြတ်ထိုးလိုက်မယ်")
    else:
        bot.reply_to(message, "❌ ဒီတိုင်းရိုက် `/play [Song]` ")

# --- ၃။ လူသစ်ဝင်လာလျှင် အလိုအလျောက် နှုတ်ဆက်သည့်စနစ် (Welcome Message) ---
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    try:
        for new_member in message.new_chat_members:
            if not new_member.is_bot:
                member_name = new_member.first_name
                welcome_text = f"👋 မင်္ဂလာပါ တောသား [{member_name}]\n ကြိုက်တာလုပ်လို့ရပါတယ် ဘမ်းချင်ရင်လည်း ဘမ်းမာပါ 🎉✨"
                bot.send_message(message.chat.id, welcome_text)
    except Exception as e:
        print(f"Welcome Error: {e}")

# --- ၄။ ဖျော်ဖြေရေးစနစ်များ (Entertainment Functions) ---

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

print("Perfect 4-Emoji Music Bot is running...")
bot.infinity_polling()
