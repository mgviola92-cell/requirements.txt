"""Wake local workers only after a successful transaction commits.

Database remains authoritative. Aligned 15-minute recovery reads catch writes from
another process and missed notifications; known due times wake earlier.
"""
import re
import threading
import time

_LOCK=threading.RLock()
_SIGNALS={}
_PENDING={}
RECOVERY_SECONDS=900
_WRITE=re.compile(r'^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:public\.)?"?([a-z_][a-z0-9_]*)',re.I)


def signal(*tables):
    event=threading.Event()
    with _LOCK:
        for table in tables:_SIGNALS.setdefault(table,set()).add(event)
    return event


def begin(connection):
    with _LOCK:_PENDING[id(connection)]=set()


def wrote(connection,query):
    match=_WRITE.match(str(query))
    if not match:return
    with _LOCK:
        pending=_PENDING.get(id(connection))
        if pending is not None:pending.add(match[1].lower())


def take(connection):
    # Detach before the connection returns to the pool; another borrower may
    # acquire the same connection immediately after its context exits.
    with _LOCK:return _PENDING.pop(id(connection),set())


def dispatch(tables):
    with _LOCK:events={event for table in tables for event in _SIGNALS.get(table,())}
    for event in events:event.set()


def finish(connection,committed):
    tables=take(connection)
    if committed:dispatch(tables)


def delay(deadline=None,now=None,minimum=0.1):
    """Next durable deadline or shared recovery boundary, whichever comes first."""
    now=time.time() if now is None else now
    recovery=RECOVERY_SECONDS-now%RECOVERY_SECONDS
    return max(minimum,min(recovery,deadline-now) if deadline is not None else recovery)


def timestamp(value):
    return value.timestamp() if value is not None else None


def next_due(sql,params=None):
    from database.db import get_db_connection
    with get_db_connection() as con,con.cursor() as cur:
        cur.execute(sql,params);row=cur.fetchone()
    return timestamp(row[0]) if row and row[0] is not None else None
