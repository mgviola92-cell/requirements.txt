"""Bounded, retryable batches for noncritical activity metadata only."""
import atexit
import logging
import threading
from collections import OrderedDict
from database.db import get_db_connection
LOG=logging.getLogger(__name__)
_WRITERS=[]

def flush_all():
    for writer in list(_WRITERS):writer.flush()


class BatchWriter:
    def __init__(self,sql,interval=15,limit=5000):
        self.sql=sql;self.interval=interval;self.limit=limit
        self.pending=OrderedDict();self.lock=threading.RLock();self.flushing=threading.Lock();self.started=False
        _WRITERS.append(self)
        atexit.register(self.flush)
    def submit(self,key,params):
        with self.lock:
            full=len(self.pending)>=self.limit and key not in self.pending
        if full:self.flush()
        with self.lock:
            # Backpressure instead of silently dropping activity during an outage.
            if len(self.pending)>=self.limit and key not in self.pending:return False
            self.pending[key]=params
            if not self.started:
                self.started=True
                threading.Thread(target=self.loop,name='activity-batch',daemon=True).start()
        return True
    def snapshot(self):
        with self.lock:return list(self.pending.values())
    def loop(self):
        pause=threading.Event()
        while True:
            pause.wait(self.interval);self.flush()
    def flush(self):
        with self.flushing:
            with self.lock:
                if not self.pending:return True
                batch=self.pending;self.pending=OrderedDict()
            try:
                with get_db_connection() as con,con.cursor() as cur:cur.executemany(self.sql,list(batch.values()))
                return True
            except Exception:
                with self.lock:
                    # A newer value wins when a failed batch is merged back.
                    for key,value in batch.items():
                        if key not in self.pending:self.pending[key]=value
                LOG.debug('Activity batch deferred')
                return False
