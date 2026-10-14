"""Shared durable RSS cache and opt-in Myanmar digest. Never copies full articles."""
import hashlib,html,json,logging,threading,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from telebot import types
from database.db import get_db_connection
from core.customization import message_text,setting_value,group_scope
from core import news_digest as engine
from data.news_sources import CATALOG

LOG=logging.getLogger(__name__);READY=False;MMT=ZoneInfo('Asia/Yangon')
DEFAULTS={'source_ids':list(CATALOG),'refresh_minutes':30,'max_age_hours':72,'items':5,'auto_enabled':False,'interval_minutes':180,'auto_min_sources':2}
MESSAGES={
 'heading':'📰 မြန်မာသတင်းစု\n{date}\n',
 'single':'သတင်းဌာနတစ်ခု၏ ဖော်ပြချက်',
 'multiple':'မီဒီယာအုပ်စု {count} ခုတွင် ဆင်တူဖော်ပြချက်ရှိသည်',
 'disclaimer':'ရင်းမြစ်ဖော်ပြချက်များကို စုထားခြင်းဖြစ်ပြီး သီးခြား fact-check အတည်ပြုချက်မဟုတ်ပါ။ မူရင်း link ကိုပါဖတ်ပါ။',
 'empty':'လက်ရှိရွေးထားသည့် source များတွင် သတ်မှတ်ချိန်အတွင်း သတင်းအသစ်မတွေ့ပါ။ /newssources ဖြင့် status ကြည့်နိုင်သည်။',
 'unavailable':'Source များကို ယာယီမရသေးပါ။ နောက်ဆုံး cache ရှိသလောက်သာဖတ်နိုင်သည်။ /newssources ဖြင့်စစ်ပါ။',
 'warming':'သတင်း cache ကို ပြင်ဆင်နေပါသည်။ ခဏနေရင် /news ပြန်သုံးပါ။',
 'group':'Auto news ကို Group ထဲတွင် /newson သို့မဟုတ် /newsoff ဖြင့်ထိန်းပါ။',
 'admin':'Group Admin သို့မဟုတ် Bot Owner သာ ပြင်နိုင်သည်။',
 'on':'✅ ဒီ Group အတွက် auto news ဖွင့်ပြီးပြီ။ Source များတွင်သတင်းအသစ်ရှိပြီး သတ်မှတ်ချက်ပြည့်မှ ပို့မည်။',
 'off':'⏸ ဒီ Group အတွက် auto news ပိတ်ပြီးပြီ။ /news နဲ့ ဆက်ဖတ်နိုင်သည်။',
 'status':'📰 News status\nAuto: {enabled}\nပို့နှုန်း: {minutes} မိနစ်\nသတင်းအသက်: {hours} နာရီအတွင်း\nAuto အနည်းဆုံး media group: {minimum}\nSource ရွေးထားမှု: {sources}',
 'error':'သတင်းစနစ်ကို ခေတ္တမသုံးနိုင်သေးပါ။ ပြန်စမ်းပါ။',
 'sources':'🗞️ News sources\n{sources}\n\n✅ = feed ဖတ်ရ၊ ⏳ = မစစ်ရသေး၊ ⚠️ = error / timestamp မရှိ။ Feed ဖတ်ရခြင်းနှင့် သတင်းအသစ်ရှိခြင်းမတူပါ။',
 'owner':'Bot Owner private chat တွင်သာ ပြင်နိုင်သည်။',
 'brief_usage':'/newsbrief ID ကိုယ်ပိုင်အကျဉ်းချုပ်\nမူရင်းကိုစစ်ပြီးမှ ပြင်ပါ။ Source link နှင့်ရက်စွဲကိုထိန်းထားသည်။',
 'brief_saved':'✅ ကိုယ်ပိုင်အကျဉ်းချုပ် သိမ်းပြီးပြီ။ ယခင်ပို့ထားသောသတင်းဖြစ်လျှင် auto ဖွင့်ထားသော Group များသို့ update အဖြစ်နောက်ပို့ချိန်တွင်ရောက်မည်။',
 'update':'🔄 ပြင်ဆင်/ဖြည့်စွက်ထားသော ဖော်ပြချက်',
 'brief_label':'✍️ Owner ရေးသားထားသော အကျဉ်းချုပ်',
 'brief_note':'အကျဉ်းချုပ်မရှိသေးသောသတင်းကို မူရင်းခေါင်းစဉ်အညွှန်းဖြင့်ဖော်ပြသည်။ အပြည့်အစုံကို ကူးမပို့ပါ။',
 'checked':'Feed နောက်ဆုံးစစ်ချိန်: {date}',
 'next':'နောက်သတင်းများ','previous':'ယခင်သတင်းများ'}

def text(key,**fields):return message_text('msg.features.news.'+key,MESSAGES[key],fields)
def cfg(key,cid=0):return setting_value('cfg.features.news.'+key,DEFAULTS[key],cid if cid<0 else 0)
def sources_for(cid):return [s for s in cfg('source_ids',cid) if s in CATALOG]
def stamp(value):return datetime.fromtimestamp(value,MMT).strftime('%d/%m/%Y %H:%M')+' MMT'

def initialize():
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('CREATE TABLE IF NOT EXISTS news_items(id TEXT PRIMARY KEY,data JSONB NOT NULL,published TIMESTAMPTZ NOT NULL)')
        cur.execute('CREATE INDEX IF NOT EXISTS news_publish_date ON news_items(published DESC)')
        cur.execute('CREATE TABLE IF NOT EXISTS news_health(source_id TEXT PRIMARY KEY,checked TIMESTAMPTZ,last_ok TIMESTAMPTZ,status TEXT NOT NULL,items INTEGER NOT NULL DEFAULT 0)')
        cur.execute('CREATE TABLE IF NOT EXISTS news_groups(chat_id BIGINT PRIMARY KEY,enabled BOOLEAN, next_due TIMESTAMPTZ, retry_after TIMESTAMPTZ)')
        cur.execute('CREATE TABLE IF NOT EXISTS news_jobs(key TEXT PRIMARY KEY,next_run TIMESTAMPTZ NOT NULL)')
        cur.execute('CREATE TABLE IF NOT EXISTS news_sent(chat_id BIGINT NOT NULL,item_id TEXT NOT NULL,revision TEXT NOT NULL, sent_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(chat_id,item_id))')

def ingest(source,now):
    sid=source['id']
    try:items,missing=engine.fetch(source,now);status='ok' if not missing else 'missing-date:'+str(missing)
    except Exception as exc:items=[];status=type(exc).__name__
    with get_db_connection() as con,con.cursor() as cur:
        for item in items:
            cur.execute('SELECT data FROM news_items WHERE id=%s',(item['key'],));old=cur.fetchone()
            if old and old[0].get('brief') and old[0]['title']==item['title']:
                item['brief']=old[0]['brief'];item['revision']=old[0]['revision']
            cur.execute('INSERT INTO news_items VALUES(%s,%s::jsonb,%s) ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data,published=EXCLUDED.published',(item['key'],json.dumps(item,ensure_ascii=False),datetime.fromtimestamp(item['published'],timezone.utc)))
        success=status=='ok' or status.startswith('missing-date:')
        cur.execute('INSERT INTO news_health VALUES(%s,NOW(),%s,%s,%s) ON CONFLICT(source_id) DO UPDATE SET checked=NOW(),last_ok=COALESCE(EXCLUDED.last_ok,news_health.last_ok),status=EXCLUDED.status,items=EXCLUDED.items',(sid,datetime.now(timezone.utc) if success else None,status,len(items)))
    return len(items),status

def refresh():
    now=time.time()
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute("INSERT INTO news_jobs VALUES('fetch',NOW()+%s*INTERVAL '1 minute') ON CONFLICT(key) DO UPDATE SET next_run=EXCLUDED.next_run WHERE news_jobs.next_run<=NOW() RETURNING key",(cfg('refresh_minutes'),))
        if not cur.fetchone():return
        cur.execute('SELECT source_id,checked FROM news_health');checked={s:d.timestamp() for s,d in cur.fetchall() if d}
    due=[CATALOG[sid] for sid in sources_for(0) if now-checked.get(sid,0)>=cfg('refresh_minutes')*60]
    # One bounded worker pool is shared by all groups. No HTTP in chat handlers.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(ingest,s,now) for s in due]
        for future in as_completed(futures):
            try:future.result()
            except Exception:LOG.exception('News cache update failed')
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute("DELETE FROM news_items WHERE published < NOW()-INTERVAL '30 days'")
        cur.execute("DELETE FROM news_sent WHERE sent_at < NOW()-INTERVAL '35 days'")

def load(cid):
    selected=set(sources_for(cid));now=time.time()
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('SELECT data FROM news_items WHERE published>=%s ORDER BY published DESC LIMIT 250',(datetime.fromtimestamp(now-cfg('max_age_hours',cid)*3600,timezone.utc),));rows=cur.fetchall()
        cur.execute('SELECT source_id,status,checked FROM news_health');health=cur.fetchall()
    items=[r[0] for r in rows if r[0]['source'] in selected and r[0]['published']<=now+300]
    return engine.clusters(items),[(sid,status,checked) for sid,status,checked in health if sid in selected]

def enabled(cid,row=None):return row if row is not None else cfg('auto_enabled',cid)
def render(cid,groups,health,offset=0):
    limit=cfg('items',cid);shown=groups[offset:offset+limit]
    if not shown:
        good=any(status=='ok' or status.startswith('missing-date:') for _,status,_ in health)
        return (text('empty') if good else text('unavailable') if health else text('warming')),[],0
    parts=[html.escape(text('heading',date=stamp(time.time())))];sent=[];page_count=0
    newest=max((d.timestamp() for _,_,d in health if d),default=0)
    footer=([html.escape(text('checked',date=stamp(newest)))] if newest else [])+[html.escape(text('brief_note')),html.escape(text('disclaimer'))]
    for n,group in enumerate(shown,offset+1):
        lead=next((a for a in group if a.get('brief')),group[0]);count=len(engine.families(group))
        label=text('multiple',count=count) if count>1 else text('single')
        # A new title is an attributed source claim, not an invented article summary.
        title=engine.headline(lead)[:500]
        links=[];seen=set()
        for item in group:
            if item['family'] in seen:continue
            seen.add(item['family'])
            links.append('<a href="'+html.escape(item['url'],quote=True)+'">'+html.escape(item['name'])+'</a>')
        block=f'<b>{n}. {html.escape(title)}</b>\n{html.escape(label)}\n'+(' · '.join(links[:4]))+'\n'+html.escape(stamp(lead['published']))+' · <code>'+lead['key']+'</code>\n'
        if lead.get('brief'):block+=html.escape(text('brief_label'))+'\n'
        elif lead.get('correction'):block+=html.escape(text('update'))+'\n'
        if len('\n'.join(parts+[block]+footer))>3900:break
        parts.append(block);sent.extend(group);page_count+=1
    parts.extend(footer)
    return '\n'.join(parts),sent,page_count

def keyboard(offset,total,count):
    count=max(1,count)
    k=types.InlineKeyboardMarkup();buttons=[]
    if offset:buttons.append(types.InlineKeyboardButton(text('previous')[:50],callback_data='news:'+str(max(0,offset-count))))
    if offset+count<total:buttons.append(types.InlineKeyboardButton(text('next')[:50],callback_data='news:'+str(offset+count)))
    if buttons:k.row(*buttons)
    return k

def auto(bot):
    from features.owner_operations import feature_allowed
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('SELECT g.chat_id,n.enabled,n.next_due,n.retry_after FROM owner_groups g LEFT JOIN news_groups n ON n.chat_id=g.chat_id WHERE g.active');targets=cur.fetchall()
    now=datetime.now(timezone.utc)
    for cid,explicit,due,retry in targets:
        if not enabled(cid,explicit) or due and due>now or retry and retry>now or not feature_allowed('enabled.features.news.news_command',cid) or not setting_value('enabled.features.news.news_command',True,scope=cid):continue
        try:
            with group_scope(cid):
                with get_db_connection() as con,con.cursor() as cur:
                    cur.execute("INSERT INTO news_groups(chat_id,next_due) VALUES(%s,NOW()+%s*INTERVAL '1 minute') ON CONFLICT(chat_id) DO UPDATE SET next_due=EXCLUDED.next_due WHERE (news_groups.next_due IS NULL OR news_groups.next_due<=NOW()) AND (news_groups.retry_after IS NULL OR news_groups.retry_after<=NOW()) RETURNING chat_id",(cid,cfg('interval_minutes',cid)))
                    if not cur.fetchone():continue
                groups,health=load(cid)
                with get_db_connection() as con,con.cursor() as cur:
                    cur.execute('SELECT item_id,revision FROM news_sent WHERE chat_id=%s',(cid,));sent=dict(cur.fetchall())
                eligible=[]
                for group in groups:
                    if len(engine.families(group))<cfg('auto_min_sources',cid):continue
                    if any(a['key'] in sent for a in group):
                        # Only explicitly edited briefs / publisher corrections trigger updates.
                        if not any((a.get('brief') or a['correction']) and sent.get(a['key'])!=a['revision'] for a in group):continue
                    eligible.append(group)
                body,items,_=render(cid,eligible,health)
                if items:
                    bot.send_message(cid,body,parse_mode='HTML',disable_web_page_preview=True)
                    with get_db_connection() as con,con.cursor() as cur:
                        for item in items:cur.execute('INSERT INTO news_sent(chat_id,item_id,revision) VALUES(%s,%s,%s) ON CONFLICT(chat_id,item_id) DO UPDATE SET revision=EXCLUDED.revision,sent_at=NOW()',(cid,item['key'],item['revision']))
                with get_db_connection() as con,con.cursor() as cur:
                    cur.execute("INSERT INTO news_groups(chat_id,next_due) VALUES(%s,NOW()+%s*INTERVAL '1 minute') ON CONFLICT(chat_id) DO UPDATE SET next_due=EXCLUDED.next_due",(cid,cfg('interval_minutes',cid)))
        except Exception:
            LOG.exception('News delivery failed')
            with get_db_connection() as con,con.cursor() as cur:
                cur.execute("INSERT INTO news_groups(chat_id,retry_after) VALUES(%s,NOW()+INTERVAL '10 minutes') ON CONFLICT(chat_id) DO UPDATE SET retry_after=EXCLUDED.retry_after,next_due=EXCLUDED.retry_after",(cid,))

def register(bot):
    global READY
    try:initialize();READY=True
    except Exception:LOG.warning('News database unavailable')
    def manage(m):
        from features.owner_operations import is_owner
        return is_owner(m.from_user.id) or bot.get_chat_member(m.chat.id,m.from_user.id).status in ('creator','administrator')
    @bot.message_handler(commands=['news','သတင်း'])
    def news_command(m):
        try:
            groups,health=load(m.chat.id);body,items,count=render(m.chat.id,groups,health)
            bot.send_message(m.chat.id,body,parse_mode='HTML',disable_web_page_preview=True,reply_markup=keyboard(0,len(groups),count))
        except Exception:bot.reply_to(m,text('error'))
    @bot.message_handler(commands=['newssources'])
    def news_sources(m):
        try:
            with get_db_connection() as con,con.cursor() as cur:cur.execute('SELECT source_id,status,checked,items FROM news_health');health={sid:(status,checked,count) for sid,status,checked,count in cur.fetchall()}
            rows=[]
            for sid in sources_for(m.chat.id):
                status,checked,count=health.get(sid,('pending',None,0));symbol='✅' if status=='ok' else '⏳' if status=='pending' else '⚠️'
                rows.append(f'{symbol} {CATALOG[sid]["name"]} [{sid}]\n{status} · {count} news · '+(stamp(checked.timestamp()) if checked else '—'))
            value=text('sources',sources='\n'.join(rows))
            # Split only at source boundaries, keeping each Telegram message bounded.
            if len(value)<3900:bot.send_message(m.chat.id,value,parse_mode=None)
            else:
                for i in range(0,len(rows),12):bot.send_message(m.chat.id,text('sources',sources='\n'.join(rows[i:i+12]))[:3900],parse_mode=None)
        except Exception:bot.reply_to(m,text('error'))
    @bot.message_handler(commands=['newson','newsoff','newsstatus'])
    def news_control(m):
        if m.chat.type not in ('group','supergroup'):bot.reply_to(m,text('group'));return
        try:
            command=m.text.split()[0].split('@')[0].lstrip('/')
            if command=='newsstatus':
                with get_db_connection() as con,con.cursor() as cur:cur.execute('SELECT enabled FROM news_groups WHERE chat_id=%s',(m.chat.id,));row=cur.fetchone()
                bot.reply_to(m,text('status',enabled=enabled(m.chat.id,row[0] if row else None),minutes=cfg('interval_minutes',m.chat.id),hours=cfg('max_age_hours',m.chat.id),minimum=cfg('auto_min_sources',m.chat.id),sources=len(sources_for(m.chat.id))));return
            if not manage(m):bot.reply_to(m,text('admin'));return
            with get_db_connection() as con,con.cursor() as cur:cur.execute('INSERT INTO news_groups(chat_id,enabled,next_due,retry_after) VALUES(%s,%s,NOW(),NULL) ON CONFLICT(chat_id) DO UPDATE SET enabled=EXCLUDED.enabled,next_due=NOW(),retry_after=NULL',(m.chat.id,command=='newson'))
            bot.reply_to(m,text('on' if command=='newson' else 'off'))
        except Exception:bot.reply_to(m,text('error'))
    @bot.message_handler(commands=['newsbrief'])
    def news_brief(m):
        from features.owner_operations import is_owner
        if m.chat.type!='private' or not is_owner(m.from_user.id):bot.reply_to(m,text('owner'));return
        parts=m.text.split(maxsplit=2)
        if len(parts)!=3 or len(parts[2])>500:bot.reply_to(m,text('brief_usage'));return
        try:
            with get_db_connection() as con,con.cursor() as cur:
                cur.execute('SELECT data FROM news_items WHERE id=%s FOR UPDATE',(parts[1],));row=cur.fetchone()
                if not row:bot.reply_to(m,text('brief_usage'));return
                item=row[0];item['brief']=parts[2];item['revision']=hashlib.sha256(parts[2].encode()).hexdigest()[:16]
                cur.execute('UPDATE news_items SET data=%s::jsonb WHERE id=%s',(json.dumps(item,ensure_ascii=False),parts[1]))
            bot.reply_to(m,text('brief_saved'))
        except Exception:bot.reply_to(m,text('error'))
    @bot.callback_query_handler(func=lambda c:bool(c.data and c.data.startswith('news:')))
    def news_page(c):
        try:bot.answer_callback_query(c.id)
        except Exception:pass
        if not c.message:return
        try:
            offset=int(c.data.split(':')[1]);cid=c.message.chat.id
            from features.owner_operations import feature_allowed
            if not feature_allowed('enabled.features.news.news_command',cid) or not setting_value('enabled.features.news.news_command',True,scope=cid if cid<0 else 0):return
            if not 0<=offset<=250:return
            groups,health=load(cid);body,_,count=render(cid,groups,health,offset)
            bot.edit_message_text(body,cid,c.message.message_id,parse_mode='HTML',disable_web_page_preview=True,reply_markup=keyboard(offset,len(groups),count))
        except Exception:LOG.debug('News page unavailable')
    if READY:
        def loop():
            while True:
                try:refresh();auto(bot)
                except Exception:LOG.exception('News worker failed')
                time.sleep(60)
        threading.Thread(target=loop,name='myanmar-news',daemon=True).start()
