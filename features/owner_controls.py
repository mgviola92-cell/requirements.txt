"""The same persistent group/default editor on the owner website and Telegram."""
import html
import json
import os
import secrets
from datetime import datetime,timezone
from urllib.parse import urlencode
from flask import Blueprint,request,redirect,url_for,abort
from telebot import types
from telebot.handler_backends import ContinueHandling
from database.db import get_db_connection
from core.customization import CATALOG,effective,save,preview,validate

controls=Blueprint('owner_controls',__name__,url_prefix='/owner/control')
KEYS=sorted(CATALOG)
CATEGORIES=sorted({e['category'] for e in CATALOG.values()})
LABELS={'bot':'Commands & Group Management','system':'System Messages','core.rewards':'Game Rewards',
        'core.keyboards':'Buttons','wyr_auto':'WYR Auto Spawn',
        'config.ranks':'Rank Tiers','database.daily_challenge':'Daily Missions & Rewards'}

def category_label(category):
    return LABELS.get(category,category.split('.')[-1].replace('_',' ').title())

def groups():
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT chat_id,title FROM owner_groups WHERE active ORDER BY title')
        return cur.fetchall()

def check_scope(scope):
    if scope==0:return
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT 1 FROM owner_groups WHERE chat_id=%s',(scope,))
        if not cur.fetchone():raise ValueError('Unknown group')

def read_scope(value):
    try:scope=int(value or 0)
    except (ValueError,TypeError):raise ValueError('Invalid group')
    check_scope(scope)
    return scope

def decode_value(key,text):
    entry=CATALOG[key]
    if key in ('cfg.features.comfort.nickname','cfg.features.comfort.emojis'):return text.strip()
    if entry['kind']=='message':return text
    if isinstance(entry['default'],bool) and text.strip().lower() in ('on','off'):return text.strip().lower()=='on'
    try:return json.loads(text)
    except ValueError:raise ValueError('Use a number, true/false, or valid JSON for lists/objects')

def encoded(value):return value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)


def register(app,bot,replace_card,back_button,clear_draft):
    controls=Blueprint('owner_controls',__name__,url_prefix='/owner/control')
    from features.owner_dashboard import _protect,_verify_csrf,_csrf,_shell,_load_panel_state
    @_protect
    def index():
        try:scope=read_scope(request.args.get('scope'))
        except ValueError as exc:return str(exc),400
        kind=request.args.get('kind','message');category=request.args.get('category','');query=request.args.get('q','').casefold()
        try:page=max(0,int(request.args.get('page',0)))
        except ValueError:page=0
        matches=[k for k in KEYS if CATALOG[k]['kind']==kind and (not category or CATALOG[k]['category']==category)
                 and (not query or query in (CATALOG[k]['label']+' '+encoded(CATALOG[k]['default'])).casefold())]
        choices="<option value='0'>All Groups · Default</option>"+''.join(f"<option value='{gid}' {'selected' if gid==scope else ''}>{html.escape(title or str(gid))}</option>" for gid,title in groups())
        cats="<option value=''>All categories</option>"+''.join(f"<option value='{html.escape(c)}' {'selected' if category==c else ''}>{html.escape(category_label(c))}</option>" for c in CATEGORIES)
        body=f'''<h1>Group Control & Bot Messages</h1><p>Default applies to every group. Group overrides take priority. Reset removes the override.</p>
        <form method='get' class='panel'><label>Group</label><select name='scope'>{choices}</select>
        <label>Customize</label><select name='kind'><option value='message' {'selected' if kind=='message' else ''}>Bot Messages</option><option value='setting' {'selected' if kind=='setting' else ''}>Settings & Functions</option></select>
        <label>Category</label><select name='category'>{cats}</select><input name='q' value='{html.escape(request.args.get('q',''),quote=True)}' placeholder='Search command, message or setting'><button>Search</button></form>
        <p>{len(matches)} entries · <a href='/owner/control/history'>Change History</a></p>'''
        for key in matches[page*20:(page+1)*20]:
            e=CATALOG[key];link='/owner/control/edit?'+urlencode({'scope':scope,'key':key})
            body+=f"<div class='panel'><small>{html.escape(category_label(e['category']))}</small><h2>{html.escape(e['label'])}</h2><pre style='white-space:pre-wrap;overflow-wrap:anywhere'>{html.escape(encoded(effective(key,scope))[:300])}</pre><a href='{html.escape(link,quote=True)}'>Edit / Preview / Reset</a></div>"
        for label,p in [('Previous',page-1),('Next',page+1)]:
            if p>=0 and p*20<len(matches):body+=f"<a style='margin-right:20px' href='?{html.escape(urlencode(dict(scope=scope,kind=kind,category=category,q=query,page=p)),quote=True)}'>{label}</a>"
        return _shell(body)

    @_protect
    def edit():
        data=request.form if request.method=='POST' else request.args
        key=data.get('key','')
        if key not in CATALOG:abort(404)
        try:scope=read_scope(data.get('scope'))
        except ValueError as exc:return str(exc),400
        e=CATALOG[key];notice='';value=effective(key,scope)
        if request.method=='POST':
            _verify_csrf()
            try:
                action=data.get('action','preview')
                if action=='reset':value=save(scope,key,None,int(os.getenv('OWNER_TELEGRAM_ID','0')),reset=True);notice='Reset to inherited/default value.'
                else:
                    value=decode_value(key,data.get('value',''));validate(key,value)
                    if action=='save':save(scope,key,value,int(os.getenv('OWNER_TELEGRAM_ID','0')));notice='Saved. Web and Telegram use the same setting.'
                    else:notice='Preview only; not saved.'
            except ValueError as exc:notice=str(exc);value=effective(key,scope)
        fields=', '.join('{'+f+'}' for f in e.get('fields',[])) or 'None'
        body=f'''<h1>{html.escape(e['label'])}</h1><p><a href='/owner/control?scope={scope}&kind={e['kind']}'>← Back to catalog</a></p>
        <p class='ok'>{html.escape(notice)}</p><div class='panel'><p>Scope: {'All Groups · Default' if scope==0 else scope}</p>
        <p>Available placeholders: {html.escape(fields)}</p><p>{'Telegram HTML formatting is supported.' if e.get('html') else 'Plain text. Keep placeholder names unchanged.'}</p>
        <form method='post'><input type='hidden' name='csrf' value='{html.escape(_csrf(),quote=True)}'><input type='hidden' name='scope' value='{scope}'>
        <input type='hidden' name='key' value='{html.escape(key,quote=True)}'><textarea name='value' style='min-height:220px'>{html.escape(encoded(value))}</textarea>
        <button name='action' value='preview'>Preview</button> <button name='action' value='save'>Save</button> <button name='action' value='reset'>Reset</button></form></div>
        <div class='panel'><h2>Preview</h2><pre style='white-space:pre-wrap;overflow-wrap:anywhere'>{html.escape(preview(key,value,scope))}</pre></div>
        <details class='panel'><summary>Original default</summary><pre style='white-space:pre-wrap'>{html.escape(encoded(e['default']))}</pre></details>'''
        return _shell(body)

    @_protect
    def history():
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute('SELECT scope,key,action,created_at FROM owner_customization_log ORDER BY id DESC LIMIT 100')
            entries=cur.fetchall()
        body="<h1>Customization History</h1><a href='/owner/control'>← Group Control</a><div class='panel'><table><tr><th>Group</th><th>Entry</th><th>Action</th><th>UTC</th></tr>"
        for scope,key,action,date in entries:
            body+=f"<tr><td>{'Default' if scope==0 else scope}</td><td>{html.escape(CATALOG.get(key,{}).get('label',key))}</td><td>{html.escape(action)}</td><td>{html.escape(str(date)[:19])}</td></tr>"
        return _shell(body+'</table></div>')
    controls.add_url_rule('/',view_func=index)
    controls.add_url_rule('/edit',view_func=edit,methods=['GET','POST'])
    controls.add_url_rule('/history',view_func=history)
    app.register_blueprint(controls)

    def owner(update):
        chat=getattr(update,'chat',None) or getattr(getattr(update,'message',None),'chat',None)
        from features.owner_operations import can
        return bool(chat and chat.type=='private' and update.from_user and can(update.from_user.id,'edit'))
    def button(text,data):return types.InlineKeyboardButton(text,callback_data=data)
    def card(uid,text,kb):replace_card(uid,uid,text,kb)
    def clear_edit(uid):
        with get_db_connection() as conn,conn.cursor() as cur:cur.execute('DELETE FROM owner_control_edit WHERE owner_id=%s',(uid,))
    def home(uid,page=0):
        entries=[(0,'🌍 All Groups · Default')]+groups()
        kb=types.InlineKeyboardMarkup(row_width=1)
        for cid,title in entries[page*15:(page+1)*15]:kb.add(button((title or str(cid))[:50],f'ctl:scope:{cid}'))
        if page:kb.add(button('← Previous',f'ctl:home:{page-1}'))
        if (page+1)*15<len(entries):kb.add(button('Next →',f'ctl:home:{page+1}'))
        from features.owner_operations import is_owner
        kb.add(button('⬅️ Owner Panel' if is_owner(uid) else '⬅️ Staff Panel','own:menu' if is_owner(uid) else 'ops:home'))
        card(uid,'⚙️ GROUP CONTROL\n\nDefault သို့မဟုတ် ပြင်ချင်တဲ့ Group ကို ရွေးပါ။',kb)
    def menu(uid,scope):
        kb=types.InlineKeyboardMarkup(row_width=1)
        kb.add(button('💌 ချော့စာ ဆက်တင်',f'ctl:list:{scope}:setting:{CATEGORIES.index('ချော့စာ')}:0'),
               button('📖 ချော့စာများ ကြည့် / ပြင်',f'ctl:list:{scope}:message:{CATEGORIES.index('ချော့စာ စာတိုဘဏ်')}:0'))
        kb.add(button('💬 Bot Messages',f'ctl:cats:{scope}:message'),button('⚙️ Settings & Functions',f'ctl:cats:{scope}:setting'),button('⬅️ Groups','ctl:home:0'))
        card(uid,f"⚙️ {'All Groups · Default' if scope==0 else 'Group '+str(scope)}\n\nပြင်ချင်တဲ့အပိုင်းကို ရွေးပါ။",kb)
    def categories(uid,scope,kind):
        kb=types.InlineKeyboardMarkup(row_width=1)
        for i,c in enumerate(CATEGORIES):
            if any(e['kind']==kind and e['category']==c for e in CATALOG.values()):kb.add(button(category_label(c),f'ctl:list:{scope}:{kind}:{i}:0'))
        kb.add(button('⬅️ Back',f'ctl:scope:{scope}'))
        card(uid,'💬 Messages' if kind=='message' else '⚙️ Settings & Functions',kb)
    def listing(uid,scope,kind,cat,page):
        category=CATEGORIES[cat]
        matches=[(i,k) for i,k in enumerate(KEYS) if CATALOG[k]['kind']==kind and CATALOG[k]['category']==category]
        kb=types.InlineKeyboardMarkup(row_width=1)
        for i,k in matches[page*8:(page+1)*8]:kb.add(button(CATALOG[k]['label'][:55],f'ctl:item:{scope}:{i}'))
        if page:kb.add(button('← Previous',f'ctl:list:{scope}:{kind}:{cat}:{page-1}'))
        if (page+1)*8<len(matches):kb.add(button('Next →',f'ctl:list:{scope}:{kind}:{cat}:{page+1}'))
        kb.add(button('⬅️ Categories',f'ctl:cats:{scope}:{kind}'))
        card(uid,f"{category_label(category)}\n\n{page+1} / {max(1,(len(matches)+7)//8)}",kb)
    def item(uid,scope,ix):
        key=KEYS[ix];e=CATALOG[key]
        kb=types.InlineKeyboardMarkup(row_width=2)
        kb.add(button('✏️ Edit',f'ctl:edit:{scope}:{ix}'),button('👀 Preview',f'ctl:preview:{scope}:{ix}'))
        kb.add(button('↩️ Reset',f'ctl:reset:{scope}:{ix}'),button('⬅️ Back',f"ctl:cats:{scope}:{e['kind']}"))
        placeholders=' '.join('{'+f+'}' for f in e.get('fields',[])) or '—'
        card(uid,e['label'][:120]+'\n\n'+encoded(effective(key,scope))[:2000]+'\n\nPlaceholders: '+placeholders[:800],kb)

    @bot.message_handler(commands=['control','groupcontrol'])
    def owner_control_command(msg):
        if not owner(msg):return ContinueHandling()
        clear_edit(msg.from_user.id);clear_draft(msg.from_user.id);home(msg.from_user.id)
        return ContinueHandling()

    @bot.callback_query_handler(func=lambda q:bool(q.data and q.data.startswith('ctl:')))
    def owner_control_action(q):
        if not owner(q):
            bot.answer_callback_query(q.id,'Owner private chat only.',show_alert=True);return
        uid=q.from_user.id
        try:
            _,latest,_=_load_panel_state(uid)
            if not latest or q.message.message_id!=latest:
                bot.answer_callback_query(q.id,'Menu ဟောင်းပါ။ /control နဲ့ ပြန်ဖွင့်ပါ။',show_alert=True);return
            parts=q.data.split(':');action=parts[1]
            clear_edit(uid);clear_draft(uid)
            if action=='home':home(uid,max(0,int(parts[2])))
            else:
                scope=read_scope(parts[2])
                if action=='scope':menu(uid,scope)
                elif action=='cats':categories(uid,scope,parts[3])
                elif action=='list':listing(uid,scope,parts[3],int(parts[4]),max(0,int(parts[5])))
                else:
                    ix=int(parts[3])
                    if not 0<=ix<len(KEYS):raise ValueError('Unknown entry')
                    key=KEYS[ix]
                    if action=='item':item(uid,scope,ix)
                    elif action=='preview':
                        text=preview(key,scope=scope)
                        bot.send_message(uid,text[:4000],parse_mode='HTML' if CATALOG[key].get('html') else None)
                    elif action=='reset':
                        save(scope,key,None,uid,reset=True);item(uid,scope,ix)
                    elif action=='edit':
                        with get_db_connection() as conn,conn.cursor() as cur:
                            cur.execute('''INSERT INTO owner_control_edit(owner_id,scope,key,expires_at) VALUES(%s,%s,%s,NOW()+INTERVAL '10 minutes')
                              ON CONFLICT(owner_id) DO UPDATE SET scope=EXCLUDED.scope,key=EXCLUDED.key,expires_at=EXCLUDED.expires_at''',(uid,scope,key))
                        kb=types.InlineKeyboardMarkup();kb.add(button('❌ Cancel',f'ctl:item:{scope}:{ix}'))
                        e=CATALOG[key];fields=' '.join('{'+f+'}' for f in e.get('fields',[]))
                        card(uid,'✏️ '+e['label'][:150]+'\n\n'+('စာအသစ်ကို ဒီမှာရေးပို့ပါ။' if e['kind']=='message' else ('Emoji တွေကို space ခြားပြီး ပို့ပါ။ Premium emoji ID ပါ သိမ်းမည်။' if key=='cfg.features.comfort.emojis' else 'ခေါ်နာမည် ပို့ပါ။' if key=='cfg.features.comfort.nickname' else 'Value အသစ်ပို့ပါ။ Number / true,false / JSON list သုံးပါ။'))+'\n\n'+fields[:800],kb)
            bot.answer_callback_query(q.id)
        except Exception as exc:
            print('Owner control:',type(exc).__name__)
            try:bot.answer_callback_query(q.id,str(exc)[:160] if isinstance(exc,ValueError) else 'ခေတ္တ အဆင်မပြေပါ။',show_alert=True)
            except Exception:pass

    @bot.message_handler(func=lambda m:bool(m.chat.type=='private' and m.text),content_types=['text'])
    def owner_control_input(msg):
        if not owner(msg) or msg.text.lstrip().startswith('/'):return ContinueHandling()
        uid=msg.from_user.id
        try:
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute('SELECT scope,key FROM owner_control_edit WHERE owner_id=%s AND expires_at>NOW()',(uid,))
                pending=cur.fetchone()
            if not pending:return ContinueHandling()
            scope,key=pending
            if key=='cfg.features.comfort.emojis':
                from core.comfort_content import encode_emojis
                value=encode_emojis(msg)
            elif key=='cfg.features.comfort.nickname':value=msg.text.strip()
            else:value=decode_value(key,msg.text)
            save(scope,key,value,uid)
            clear_edit(uid);item(uid,scope,KEYS.index(key))
        except ValueError as exc:bot.reply_to(msg,'⚠️ '+str(exc))
        except Exception as exc:
            print('Owner control input:',type(exc).__name__)
            bot.reply_to(msg,'⚠️ မသိမ်းနိုင်သေးပါ။ ထပ်စမ်းပါ။')
        return ContinueHandling()
