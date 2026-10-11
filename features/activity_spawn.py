"""Group-local randomized activity triggers for raid and WYR (not timer loops)."""
import random
import threading
import time
from collections import deque


class ActivitySpawner:
    def __init__(self, spawn, *, threshold, chance, quiet, can_spawn=lambda cid: True,
                 clock=time.monotonic, rng=None):
        self.spawn=spawn
        self.threshold=threshold
        self.chance=chance
        self.quiet=quiet
        self.can_spawn=can_spawn
        self.clock=clock
        self.rng=rng or random.Random()
        self.lock=threading.RLock()
        self.groups={}

    def _state(self, cid):
        if cid not in self.groups:
            self.groups[cid]={'events':deque(), 'users':{},
                'next_check':self.rng.randint(*self.threshold), 'quiet_until':0, 'checking':False}
        return self.groups[cid]

    def note_spawn(self, cid):
        with self.lock:
            state=self._state(cid)
            state['events'].clear()
            state['next_check']=self.rng.randint(*self.threshold)
            state['quiet_until']=self.clock()+self.rng.randint(*self.quiet)

    def record(self, cid, uid):
        now=self.clock()
        with self.lock:
            state=self._state(cid)
            # Only activity from the last ten minutes counts; one-user floods don't trigger.
            expired=0
            while state['events'] and state['events'][0][0]<now-600:
                state['events'].popleft()
                expired+=1
            if expired:
                state['next_check']=max(self.threshold[0],state['next_check']-expired)
            state['users']={u:t for u,t in state['users'].items() if t>=now-600}
            if now-state['users'].get(uid,float('-inf'))<3:return False
            state['users'][uid]=now
            if now<state['quiet_until'] or state['checking']:return False
            state['events'].append((now,uid))
            count=len(state['events'])
            if count<state['next_check'] or len({u for _,u in state['events']})<2:return False
            state['checking']=True
        success=False
        try:
            if self.can_spawn(cid) and self.rng.random()<self.chance:
                success=bool(self.spawn(cid))
            return success
        finally:
            with self.lock:
                state['checking']=False
                if success:self.note_spawn(cid)
                else:
                    # Keep earned activity when another game blocks us; retry after a few messages.
                    state['next_check']=len(state['events'])+self.rng.randint(3,7)
