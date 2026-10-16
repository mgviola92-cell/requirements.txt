"""Process-local payload accounting. No secrets, chat text, SQL or URLs retained.
Payload sizes exclude transport headers/TLS; database sizes are estimates.
"""
import json
import threading
import time
import sys
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse
import psycopg

_STARTED=time.time()
_LOCK=threading.Lock()
_ROWS=defaultdict(lambda:dict(calls=0,sent_bytes=0,received_bytes=0))

def size(value):
    if value is None:return 0
    if isinstance(value,(bytes,bytearray,memoryview)):return len(value)
    if isinstance(value,str):return len(value.encode('utf-8'))
    if isinstance(value,dict):return len(json.dumps(value,ensure_ascii=False,default=str,separators=(',',':')).encode())
    if isinstance(value,(tuple,list)):return sum(size(v) for v in value)
    return len(str(value).encode())

def caller():
    frame=sys._getframe(1)
    for _ in range(16):
        if frame is None:break
        path=Path(frame.f_code.co_filename)
        if path.name not in ('traffic_meter.py','db.py') and path.parent.name in ('features','database','games','core'):
            return path.parent.name+'.'+path.stem+'.'+frame.f_code.co_name
        if path.name=='bot.py':return 'bot.'+frame.f_code.co_name
        frame=frame.f_back
    return 'other'

def record(category,label,sent=0,received=0,calls=1):
    with _LOCK:
        row=_ROWS[(category,label)]
        row['calls']+=calls;row['sent_bytes']+=int(sent);row['received_bytes']+=int(received)

def snapshot():
    with _LOCK:
        rows=[dict(category=c,label=l,**v) for (c,l),v in _ROWS.items()]
    return dict(since=_STARTED,note='Request payload sizes count attempts; excludes TLS/protocol overhead. Database bytes are estimates. Counters reset when the process restarts.',rows=sorted(rows,key=lambda r:r['sent_bytes'],reverse=True))

def query_label(query):
    match=re.search(r'\b(?:INTO|UPDATE|FROM)\s+([a-z_][a-z0-9_]*)',str(query),re.I)
    return caller()+(':'+match[1] if match else '')

class MeteredCursor(psycopg.Cursor):
    def execute(self,query,params=None,**kwargs):
        self._traffic_label=query_label(query)
        record('database_estimate',self._traffic_label,sent=size(query)+size(params))
        return super().execute(query,params,**kwargs)
    def executemany(self,query,params_seq,**kwargs):
        params=list(params_seq);self._traffic_label=query_label(query)
        record('database_estimate',self._traffic_label,sent=sum(size(query)+size(p) for p in params),calls=len(params))
        return super().executemany(query,params,**kwargs)
    def _received(self,value):
        record('database_estimate',getattr(self,'_traffic_label','other'),received=size(value),calls=0)
        return value
    def fetchone(self):return self._received(super().fetchone())
    def fetchall(self):return self._received(super().fetchall())
    def fetchmany(self,*args,**kwargs):return self._received(super().fetchmany(*args,**kwargs))

def install_telegram():
    import requests
    original=requests.Session.send
    if getattr(original,'_traffic_meter',False) is True:return
    def send(session,request,**kwargs):
        parsed=urlparse(request.url)
        if parsed.hostname!='api.telegram.org':return original(session,request,**kwargs)
        method=parsed.path.rsplit('/',1)[-1]
        if not re.fullmatch('[A-Za-z]+',method):method='file_download'
        label=caller()+':'+method
        body=request.body
        record('telegram_payload',label,sent=size(body) if isinstance(body,(str,bytes,bytearray)) else 0)
        response=original(session,request,**kwargs)
        if not kwargs.get('stream'):record('telegram_payload',label,received=len(response.content),calls=0)
        return response
    send._traffic_meter=True
    requests.Session.send=send


def install_flask(app):
    from flask import request
    @app.after_request
    def measure_web(response):
        record('web_payload',request.endpoint or 'unknown',sent=response.content_length or 0,received=request.content_length or 0)
        return response
