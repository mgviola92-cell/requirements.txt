"""Reuse Telegram photo identifiers, scoped to one bot and exact image bytes."""
import hashlib
import logging
import threading
from collections import OrderedDict
from telebot import types
from database.db import get_db_connection

LOG=logging.getLogger(__name__)
_CACHE=OrderedDict()
_LOCK=threading.RLock()
_LIMIT=256

def initialize():
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute('CREATE TABLE IF NOT EXISTS telegram_photo_cache(bot_key TEXT NOT NULL,digest TEXT NOT NULL,file_id TEXT NOT NULL,PRIMARY KEY(bot_key,digest))')

def key(bot,photo):
    token=getattr(bot,'token',None)
    if not isinstance(token,str) or not token:return None
    if isinstance(photo,bytes):raw=photo
    elif callable(getattr(photo,'getvalue',None)):raw=photo.getvalue()
    else:return None
    if not isinstance(raw,bytes):return None
    return hashlib.sha256(token.encode()).hexdigest(),hashlib.sha256(raw).hexdigest()

def lookup(identity):
    if identity is None:return None
    with _LOCK:
        if identity in _CACHE:
            _CACHE.move_to_end(identity);return _CACHE[identity]
    try:
        with get_db_connection() as con,con.cursor() as cur:
            cur.execute('SELECT file_id FROM telegram_photo_cache WHERE bot_key=%s AND digest=%s',identity);row=cur.fetchone()
        if row:
            remember(identity,row[0],persist=False);return row[0]
    except Exception:LOG.debug('Photo cache lookup unavailable')
    return None

def remember(identity,file_id,persist=True):
    if identity is None or not isinstance(file_id,str) or not file_id:return
    with _LOCK:
        _CACHE[identity]=file_id;_CACHE.move_to_end(identity)
        while len(_CACHE)>_LIMIT:_CACHE.popitem(last=False)
    if persist:
        try:
            with get_db_connection() as con,con.cursor() as cur:
                cur.execute('INSERT INTO telegram_photo_cache VALUES(%s,%s,%s) ON CONFLICT(bot_key,digest) DO UPDATE SET file_id=EXCLUDED.file_id WHERE telegram_photo_cache.file_id IS DISTINCT FROM EXCLUDED.file_id',(*identity,file_id))
        except Exception:LOG.debug('Photo cache save unavailable')

def invalid_file(exc):
    reason=str(exc).lower()
    return getattr(exc,'error_code',None)==400 and any(s in reason for s in ('wrong file identifier','file_id','invalid file id','file reference expired'))

def deliver(bot,photo,operation):
    identity=key(bot,photo);cached=lookup(identity)
    try:result=operation(cached or photo)
    except Exception as exc:
        if not cached or not invalid_file(exc):raise
        # Only invalid stored IDs fall back to one upload. Permission/network errors do not.
        with _LOCK:_CACHE.pop(identity,None)
        if callable(getattr(photo,'seek',None)):photo.seek(0)
        result=operation(photo)
    photos=getattr(result,'photo',None)
    if isinstance(photos,(list,tuple)) and photos:
        file_id=getattr(photos[-1],'file_id',None)
        if file_id and file_id!=cached:remember(identity,file_id)
    return result

def send_photo(bot,chat_id,photo,**kwargs):
    return deliver(bot,photo,lambda media:bot.send_photo(chat_id,media,**kwargs))

def edit_photo(bot,chat_id,message_id,photo,**kwargs):
    caption=kwargs.pop('caption',None);parse_mode=kwargs.pop('parse_mode',None)
    return deliver(bot,photo,lambda media:bot.edit_message_media(types.InputMediaPhoto(media,caption=caption,parse_mode=parse_mode),chat_id,message_id,**kwargs))
