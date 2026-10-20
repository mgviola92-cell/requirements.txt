"""Private owner-only source picker. Drafts do not change active settings."""
import secrets
import threading
import time
from telebot import types
from core.customization import save,refresh
from data.news_sources import CATALOG
from features import news

LOCK=threading.RLock()
DRAFTS={}
PAGE=8


def register(bot,replace_card,clear_draft):
    def allowed(update):
        from features.owner_operations import is_owner
        chat=getattr(update,'chat',None) or getattr(getattr(update,'message',None),'chat',None)
        return bool(chat and chat.type=='private' and update.from_user and is_owner(update.from_user.id))

    def show(uid,draft,page=0,notice=''):
        ids=list(CATALOG);page=max(0,min(page,(len(ids)-1)//PAGE));draft['page']=page
        kb=types.InlineKeyboardMarkup(row_width=1)
        for sid in ids[page*PAGE:(page+1)*PAGE]:
            label=('✅ ' if sid in draft['selected'] else '⬜ ')+CATALOG[sid]['name']
            kb.add(types.InlineKeyboardButton(label[:55],callback_data=f"nws:{draft['token']}:toggle:{sid}"))
        nav=[]
        if page:nav.append(types.InlineKeyboardButton('⬅️ ရှေ့',callback_data=f"nws:{draft['token']}:page:{page-1}"))
        if (page+1)*PAGE<len(ids):nav.append(types.InlineKeyboardButton('နောက် ➡️',callback_data=f"nws:{draft['token']}:page:{page+1}"))
        if nav:kb.row(*nav)
        kb.row(types.InlineKeyboardButton('အားလုံးရွေး',callback_data=f"nws:{draft['token']}:all"),types.InlineKeyboardButton('အားလုံးဖြုတ်',callback_data=f"nws:{draft['token']}:none"))
        kb.row(types.InlineKeyboardButton('💾 သိမ်းမယ်',callback_data=f"nws:{draft['token']}:save"),types.InlineKeyboardButton('❌ မသိမ်းတော့ပါ',callback_data='own:menu'))
        body='📰 သတင်းဌာနရွေးရန်\n\n'+f"ရွေးထားသည် — {len(draft['selected'])} / {len(ids)} ဌာန\nစာမျက်နှာ {page+1} / {(len(ids)+PAGE-1)//PAGE}\n\n"
        body+='Group အားလုံးအတွက် သက်ရောက်မည်။ ရွေးထားသည့်ဌာန တစ်ခုခုမှ သတင်းအသစ်ရလျှင် feed စစ်ချိန်တွင် စုပို့မည်။\n\nသိမ်းမယ် နှိပ်မှ အတည်ဖြစ်မည်။ ၀ ဌာနဆို သတင်းပို့ခြင်းကို ရပ်ထားမည်။'
        if notice:body+='\n\n'+notice
        replace_card(uid,uid,body,kb)
        from features.owner_dashboard import _load_panel_state
        _,mid,_=_load_panel_state(uid);draft['message']=mid

    def open_picker(uid):
        clear_draft(uid);refresh(force=True)
        selected=set(news.sources_for(0))
        draft={'token':secrets.token_hex(4),'selected':selected.copy(),'base':selected,'opened':time.monotonic(),'page':0}
        DRAFTS[uid]=draft;show(uid,draft)

    @bot.message_handler(commands=['newsowner'])
    def news_owner_command(m):
        if not allowed(m):return
        try:
            with LOCK:open_picker(m.from_user.id)
        except Exception:bot.reply_to(m,'သတင်းဌာနရွေးချယ်မှု ဖွင့်မရသေးပါ။ ခဏနေ /newsowner ပြန်သုံးပါ။')

    @bot.callback_query_handler(func=lambda q:bool(q.data and q.data.startswith('nws:')))
    def news_owner_callback(q):
        if not allowed(q):
            bot.answer_callback_query(q.id,'Owner private chat တွင်သာ သုံးနိုင်သည်။',show_alert=True);return
        try:
            with LOCK:
                uid=q.from_user.id
                if q.data=='nws:open':
                    bot.answer_callback_query(q.id);open_picker(uid);return
                parts=q.data.split(':');draft=DRAFTS.get(uid)
                from features.owner_dashboard import _load_panel_state
                _,latest,_=_load_panel_state(uid)
                if not draft or len(parts)<3 or parts[1]!=draft['token'] or time.monotonic()-draft['opened']>1800 or q.message.message_id!=draft.get('message') or q.message.message_id!=latest:
                    bot.answer_callback_query(q.id,'Menu ဟောင်းပါ။ /newsowner ဖြင့် ပြန်ဖွင့်ပါ။',show_alert=True);return
                action=parts[2]
                if action=='toggle' and len(parts)==4 and parts[3] in CATALOG:draft['selected'].symmetric_difference_update([parts[3]])
                elif action=='all':draft['selected']=set(CATALOG)
                elif action=='none':draft['selected']=set()
                elif action=='page' and len(parts)==4:
                    bot.answer_callback_query(q.id);show(uid,draft,int(parts[3]));return
                elif action=='save':
                    refresh(force=True)
                    if set(news.sources_for(0))!=draft['base']:
                        bot.answer_callback_query(q.id,'Setting ပြောင်းထားပြီးပါပြီ။ အသစ်ပြန်ဖွင့်ပါ။',show_alert=True);DRAFTS.pop(uid,None);return
                    selected=[sid for sid in CATALOG if sid in draft['selected']]
                    save(0,'cfg.features.news.source_ids',selected,uid)
                    draft['base']=set(selected)
                    bot.answer_callback_query(q.id,'သိမ်းပြီးပြီ။')
                    show(uid,draft,draft['page'],'✅ သိမ်းပြီးပြီ။ အသစ်ရွေးသည့်ဌာန၏ သတင်းဟောင်းများကို auto ပြန်မပို့ပါ။');return
                else:
                    bot.answer_callback_query(q.id);return
                bot.answer_callback_query(q.id);show(uid,draft,draft['page'])
        except Exception:
            try:bot.answer_callback_query(q.id,'သိမ်းမရသေးပါ။ /newsowner ဖြင့် ပြန်စမ်းပါ။',show_alert=True)
            except Exception:pass
