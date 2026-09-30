import telebot
import time

BOT_TOKEN = '8956351614:AAFtAaY7qxcFufuFoxraPBcRku40PpgVwAA'
bot = telebot.TeleBot(BOT_TOKEN)

FINISH_MESSAGE = "တောသားတွေကိုခေါ်ပြီးပြီ Daddy <3...."

@bot.message_handler(commands=['start', 'all', 'everyone', 'လာကြစမ်း'])
def mention_all_users(message):
    if message.chat.type in ['group', 'supergroup']:
        chat_id = message.chat.id

        # စာသားကို မျက်တောင်ကွင်းများနှင့် အကွင်းများ လုံးဝမပါဘဲ မြန်မာစာသက်သက်အဖြစ် ပြောင်းလဲခြင်း
        user_text = message.text.split(maxsplit=1)
        if len(user_text) > 1:
            input_line = str(user_text[1])  # စာသားအစစ်အဖြစ် သေချာပေါက် ပြောင်းလဲလိုက်ခြင်း
        else:
            input_line = "တောသားတွေကိုခေါ်နေပြီ လာကြစမ်း"

        try:
            chat_admins = bot.get_chat_administrators(chat_id)

            user_list = []
            for admin in chat_admins:
                if not admin.user.is_bot:
                    user_list.append(admin.user.id)

            # စာစောင်အရေအတွက် ၂၀ ကြိမ် ပို့မည့်အပိုင်း
            for _ in range(30):
                hidden_mentions = ""
                for u_id in user_list:
                    hidden_mentions += f"<a href='tg://user?id={u_id}'>​</a>"

                final_message = f"{input_line}{hidden_mentions}"
                bot.send_message(chat_id, final_message, parse_mode='HTML')
                time.sleep(2)

        except Exception as e:
            print(f"Error caught inside loop: {e}")

        finally:
            # ဘာ Error ပဲတက်တက်၊ ဘာပဲဖြစ်ဖြစ် ဒီ Finish Message ကိုတော့ အောက်ဆုံးကနေ မဖြစ်မနေ ထွက်လာအောင် လုပ်ပေးမည့်အပိုင်း
            try:
                time.sleep(2)
                bot.send_message(chat_id, str(FINISH_MESSAGE))
            except Exception as e:
                print(f"Error sending finish message: {e}")

    else:
        bot.reply_to(message, "This command can only be used in Telegram Groups.")

print("Final Fixed Bot is running...")
bot.infinity_polling()
