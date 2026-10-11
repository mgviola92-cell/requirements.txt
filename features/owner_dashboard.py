"""Owner-only Flask dashboard. Locked until Render env secrets are configured."""
import os, time, secrets, threading, html
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, render_template_string, abort
from werkzeug.security import check_password_hash
from database.db import get_db_connection
from telebot.handler_backends import ContinueHandling
from telebot import types

dashboard = Blueprint("owner_dashboard", __name__, url_prefix="/owner")
BOT = None
DEFAULT_GROUP_WELCOME = (
    "🤖 Group ထဲကို ကြိုဆိုပါတယ်!\n\n"
    "Bot ကို Add လုပ်ပေးတဲ့အတွက် ကျေးဇူးတင်ပါတယ်။ 🎉\n\n"
    "🛡️ Admin များအတွက်: Bot ကို Admin ပေးပြီး Delete Messages, Pin Messages, "
    "Restrict Members permissions တွေ ဖွင့်ပေးပါ။\n\n"
    "📋 /cmd — Commands နဲ့ Games\n"
    "📣 /အက်မင်ခေါ် — Admin တွေကို ခေါ်ရန်\n"
)
_job_lock = threading.Lock()
_running = False
_owner_drafts = {}
_owner_draft_lock = threading.RLock()
_owner_card_ids = {}

def _ready():
    return bool(os.getenv("OWNER_PASSWORD_HASH") and os.getenv("DASHBOARD_SECRET_KEY"))

def _init_db():
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS owner_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur.execute("""CREATE TABLE IF NOT EXISTS owner_groups (
          chat_id BIGINT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
          active BOOLEAN NOT NULL DEFAULT TRUE, broadcast_opt_out BOOLEAN NOT NULL DEFAULT FALSE,
          last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS owner_source_messages (id BIGSERIAL PRIMARY KEY, chat_id BIGINT NOT NULL, message_id BIGINT NOT NULL, preview TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS owner_broadcasts (
          id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          message TEXT NOT NULL, total INT NOT NULL DEFAULT 0,
          sent INT NOT NULL DEFAULT 0, failed INT NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'queued'
        )""")

def record_group(chat, active=True):
    if getattr(chat,"type",None) not in ("group","supergroup"): return
    try:
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO owner_groups(chat_id,title,active,last_seen)
             VALUES(%s,%s,%s,NOW()) ON CONFLICT(chat_id) DO UPDATE SET
             title=EXCLUDED.title,active=EXCLUDED.active,last_seen=NOW()""",
             (chat.id,(getattr(chat,"title","") or "")[:160],active))
    except Exception as exc:
        print("Owner group tracking failed:",type(exc).__name__)

def _authenticated():
    return _ready() and session.get("owner") is True

def _protect(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if not _ready(): return ("Dashboard is locked. Configure OWNER_PASSWORD_HASH and DASHBOARD_SECRET_KEY on Render.",503)
        if not _authenticated(): return redirect(url_for("owner_dashboard.login"))
        return fn(*a,**kw)
    return inner

def _csrf():
    if "csrf" not in session: session["csrf"]=secrets.token_urlsafe(32)
    return session["csrf"]

def _verify_csrf():
    if not secrets.compare_digest(str(request.form.get("csrf","")),_csrf()): abort(403)

CSS="""<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;background:#0e1421;color:#f2f5fc;font:15px system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:auto;padding:26px 16px}h1{font-size:26px;margin:6px 0 24px}h2{font-size:19px;margin:0 0 14px}
a{color:#88c5ff}nav{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:26px}
.panel{background:#192234;border:1px solid #33415d;border-radius:16px;padding:20px;margin:14px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.big{font-size:30px;font-weight:750}small,.muted{color:#b6c2d6}
input,textarea{width:100%;padding:12px;background:#101a2a;color:#fff;border:1px solid #50637f;border-radius:9px;font:inherit;margin:9px 0}
textarea{min-height:130px}button{background:#397fe8;color:white;border:0;border-radius:9px;padding:12px 18px;font-weight:700;cursor:pointer}
table{width:100%;border-collapse:collapse}th,td{padding:11px 6px;text-align:left;border-bottom:1px solid #33415d;overflow-wrap:anywhere}
.wrap{overflow-x:auto}.error{color:#ffadad}.ok{color:#9be4ac}
</style>"""

@dashboard.route("/login",methods=["GET","POST"])
def login():
    if not _ready():return ("Dashboard locked: configure owner credentials in Render first.",503)
    error=""
    if request.method=="POST":
        _verify_csrf()
        # Single-owner login; generic error avoids revealing account existence.
        username=request.form.get("username","")
        password=request.form.get("password","")
        valid_username=secrets.compare_digest(username,os.getenv("OWNER_USERNAME","owner"))
        valid_password=False
        try: valid_password=check_password_hash(os.getenv("OWNER_PASSWORD_HASH",""),password)
        except (ValueError,TypeError):pass
        if valid_username and valid_password:
            session.clear();session["owner"]=True;session.permanent=True
            _csrf()
            return redirect(url_for("owner_dashboard.index"))
        time.sleep(1.5)
        error="Username or password incorrect."
    return render_template_string(CSS+"""<main style="max-width:450px"><div class="panel">
    <h1>🔐 Owner Login</h1><p class="error">{{error}}</p>
    <form method="post"><input type="hidden" name="csrf" value="{{csrf}}">
    <label>Username</label><input name="username" required autocomplete="username">
    <label>Password</label><input name="password" type="password" required autocomplete="current-password">
    <button>Sign in</button></form></div></main>""",csrf=_csrf(),error=error)

@dashboard.route("/logout",methods=["POST"])
@_protect
def logout():
    _verify_csrf();session.clear();return redirect(url_for("owner_dashboard.login"))

SHELL=CSS+"""<main><nav><strong>👑 BOT CONTROL</strong>
<a href="{{url_for('owner_dashboard.index')}}">Dashboard</a>
<a href="{{url_for('owner_dashboard.broadcast')}}">Broadcast</a>
<a href="{{url_for('owner_dashboard.edit_welcome')}}">✏️ Welcome Editor</a>
<form action="{{url_for('owner_dashboard.logout')}}" method="post">
<input type="hidden" name="csrf" value="{{csrf}}"><button style="padding:5px 12px">Logout</button></form>
</nav>{{ body|safe }}</main>"""

def _shell(body):
    return render_template_string(SHELL,csrf=_csrf(),body=body)

@dashboard.route("/")
@_protect
def index():
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT COUNT(*),COUNT(*) FILTER(WHERE active),COUNT(*) FILTER(WHERE active AND NOT broadcast_opt_out) FROM owner_groups")
        total,active,subscribed=cur.fetchone()
        cur.execute("SELECT title,chat_id,active,broadcast_opt_out,last_seen FROM owner_groups ORDER BY last_seen DESC LIMIT 200")
        groups=cur.fetchall()
        cur.execute("SELECT id,created_at,total,sent,failed,status FROM owner_broadcasts ORDER BY id DESC LIMIT 15")
        history=cur.fetchall()
    body="<h1>Owner Dashboard</h1><div class='grid'>"
    for name,n in [("Known groups",total),("Active groups",active),("Broadcast enabled",subscribed)]:
        body+=f"<div class='panel'><small>{name}</small><div class='big'>{n}</div></div>"
    body+="</div><div class='panel'><h2>Group Welcome Message</h2><p>Customize the message posted when the bot joins a new group.</p><a href='/owner/welcome'>✏️ Edit Welcome Message</a></div><div class='panel'><h2>Tracked Groups</h2><p class='muted'>Only groups discovered after tracking starts; total is not a historical Telegram-wide count.</p><div class='wrap'><table><tr><th>Group</th><th>Chat ID</th><th>Status</th><th>Last seen UTC</th></tr>"
    for title,gid,is_active,optout,last in groups:
        body+=f"<tr><td>{html.escape(title or 'Unnamed')}</td><td>{gid}</td><td>{'Active' if is_active else 'Left'}{' · Opted out' if optout else ''}</td><td>{html.escape(str(last)[:19])}</td></tr>"
    body+="</table></div></div><div class='panel'><h2>Broadcast History</h2><div class='wrap'><table><tr><th>ID</th><th>Sent</th><th>Failed</th><th>Total</th><th>Status</th></tr>"
    for rid,created,all_count,sent,failed,status in history:
        body+=f"<tr><td>{rid}</td><td>{sent}</td><td>{failed}</td><td>{all_count}</td><td>{html.escape(status)}</td></tr>"
    body+="</table></div></div>"
    return _shell(body)

@dashboard.route("/welcome",methods=["GET","POST"])
@_protect
def edit_welcome():
    notice=""
    if request.method=="POST":
        _verify_csrf()
        value=request.form.get("welcome","")
        if not (1<=len(value)<=3500):return ("Welcome text must be 1–3500 characters",400)
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute("INSERT INTO owner_settings(key,value) VALUES('group_welcome',%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",(value,))
        notice="✅ Welcome text saved. Only future group joins will use it."
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT value FROM owner_settings WHERE key='group_welcome'")
        row=cur.fetchone()
    value=row[0] if row else DEFAULT_GROUP_WELCOME
    body=("<h1>Group Welcome Message</h1><p class='muted'>Changes apply only when the bot joins a group. "
          "Text and line breaks are preserved. HTML is not interpreted.</p>"
          f"<p class='ok'>{html.escape(notice)}</p>"
          "<div class='panel'><form method='post'>"
          f"<input type='hidden' name='csrf' value='{html.escape(_csrf())}'>"
          f"<textarea name='welcome' maxlength='3500' required style='min-height:300px'>{html.escape(value)}</textarea>"
          "<button>Save Welcome</button></form></div>")
    return _shell(body)

@dashboard.route("/saved",methods=["GET"])
@_protect
def saved_messages():
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT id,preview,created_at FROM owner_source_messages ORDER BY id DESC LIMIT 100")
        entries=cur.fetchall()
    body="<h1>Saved Telegram Messages</h1><p>Latest 100 saved originals. Removing here does not delete the original Telegram message.</p><div class='panel'><table><tr><th>Message</th><th>Saved</th><th>Action</th></tr>"
    for mid,preview,created in entries:
        body+=f"<tr><td>#{mid}: {html.escape(preview[:100])}</td><td>{html.escape(str(created)[:16])}</td><td><form method='post' action='/owner/saved/delete'><input type='hidden' name='csrf' value='{html.escape(_csrf())}'><input type='hidden' name='id' value='{mid}'><button type='submit'>Remove</button></form></td></tr>"
    return _shell(body+"</table></div>")

@dashboard.route("/saved/delete",methods=["POST"])
@_protect
def delete_saved_message():
    _verify_csrf()
    try: mid=int(request.form.get("id",""))
    except ValueError: abort(400)
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute("DELETE FROM owner_source_messages WHERE id=%s",(mid,))
    return redirect(url_for("owner_dashboard.saved_messages"))

@dashboard.route("/broadcast",methods=["GET","POST"])
@_protect
def broadcast():
    global _running
    if request.method=="POST":
        _verify_csrf()
        message=(request.form.get("message") or "").strip()
        if len(message)>1500:return ("Message too long",400)
        source=request.form.get("source","text")
        if source=="text" and not message:return ("Message required",400)
        if request.form.get("confirm")!="yes":return ("Confirmation required",400)
        source_chat=source_msg=None
        if source!="text":
            try:source_id=int(source)
            except ValueError:return ("Invalid Telegram source",400)
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute("SELECT chat_id,message_id FROM owner_source_messages WHERE id=%s",(source_id,))
                row=cur.fetchone()
                if not row:return ("Telegram source not found",400)
                source_chat,source_msg=row
        target=request.form.get("target","all")
        if target!="all":
            try:target=int(target)
            except ValueError:return ("Invalid target",400)
        if target!="all":
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute("SELECT 1 FROM owner_groups WHERE chat_id=%s AND active=TRUE AND broadcast_opt_out=FALSE",(target,))
                if not cur.fetchone():return ("Destination not available",400)
        with _job_lock:
            if _running:return ("A broadcast is already in progress",409)
            _running=True
        try:
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute("SELECT chat_id FROM owner_groups WHERE active=TRUE AND broadcast_opt_out=FALSE ORDER BY chat_id")
                ids=[x[0] for x in cur.fetchall()]
                if target!="all":
                    if target not in ids:raise RuntimeError("Destination no longer available")
                    ids=[target]
                cur.execute("INSERT INTO owner_broadcasts(message,total,status) VALUES(%s,%s,'running') RETURNING id",
                            (message,len(ids)))
                jobid=cur.fetchone()[0]
            threading.Thread(target=_send_broadcast,args=(jobid,message,ids,source_chat,source_msg),daemon=True).start()
        except Exception:
            with _job_lock:_running=False
            raise
        return redirect(url_for("owner_dashboard.index"))
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT chat_id,title FROM owner_groups WHERE active=TRUE AND broadcast_opt_out=FALSE ORDER BY title")
        groups=cur.fetchall()
        count=len(groups)
        cur.execute("SELECT id,preview FROM owner_source_messages ORDER BY id DESC LIMIT 5")
        originals=cur.fetchall()
    source_options="<option value='text'>Write text in website</option>"
    for sid,preview in originals:
        source_options+=f"<option value='{sid}'>Telegram Original #{sid}: {html.escape(preview[:70])}</option>"
    choices="<option value='all'>All groups</option>"
    for gid,title in groups:
        choices+=f"<option value='{gid}'>{html.escape(title or str(gid))}</option>"
    body=f"""<h1>📢 Broadcast Center</h1><p><a href="/owner/saved">Manage saved messages</a></p><div class='panel'><h2>Send announcement to {count} opted-in groups</h2>
<p class='muted'>Group admins can opt out using /broadcastoff in their group. Broadcasts are plain text and rate limited.</p>
<form method="post"><input type="hidden" name="csrf" value="{html.escape(_csrf())}">
<label>Message Source</label><select name="source" style="width:100%;padding:12px;background:#101a2a;color:white;border:1px solid #50637f;border-radius:9px">{source_options}</select><p class="muted">For original formatting and Premium emoji, send the message to the bot in Telegram private chat first. Configure OWNER_TELEGRAM_ID on Render.</p><label>Destination</label><select name="target" style="width:100%;padding:12px;background:#101a2a;color:white;border:1px solid #50637f;border-radius:9px">{choices}</select><textarea name="message" maxlength="1500" placeholder="Write the announcement..."></textarea>
<label><input style="width:auto" type="checkbox" name="confirm" value="yes" required> I confirm sending to selected destination.</label>
<p><button>Send to groups</button></p></form></div>"""
    return _shell(body)

def _send_broadcast(jobid,message,ids,source_chat=None,source_msg=None):
    global _running
    sent=failed=0
    try:
        for gid in ids:
            try:
                if source_chat is not None:
                    BOT.copy_message(gid,source_chat,source_msg)
                else:
                    BOT.send_message(gid,message)
                sent+=1
            except Exception as exc:
                failed+=1
                if "chat not found" in str(exc).lower() or "bot was kicked" in str(exc).lower():
                    with get_db_connection() as conn,conn.cursor() as cur:
                        cur.execute("UPDATE owner_groups SET active=FALSE WHERE chat_id=%s",(gid,))
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute("UPDATE owner_broadcasts SET sent=%s,failed=%s WHERE id=%s",(sent,failed,jobid))
            time.sleep(0.12)
    finally:
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute("UPDATE owner_broadcasts SET status=%s WHERE id=%s",("completed",jobid))
        with _job_lock:_running=False

def register_owner_dashboard(app,bot):
    global BOT
    BOT=bot
    app.secret_key=os.getenv("DASHBOARD_SECRET_KEY") or secrets.token_urlsafe(32)
    app.config.update(SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=3600)
    app.register_blueprint(dashboard)
    _init_db()
    observed={}
    observed_lock=threading.Lock()
    @bot.message_handler(func=lambda m:m.chat.type in ("group","supergroup"),content_types=["text"])
    def observe_group(msg):
        now=time.monotonic()
        with observed_lock:
            if now-observed.get(msg.chat.id,-1000000)<21600:
                return ContinueHandling()
            observed[msg.chat.id]=now
        record_group(msg.chat)
        return ContinueHandling()
    @bot.my_chat_member_handler(func=lambda m:True)
    def owner_membership(m):
        if m.chat.type not in ("group","supergroup"):
            return
        old_status=getattr(m.old_chat_member,"status","")
        new_status=getattr(m.new_chat_member,"status","")
        old_joined=old_status not in ("left","kicked")
        new_joined=new_status not in ("left","kicked")
        record_group(m.chat,active=new_joined)
        if not old_joined and new_joined:
            try:
                with get_db_connection() as conn,conn.cursor() as cur:
                    cur.execute("SELECT value FROM owner_settings WHERE key='group_welcome'")
                    row=cur.fetchone()
                bot.send_message(m.chat.id,row[0] if row else DEFAULT_GROUP_WELCOME)
            except Exception as exc:
                print("Bot group welcome failed:",type(exc).__name__)
    def is_owner(msg):
        return (msg.chat.type=="private" and msg.from_user is not None and
                os.getenv("OWNER_TELEGRAM_ID","").strip()==str(msg.from_user.id))

    def owner_replace_card(uid,chat_id,text,keyboard=None):
        """Send the next card at the bottom, then delete only our previous card."""
        new_card=bot.send_message(chat_id,text,reply_markup=keyboard)
        with _owner_draft_lock:
            old_id=_owner_card_ids.get(uid)
            _owner_card_ids[uid]=new_card.message_id
        if old_id and old_id!=new_card.message_id:
            try:bot.delete_message(chat_id,old_id)
            except Exception:
                try:bot.edit_message_reply_markup(chat_id,old_id,reply_markup=None)
                except Exception:pass
        return new_card
    def owner_buttons():
        kb=types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("📢 Broadcast",callback_data="own:broadcast"),
               types.InlineKeyboardButton("👥 Groups",callback_data="own:groups"))
        kb.add(types.InlineKeyboardButton("📜 History",callback_data="own:history"),
               types.InlineKeyboardButton("❌ Cancel",callback_data="own:cancel"))
        return kb

    def owner_back_button():
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel",callback_data="own:menu"))
        return kb

    def owner_home(uid,chat_id):
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute("SELECT COUNT(*),COUNT(*) FILTER(WHERE active),COUNT(*) FILTER(WHERE active AND NOT broadcast_opt_out) FROM owner_groups")
            total,active,enabled=cur.fetchone()
        owner_replace_card(uid,chat_id,f"👑 OWNER PANEL\n\n👥 Groups: {total}\n🟢 Active: {active}\n📢 Broadcast enabled: {enabled}\n\nအောက်က Menu ကို ရွေးပါ။",owner_buttons())
    @bot.message_handler(commands=["owner"])
    def telegram_owner_panel(msg):
        if not is_owner(msg):return ContinueHandling()
        owner_home(msg.from_user.id,msg.chat.id)
        return ContinueHandling()

    @bot.callback_query_handler(func=lambda q:bool(q.data and q.data.startswith("own:")))
    def owner_actions(q):
        if not q.from_user or str(q.from_user.id)!=os.getenv("OWNER_TELEGRAM_ID","").strip() or q.message.chat.type!="private":
            bot.answer_callback_query(q.id,"Owner သာ အသုံးပြုနိုင်ပါတယ်။",show_alert=True)
            return
        action=q.data.split(":",1)[1]
        uid=q.from_user.id
        try:
            if action=="menu":
                with _owner_draft_lock:_owner_drafts.pop(uid,None)
                owner_home(uid,q.message.chat.id)
            elif action=="broadcast":
                with _owner_draft_lock:_owner_drafts[uid]={"phase":"waiting","expires":time.monotonic()+600}
                owner_replace_card(uid,q.message.chat.id,"📢 ပို့ချင်တဲ့စာကို Forward လုပ်ပါ။\n\nပြီးရင် အဲဒီစာကို Reply နှိပ်ပြီး /ownersend ပို့ပါ။\n/ownercancel နဲ့ ရပ်နိုင်ပါတယ်။",owner_back_button())
            elif action=="groups":
                with get_db_connection() as conn,conn.cursor() as cur:
                    cur.execute("SELECT title,active,broadcast_opt_out FROM owner_groups ORDER BY last_seen DESC LIMIT 30")
                    groups=cur.fetchall()
                lines=[f"{i}. {title or 'Unnamed'} — {'🟢' if active else '⚪'}{' 🔕' if muted else ''}" for i,(title,active,muted) in enumerate(groups,1)]
                owner_replace_card(uid,q.message.chat.id,"👥 Group List\n\n"+("\n".join(lines) if lines else "Group မရှိသေးပါ။"),owner_back_button())
            elif action=="history":
                with get_db_connection() as conn,conn.cursor() as cur:
                    cur.execute("SELECT id,total,sent,failed,status FROM owner_broadcasts ORDER BY id DESC LIMIT 8")
                    jobs=cur.fetchall()
                lines=[f"#{i} · {sent}/{total} sent · {failed} failed · {status}" for i,total,sent,failed,status in jobs]
                owner_replace_card(uid,q.message.chat.id,"📜 Broadcast History\n\n"+("\n".join(lines) if lines else "မရှိသေးပါ။"),owner_back_button())
            elif action=="cancel":
                with _owner_draft_lock:_owner_drafts.pop(uid,None)
                owner_home(uid,q.message.chat.id)
            elif action.startswith("to:"):
                target=action[3:]
                with _owner_draft_lock:
                    draft=_owner_drafts.get(uid)
                    if not draft or draft.get("phase")!="ready" or time.monotonic()>draft["expires"]:
                        bot.answer_callback_query(q.id,"Message သက်တမ်းကုန်သွားပါပြီ။",show_alert=True);return
                    draft["target"]=target
                kb=types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("✅ Confirm Send",callback_data="own:send"),
                       types.InlineKeyboardButton("❌ Cancel",callback_data="own:cancel"))
                owner_replace_card(uid,q.message.chat.id,"📢 ဒီ Message ကို "+("Group အားလုံး" if target=="all" else "ရွေးထားတဲ့ Group")+" ဆီ ပို့မှာလား။",kb)
            elif action=="send":
                global _running
                with _owner_draft_lock:
                    draft=_owner_drafts.get(uid)
                    if not draft or draft.get("phase")!="ready" or "target" not in draft or time.monotonic()>draft["expires"]:
                        bot.answer_callback_query(q.id,"Message သက်တမ်းကုန်သွားပါပြီ။",show_alert=True);return
                    with _job_lock:
                        if _running:
                            bot.answer_callback_query(q.id,"Broadcast တစ်ခု ပို့နေပါတယ်။",show_alert=True);return
                        _running=True
                    draft=_owner_drafts.pop(uid)
                try:
                    with get_db_connection() as conn,conn.cursor() as cur:
                        cur.execute("SELECT chat_id FROM owner_groups WHERE active AND NOT broadcast_opt_out ORDER BY chat_id")
                        ids=[r[0] for r in cur.fetchall()]
                        if draft["target"]!="all":ids=[i for i in ids if str(i)==draft["target"]]
                        if not ids:raise ValueError("No eligible groups")
                        cur.execute("INSERT INTO owner_broadcasts(message,total,status) VALUES(%s,%s,'running') RETURNING id",("[Telegram original]",len(ids)))
                        jobid=cur.fetchone()[0]
                    threading.Thread(target=_send_broadcast,args=(jobid,"",ids,draft["chat_id"],draft["message_id"]),daemon=True).start()
                    owner_replace_card(uid,q.message.chat.id,f"✅ Broadcast #{jobid} စတင်ပို့နေပြီ။ Group {len(ids)} ခု။",owner_back_button())
                except Exception as exc:
                    with _job_lock:_running=False
                    owner_replace_card(uid,q.message.chat.id,"⚠️ Broadcast စတင်မရပါ။ Eligible Group ရှိ/မရှိ စစ်ပါ။",owner_back_button())
            bot.answer_callback_query(q.id)
        except Exception as exc:
            print("Owner panel action:",type(exc).__name__)
            try:bot.answer_callback_query(q.id,"ခေတ္တ အဆင်မပြေပါ။",show_alert=True)
            except Exception:pass

    @bot.message_handler(commands=["ownercancel"])
    def owner_cancel(msg):
        if not is_owner(msg):return ContinueHandling()
        with _owner_draft_lock:_owner_drafts.pop(msg.from_user.id,None)
        bot.reply_to(msg,"❌ Cancelled.")
        return ContinueHandling()

    def offer_destinations(msg,source):
        with _owner_draft_lock:
            _owner_drafts[msg.from_user.id]={"phase":"ready","chat_id":source.chat.id,"message_id":source.message_id,"expires":time.monotonic()+600}
        kb=types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("📢 All Groups",callback_data="own:to:all"))
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute("SELECT chat_id,title FROM owner_groups WHERE active AND NOT broadcast_opt_out ORDER BY last_seen DESC LIMIT 20")
            groups=cur.fetchall()
        for gid,title in groups:
            kb.add(types.InlineKeyboardButton("👥 "+(title or str(gid))[:30],callback_data="own:to:"+str(gid)))
        kb.add(types.InlineKeyboardButton("❌ Cancel",callback_data="own:cancel"))
        owner_replace_card(msg.from_user.id,msg.chat.id,"✅ Original Message ရပြီ။ ပို့မယ့် Group ကို ရွေးပါ။",kb)

    @bot.message_handler(commands=["ownersend"])
    def owner_send_reply(msg):
        if not is_owner(msg):return ContinueHandling()
        if not msg.reply_to_message:
            bot.reply_to(msg,"Forward လုပ်ထားတဲ့စာကို Reply နှိပ်ပြီး /ownersend ပို့ပါ။")
            return ContinueHandling()
        try:offer_destinations(msg,msg.reply_to_message)
        except Exception as exc:
            print("Owner send:",type(exc).__name__)
            bot.reply_to(msg,"⚠️ Group ရွေးချယ်မှုဖွင့်မရသေးပါ။")
        return ContinueHandling()

    @bot.message_handler(commands=["ownersave"])
    def owner_save_reply(msg):
        if msg.chat.type!="private":return ContinueHandling()
        if str(msg.from_user.id)!=os.getenv("OWNER_TELEGRAM_ID","").strip():
            bot.reply_to(msg,"🔒 Owner သာ သုံးနိုင်ပါတယ်။")
            return ContinueHandling()
        source=msg.reply_to_message
        if source is None:
            bot.reply_to(msg,"Forward လုပ်ထားတဲ့ Message ကို Reply ပြီး /ownersave ပို့ပါ။")
            return ContinueHandling()
        try:
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute("INSERT INTO owner_source_messages(chat_id,message_id,preview) VALUES(%s,%s,%s)",
                    (msg.chat.id,source.message_id,(source.text or source.caption or "["+source.content_type+"]")[:180]))
            bot.reply_to(msg,"✅ Telegram Original သိမ်းပြီးပါပြီ။ Dashboard ကနေ ရွေးပို့နိုင်ပြီ။")
        except Exception as exc:
            print("Owner reply save:",type(exc).__name__)
            bot.reply_to(msg,"⚠️ Message သိမ်းမရပါ။")
        return ContinueHandling()
    @bot.message_handler(commands=["broadcastcheck"])
    def broadcast_check(msg):
        if msg.chat.type!="private":return ContinueHandling()
        configured=os.getenv("OWNER_TELEGRAM_ID","").strip()
        matched=configured==str(msg.from_user.id)
        status="✅ Owner ID ကိုက်ညီပါတယ်။" if matched else "❌ Owner ID မကိုက်ပါ၊ သို့မဟုတ် Render မှာ မသတ်မှတ်ရသေးပါ။"
        bot.reply_to(msg,f"🔐 Broadcast Check\n\nYour Telegram ID: <code>{msg.from_user.id}</code>\n{status}\n\nRender Environment က OWNER_TELEGRAM_ID ကို စစ်ပါ။",parse_mode="HTML")
        return ContinueHandling()
    @bot.message_handler(func=lambda m:m.chat.type=="private",content_types=["text","photo","video","animation","document","audio","voice","video_note","sticker"])
    def capture_owner_message(msg):
        owner_id=os.getenv("OWNER_TELEGRAM_ID","").strip()
        if not owner_id or str(msg.from_user.id)!=owner_id:
            bot.reply_to(msg,"🔒 ဒီ Message ကို Broadcast အတွက် သိမ်းခွင့်မရှိပါ။ /broadcastcheck နဲ့ Owner ID ကို စစ်ပါ။")
            return ContinueHandling()
        if msg.content_type=="text" and (msg.text or "").startswith("/") and not getattr(msg,"forward_origin",None) and not getattr(msg,"forward_date",None):return ContinueHandling()
        with _owner_draft_lock:
            draft=_owner_drafts.get(msg.from_user.id)
            if draft and draft.get("phase")=="waiting" and time.monotonic()<draft["expires"]:
                _owner_drafts[msg.from_user.id]={"phase":"ready","chat_id":msg.chat.id,"message_id":msg.message_id,"expires":time.monotonic()+600}
                choices=types.InlineKeyboardMarkup(row_width=1)
                choices.add(types.InlineKeyboardButton("📢 All Groups",callback_data="own:to:all"))
                with get_db_connection() as conn,conn.cursor() as cur:
                    cur.execute("SELECT chat_id,title FROM owner_groups WHERE active AND NOT broadcast_opt_out ORDER BY last_seen DESC LIMIT 20")
                    groups=cur.fetchall()
                for gid,title in groups:
                    choices.add(types.InlineKeyboardButton("👥 "+(title or str(gid))[:30],callback_data="own:to:"+str(gid)))
                choices.add(types.InlineKeyboardButton("❌ Cancel",callback_data="own:cancel"))
                bot.reply_to(msg,"✅ Message ရပြီ။ ပို့မယ့် Group ကို ရွေးပါ။",reply_markup=choices)
                return ContinueHandling()
        # Only /ownersave stores originals. Ordinary private messages are not saved.
        return ContinueHandling()
    @bot.message_handler(commands=["broadcastoff","broadcaston"])
    def toggle_broadcast(msg):
        if msg.chat.type not in ("group","supergroup"):return ContinueHandling()
        try:
            member=bot.get_chat_member(msg.chat.id,msg.from_user.id)
            if member.status not in ("administrator","creator"):
                bot.reply_to(msg,"Group Admin သာ Announcement Setting ပြောင်းနိုင်ပါတယ်။")
                return ContinueHandling()
            record_group(msg.chat)
            optout=(msg.text or "").split()[0].split("@")[0]=="/broadcastoff"
            with get_db_connection() as conn,conn.cursor() as cur:
                cur.execute("UPDATE owner_groups SET broadcast_opt_out=%s WHERE chat_id=%s",(optout,msg.chat.id))
            bot.reply_to(msg,"📢 Announcement ပိတ်ထားပါပြီ။" if optout else "📢 Announcement ပြန်ဖွင့်ထားပါပြီ။")
        except Exception as exc:print("Owner broadcast setting:",type(exc).__name__)
        return ContinueHandling()
