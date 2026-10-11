"""Owner-only Flask dashboard. Locked until Render env secrets are configured."""
import os, time, secrets, threading, html
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, render_template_string, abort
from werkzeug.security import check_password_hash
from database.db import get_db_connection
from telebot.handler_backends import ContinueHandling

dashboard = Blueprint("owner_dashboard", __name__, url_prefix="/owner")
BOT = None
_job_lock = threading.Lock()
_running = False

def _ready():
    return bool(os.getenv("OWNER_PASSWORD_HASH") and os.getenv("DASHBOARD_SECRET_KEY"))

def _init_db():
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS owner_groups (
          chat_id BIGINT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
          active BOOLEAN NOT NULL DEFAULT TRUE, broadcast_opt_out BOOLEAN NOT NULL DEFAULT FALSE,
          last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""")
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
    body+="</div><div class='panel'><h2>Tracked Groups</h2><p class='muted'>Only groups discovered after tracking starts; total is not a historical Telegram-wide count.</p><div class='wrap'><table><tr><th>Group</th><th>Chat ID</th><th>Status</th><th>Last seen UTC</th></tr>"
    for title,gid,is_active,optout,last in groups:
        body+=f"<tr><td>{html.escape(title or 'Unnamed')}</td><td>{gid}</td><td>{'Active' if is_active else 'Left'}{' · Opted out' if optout else ''}</td><td>{html.escape(str(last)[:19])}</td></tr>"
    body+="</table></div></div><div class='panel'><h2>Broadcast History</h2><div class='wrap'><table><tr><th>ID</th><th>Sent</th><th>Failed</th><th>Total</th><th>Status</th></tr>"
    for rid,created,all_count,sent,failed,status in history:
        body+=f"<tr><td>{rid}</td><td>{sent}</td><td>{failed}</td><td>{all_count}</td><td>{html.escape(status)}</td></tr>"
    body+="</table></div></div>"
    return _shell(body)

@dashboard.route("/broadcast",methods=["GET","POST"])
@_protect
def broadcast():
    global _running
    if request.method=="POST":
        _verify_csrf()
        message=(request.form.get("message") or "").strip()
        if not message or len(message)>1500: return ("Message must be 1–1500 characters",400)
        if request.form.get("confirm")!="yes":return ("Confirmation required",400)
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
            threading.Thread(target=_send_broadcast,args=(jobid,message,ids),daemon=True).start()
        except Exception:
            with _job_lock:_running=False
            raise
        return redirect(url_for("owner_dashboard.index"))
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT chat_id,title FROM owner_groups WHERE active=TRUE AND broadcast_opt_out=FALSE ORDER BY title")
        groups=cur.fetchall()
        count=len(groups)
    choices="<option value='all'>All groups</option>"
    for gid,title in groups:
        choices+=f"<option value='{gid}'>{html.escape(title or str(gid))}</option>"
    body=f"""<h1>📢 Broadcast Center</h1><div class='panel'><h2>Send announcement to {count} opted-in groups</h2>
<p class='muted'>Group admins can opt out using /broadcastoff in their group. Broadcasts are plain text and rate limited.</p>
<form method="post"><input type="hidden" name="csrf" value="{html.escape(_csrf())}">
<label>Destination</label><select name="target" style="width:100%;padding:12px;background:#101a2a;color:white;border:1px solid #50637f;border-radius:9px">{choices}</select><textarea name="message" maxlength="1500" required placeholder="Write the announcement..."></textarea>
<label><input style="width:auto" type="checkbox" name="confirm" value="yes" required> I confirm sending to selected destination.</label>
<p><button>Send to groups</button></p></form></div>"""
    return _shell(body)

def _send_broadcast(jobid,message,ids):
    global _running
    sent=failed=0
    try:
        for gid in ids:
            try:
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
        new=getattr(m.new_chat_member,"status","")
        record_group(m.chat,active=new not in ("left","kicked"))
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
