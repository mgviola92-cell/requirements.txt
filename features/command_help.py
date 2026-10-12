"""Complete static command directory; no owner data is exposed by help."""
import json
import logging
from pathlib import Path
from flask import send_file
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.customization import message_text

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = json.loads((ROOT / 'config/command_reference.json').read_text())
GUIDE = ROOT / 'docs/bot_user_guide.html'
MESSAGES = {'home':'📋 Bot အသုံးပြုနည်း\nအောက်က အပိုင်းကိုရွေးပါ။ Command၊ alias၊ အသုံးပြုနိုင်သည့်နေရာနှင့် permission အားလုံး ပါဝင်သည်။\nအသေးစိတ်ဖိုင်: /guide\nကိုယ်ပိုင် command စာရင်း: /commands', 'download':'📥 အသုံးပြုနည်းဖိုင်', 'back':'↩️ အဓိကစာရင်း', 'all':'📋 Command အားလုံး', 'error':'ဖိုင်ပို့မရသေးပါ။ ခဏနေရင် /guide ပြန်သုံးပါ။'}

def text(key):
    return message_text('msg.features.command_help.'+key, MESSAGES[key], {})

def pages(category):
    entries = [e for e in REFERENCE['entries'] if category == 'all' or e['category'] == category]
    result, current = [], []
    for e in entries:
        names = ' ၊ '.join('/'+a for a in e['aliases']) or e['title']
        row = names+' — '+e['title']+'\n📍 '+e['where']+' | '+e['who']+'\n'+e['usage']+'\n'
        if current and len('\n'.join(current+[row])) > 2900:
            result.append('\n'.join(current)); current=[]
        current.append(row)
    if current: result.append('\n'.join(current))
    return result or ['မရှိသေးပါ။']

def view(category='home', page=0):
    keyboard = InlineKeyboardMarkup()
    if category == 'home':
        body = text('home')
        for key, label in REFERENCE['categories'].items():
            keyboard.row(InlineKeyboardButton(label, callback_data='cmdh:'+key+':0'))
        keyboard.row(InlineKeyboardButton(text('all'), callback_data='cmdh:all:0'))
    else:
        chunks=pages(category); page=max(0,min(page,len(chunks)-1))
        title = REFERENCE['categories'].get(category,text('all'))
        body=title+' ('+str(page+1)+'/'+str(len(chunks))+')\n\n'+chunks[page]
        navigation=[]
        if page: navigation.append(InlineKeyboardButton('◀️', callback_data=f'cmdh:{category}:{page-1}'))
        if page+1<len(chunks): navigation.append(InlineKeyboardButton('▶️', callback_data=f'cmdh:{category}:{page+1}'))
        if navigation: keyboard.row(*navigation)
        keyboard.row(InlineKeyboardButton(text('back'),callback_data='cmdh:home:0'))
    keyboard.row(InlineKeyboardButton(text('download'), callback_data='cmdh:download:0'))
    return body, keyboard

def show(bot,message):
    body, keyboard=view()
    bot.send_message(message.chat.id,body,reply_markup=keyboard,parse_mode=None)

def download(bot,cid):
    try:
        with GUIDE.open('rb') as source:
            bot.send_document(cid, source, visible_file_name='bot_user_guide.html')
    except Exception:
        logging.getLogger(__name__).exception('Command guide delivery failed')
        bot.send_message(cid,text('error'),parse_mode=None)

def register(app,bot):
    @app.get('/guide')
    def public_guide():
        return send_file(GUIDE,as_attachment=True,download_name='bot_user_guide.html')

    @bot.message_handler(commands=['guide','helpguide'])
    def guide_command(message):
        download(bot,message.chat.id)

    @bot.callback_query_handler(func=lambda c:bool(c.data and c.data.startswith('cmdh:')))
    def command_page(call):
        # Ack immediately, including invalid or stale buttons.
        bot.answer_callback_query(call.id)
        if not call.message: return
        try:
            _, category, raw=call.data.split(':'); page=int(raw)
        except (ValueError,AttributeError): return
        if category=='download':
            download(bot,call.message.chat.id); return
        if category not in {'home','all',*REFERENCE['categories']}: return
        body,keyboard=view(category,page)
        try:
            bot.edit_message_text(body,call.message.chat.id,call.message.message_id,reply_markup=keyboard,parse_mode=None)
        except Exception as exc:
            if 'message is not modified' not in str(exc).lower():
                logging.getLogger(__name__).warning('Command help edit failed: %s',exc)
