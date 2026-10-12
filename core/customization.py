"""Persistent owner customization. Global defaults + group overrides; no eval."""
import contextvars
import functools
import html
import inspect
import json
import math
import re
import threading
import time
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path

CATALOG=json.loads((Path(__file__).resolve().parent.parent/'config/customization_catalog.json').read_text())
_scope=contextvars.ContextVar('customization_group',default=None)
_lock=threading.RLock()
_values={}
_loaded_at=0
_ready=False
_loading=False
_FIELDS=re.compile(r'\{([a-zA-Z][a-zA-Z0-9_]*)\}')


@contextmanager
def group_scope(chat_id):
    token=_scope.set(chat_id if isinstance(chat_id,int) and chat_id<0 else None)
    try:yield
    finally:_scope.reset(token)


def current_group():
    explicit=_scope.get()
    if explicit is not None:return explicit
    frame=inspect.currentframe().f_back
    try:
        for _ in range(18):
            if not frame:break
            for name in ('chat_id','cid','group_id'):
                value=frame.f_locals.get(name)
                if isinstance(value,int) and value<0:return value
            for name in ('message','msg','m','q','call'):
                value=frame.f_locals.get(name)
                chat=getattr(value,'chat',None) or getattr(getattr(value,'message',None),'chat',None)
                cid=getattr(chat,'id',None)
                if isinstance(cid,int) and cid<0:return cid
            for name in ('game','raid','battle','g','s'):
                value=frame.f_locals.get(name)
                cid=value.get('chat_id') if isinstance(value,dict) else None
                if isinstance(cid,int) and cid<0:return cid
            frame=frame.f_back
        return 0
    finally:del frame


def initialize():
    global _ready
    from database.db import get_db_connection
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('''CREATE TABLE IF NOT EXISTS owner_customizations (
            scope BIGINT NOT NULL, key TEXT NOT NULL, value JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(scope,key))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS owner_customization_log (
            id BIGSERIAL PRIMARY KEY,owner_id BIGINT,scope BIGINT NOT NULL,key TEXT NOT NULL,
            previous JSONB,value JSONB,action TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())''')
        cur.execute('''CREATE TABLE IF NOT EXISTS owner_control_edit (
            owner_id BIGINT PRIMARY KEY,scope BIGINT NOT NULL,key TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL)''')
    _ready=True
    refresh(force=True)


def refresh(force=False):
    global _loaded_at,_values,_loading
    with _lock:
        if not _ready or _loading or (not force and time.monotonic()-_loaded_at<10):return
        _loading=True
    try:
        from database.db import get_db_connection
        with get_db_connection() as conn,conn.cursor() as cur:
            cur.execute('SELECT scope,key,value FROM owner_customizations')
            rows=cur.fetchall()
        valid={}
        for scope,key,value in rows:
            if key not in CATALOG:continue
            try:validate(key,value);valid[(scope,key)]=value
            except ValueError:continue
        with _lock:_values=valid;_loaded_at=time.monotonic()
    except Exception as exc:
        print('Customization refresh:',type(exc).__name__)
        with _lock:_loaded_at=time.monotonic()
    finally:
        with _lock:_loading=False


def effective(key,scope=None):
    refresh()
    if scope is None:scope=current_group()
    with _lock:return _values.get((scope,key),_values.get((0,key),CATALOG[key]['default']))


def _coerce(value,default):
    if isinstance(default,tuple):return tuple(_coerce(v,d) for v,d in zip(value,default))
    if isinstance(default,list):return [_coerce(v,default[min(i,len(default)-1)]) for i,v in enumerate(value)] if default else value
    if isinstance(default,dict):return {k:_coerce(value[k],d) for k,d in default.items()}
    return value


def setting_value(key,default,scope=None):
    if key not in CATALOG:return default
    return _coerce(effective(key,scope),default)


class MarkupValidator(HTMLParser):
    allowed={'b','strong','i','em','u','ins','s','strike','del','code','pre','a','tg-spoiler','tg-emoji','blockquote','span'}
    def __init__(self):super().__init__();self.stack=[]
    def handle_starttag(self,tag,attrs):
        if tag not in self.allowed:raise ValueError('Unsupported HTML tag: '+tag)
        attrs=dict(attrs)
        allowed={'a':{'href'},'tg-emoji':{'emoji-id'},'span':{'class'},'blockquote':{'expandable'},'code':{'class'}}.get(tag,set())
        if set(attrs)-allowed:raise ValueError('Unsupported HTML attribute')
        if tag=='a' and not re.match(r'^(https?://|tg://|\{[A-Za-z][A-Za-z0-9_]*\})',attrs.get('href','')):raise ValueError('Invalid link URL')
        if tag=='span' and attrs.get('class')!='tg-spoiler':raise ValueError('Invalid span')
        self.stack.append(tag)
    def handle_endtag(self,tag):
        if not self.stack or self.stack.pop()!=tag:raise ValueError('Unbalanced HTML tags')
    def finish(self):
        if self.stack:raise ValueError('Unclosed HTML tag')


def validate(key,value):
    if key not in CATALOG:raise ValueError('Unknown customization key')
    entry=CATALOG[key]
    if entry['kind']=='message':
        if not isinstance(value,str) or not value.strip():raise ValueError('Text must not be empty')
        if len(value)>entry.get('max_length',4000):raise ValueError('Text is too long')
        unknown=set(_FIELDS.findall(value))-set(entry.get('fields',[]))
        if unknown:raise ValueError('Unknown placeholders: '+', '.join(sorted(unknown)))
        if any(not _FIELDS.fullmatch(token) for token in re.findall(r'\{[_A-Za-z][^{}]*\}',value)):raise ValueError('Use simple {placeholder} names only')
        if entry.get('html'):
            parser=MarkupValidator();parser.feed(value);parser.finish()
        return value
    default=entry['default']
    def check(v,d):
        if isinstance(d,bool):
            if type(v) is not bool:raise ValueError('Use true or false')
        elif isinstance(d,(int,float)):
            if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('Use a finite number')
            if isinstance(d,int) and type(v) is not int:raise ValueError('Use an integer')
            lo=entry.get('minimum',0);hi=entry.get('maximum',100000)
            if not lo<=v<=hi:raise ValueError(f'Value must be between {lo} and {hi}')
        elif isinstance(d,str):
            if not isinstance(v,str) or len(v)>3500:raise ValueError('Invalid text value')
        elif isinstance(d,list):
            if not isinstance(v,list) or not v or len(v)>entry.get("max_items",500):raise ValueError('Use a nonempty JSON list')
            if entry.get('fixed_length') and len(v)!=len(d):raise ValueError('Keep the same number of entries')
            for i,item in enumerate(v):check(item,d[min(i,len(d)-1)])
        elif isinstance(d,dict):
            if isinstance(v,dict) and 'min' in v and 'max' in v and isinstance(v['min'],(int,float)) and isinstance(v['max'],(int,float)) and v['min']>v['max']:raise ValueError('Minimum exceeds maximum')
            if not isinstance(v,dict) or set(v)!=set(d):raise ValueError('Keep the same object keys')
            for k in d:check(v[k],d[k])
        elif d is None:
            if v is not None:raise ValueError('Keep null for unbounded values')
        else:raise ValueError('Unsupported setting')
    check(value,default)
    if key in ('cfg.tot_auto.threshold','cfg.tot_auto.quiet') and len(value)!=2:
        raise ValueError('Use exactly two values: minimum and maximum')
    if key=='cfg.features.draw_guess.words':
        from games.draw_guess import normalize
        if any(not isinstance(w,str) or not 1<=len(w.strip())<=40 or not normalize(w) for w in value):
            raise ValueError('Drawing words must contain 1 to 40 characters')
        if len({normalize(w) for w in value})!=len(value):
            raise ValueError('Drawing words must be unique')
    if key=='cfg.features.nan_yate.role_enabled':
        if not all(value[r] for r in ('noble','seer','doctor','detective','leader','blade')):
            raise ValueError('Nan Yate requires noble, seer, doctor, detective, leader and blade roles')
    if key=='cfg.features.nan_yate.role_uses':
        if any(type(v) is not int or not 1<=v<=3 for v in value.values()):
            raise ValueError('Role uses must be integers from 1 to 3')
    # Known structural invariants are checked before data reaches gameplay.
    if entry.get('ordered') and any(a>b for a,b in zip(value,value[1:])):raise ValueError('Values must be in ascending order')
    if isinstance(value,dict) and 'min' in value and 'max' in value and value['min']>value['max']:raise ValueError('Minimum exceeds maximum')
    return value


def save(scope,key,value,owner_id,reset=False):
    if scope>0:raise ValueError('Choose Global Defaults or a group')
    if key not in CATALOG:raise ValueError('Unknown customization key')
    if not reset:
        validate(key,value)
        entry=CATALOG[key]
        if entry.get('pair_max') and value>effective(entry['pair_max'],scope):raise ValueError('Minimum exceeds maximum')
        if entry.get('pair_min') and value<effective(entry['pair_min'],scope):raise ValueError('Maximum is below minimum')
    from database.db import get_db_connection
    with get_db_connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(759012347)')
        cur.execute('SELECT value FROM owner_customizations WHERE scope=%s AND key=%s',(scope,key))
        row=cur.fetchone();old=row[0] if row else None
        if reset:cur.execute('DELETE FROM owner_customizations WHERE scope=%s AND key=%s',(scope,key))
        else:
            cur.execute('''INSERT INTO owner_customizations(scope,key,value) VALUES(%s,%s,%s::jsonb)
              ON CONFLICT(scope,key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()''',(scope,key,json.dumps(value)))
        cur.execute('''INSERT INTO owner_customization_log(owner_id,scope,key,previous,value,action)
            VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s)''',
            (owner_id,scope,key,json.dumps(old),json.dumps(None if reset else value),'reset' if reset else 'save'))
    with _lock:
        if reset:_values.pop((scope,key),None)
        else:_values[(scope,key)]=value
    return effective(key,scope)


def message_text(key,default,fields=None,scope=None):
    fields=fields or {}
    if key not in CATALOG:template=default
    else:template=effective(key,scope)
    rendered=_FIELDS.sub(lambda m:str(fields.get(m.group(1),m.group(0))),template)
    # Telegram limits differ for buttons/polls/cards. Unsafe overrides fall back to the original.
    entry=CATALOG.get(key,{})
    if template!=default:
        try:
            if len(rendered)>entry.get('max_length',4000):raise ValueError('Text too long')
            if entry.get('html'):
                parser=MarkupValidator();parser.feed(rendered);parser.finish()
        except ValueError:rendered=_FIELDS.sub(lambda m:str(fields.get(m.group(1),m.group(0))),default)
    return rendered


def preview(key,value=None,scope=0):
    entry=CATALOG[key]
    value=effective(key,scope) if value is None else value
    validate(key,value)
    if entry['kind']!='message':return json.dumps(value,ensure_ascii=False,indent=2)
    examples={f:('Player' if 'name' in f else '10') for f in entry.get('fields',[])}
    return _FIELDS.sub(lambda m:examples[m.group(1)],value)


def install_handler_controls(bot):
    """Scope handler execution and allow existing group commands/features to be disabled."""
    for method in ('message_handler','callback_query_handler','poll_answer_handler','my_chat_member_handler'):
        original=getattr(bot,method)
        def factory(original=original,method=method):
            def decorator(*args,**kwargs):
                register=original(*args,**kwargs)
                def bind(fn):
                    key='enabled.'+('bot' if fn.__module__=='__main__' else fn.__module__)+'.'+fn.__name__
                    @functools.wraps(fn)
                    def wrapped(update,*a,**kw):
                        chat=getattr(update,'chat',None) or getattr(getattr(update,'message',None),'chat',None)
                        cid=getattr(chat,'id',None)
                        if cid is None:return fn(update,*a,**kw)
                        if cid>0 and _ready:
                            text=getattr(update,'text','') or ''
                            data=getattr(update,'data','') or ''
                            if text.lstrip().startswith('/') or data.startswith(('own:','ctl:','ops:')):
                                from database.db import get_db_connection
                                with get_db_connection() as conn,conn.cursor() as cur:
                                    cur.execute('DELETE FROM owner_control_edit WHERE owner_id=%s',(update.from_user.id,))
                                    from features.owner_operations import _ready as ops_ready
                                    if ops_ready and (text.lstrip().startswith('/') or data.startswith(('own:','ctl:'))):
                                        cur.execute('DELETE FROM owner_operation_drafts WHERE user_id=%s',(update.from_user.id,))
                        with group_scope(cid):
                            if method=='message_handler' and cid<0:
                                from features.owner_operations import feature_allowed,usage,COMMAND_GAMES
                                if kwargs.get('commands'):
                                    usage(cid,'command',((getattr(update,'text','') or '').split() or [''])[0],f'cmd:{cid}:{getattr(update,"message_id",0)}')
                                command=((getattr(update,'text','') or '').split() or [''])[0].lstrip('/').split('@')[0].lower()
                                game_key=COMMAND_GAMES.get(command) if kwargs.get('commands') else None
                                if not feature_allowed(key,cid) or (game_key and not feature_allowed('game:'+game_key,cid)):
                                    from telebot.handler_backends import ContinueHandling
                                    if kwargs.get('commands'):
                                        bot.reply_to(update,message_text('system.test_group_only','🧪 ဒီ feature ကို Test Group မှာပဲ စမ်းနေပါတယ်။'))
                                        return None
                                    return ContinueHandling()
                            if method=='message_handler' and cid<0 and key in CATALOG and not effective(key,cid):
                                from telebot.handler_backends import ContinueHandling
                                if kwargs.get('commands'):
                                    bot.reply_to(update,message_text('system.disabled','⏸ ဒီ function ကို Owner က ပိတ်ထားပါတယ်။'))
                                    return None
                                return ContinueHandling()
                            return fn(update,*a,**kw)
                    return register(wrapped)
                return bind
            return decorator
        setattr(bot,method,factory())


def bank_text(module,default):
    entries=[(e['default'],key) for key,e in CATALOG.items()
             if e['kind']=='message' and e.get('bank') and e['category']==module]
    if not entries:return default
    replacements={old:effective(key) for old,key in entries}
    active={old:new for old,new in replacements.items() if old!=new}
    if not active:return default
    pattern=re.compile('|'.join(re.escape(s) for s in sorted(active,key=len,reverse=True)))
    def walk(value):
        if isinstance(value,str):return pattern.sub(lambda m:active[m.group(0)],value)
        if isinstance(value,list):return [walk(v) for v in value]
        if isinstance(value,tuple):return tuple(walk(v) for v in value)
        if isinstance(value,dict):return {k:walk(v) for k,v in value.items()}
        return value
    return walk(default)
