"""Five-round group Math Battle; scores are match-only until final rewards."""
import random
import threading
import time
import uuid
from core.sessions import start_session, end_session
from database.used_questions import get_used_question_ids, get_recent_question_ids, mark_question_used, reset_used_questions

TIMES = (45, 60, 75, 90, 105)
_lock = threading.RLock()
_games = {}
_POOL = None

def _pool():
    global _POOL
    if _POOL is not None:
        return _POOL
    rng = random.Random(20261004)
    pools = []
    for level in range(5):
        pool = []
        seen = set()
        for attempt in range(150000):
            if level == 0:
                a, b = rng.randint(3, 90), rng.randint(2, 80)
                op = rng.choice(('+', '-', '×'))
                if op == '×': a, b = rng.randint(2, 12), rng.randint(2, 12)
                if op == '-' and a < b: a, b = b, a
                q = f'{a} {op} {b}'
                ans = a+b if op=='+' else a-b if op=='-' else a*b
            elif level == 1:
                a,b,c = rng.randint(5,40), rng.randint(2,15), rng.randint(2,13)
                op=rng.choice(('+','-'))
                q=f'{a} {op} {b} × {c}'
                ans=a+b*c if op=='+' else a-b*c
            elif level == 2:
                a,b,c = rng.randint(3,24), rng.randint(2,16), rng.randint(2,18)
                op=rng.choice(('+','-'))
                q=f'({a} {op} {b}) × {c}'
                ans=(a+b)*c if op=='+' else (a-b)*c
            elif level == 3:
                x, a, b = rng.randint(-14,22), rng.randint(2,10), rng.randint(-40,40)
                c=a*x+b
                q=f'{a}x {"+" if b>=0 else "-"} {abs(b)} = {c}; x = ?'
                ans=x
            else:
                a,b,c,d = rng.randint(2,17),rng.randint(2,19),rng.randint(2,15),rng.randint(2,12)
                op=rng.choice(('+','-'))
                q=f'({a}² {op} {b} × {c}) ÷ {d}'
                numerator = a*a+b*c if op=='+' else a*a-b*c
                if numerator%d: continue
                ans=numerator//d
            if q in seen: continue
            seen.add(q)
            pool.append({'id':f'M{level+1}-{len(pool)+1:04d}','question':q,'answer':ans})
            if len(pool)==1000: break
        if len(pool)<1000: raise RuntimeError(f'Only {len(pool)} level {level+1} questions')
        pools.append(pool)
    _POOL=pools
    return pools

def _next_question(chat_id, level):
    pool=_pool()[level]
    kind='math_battle'
    used=set(get_used_question_ids(chat_id,kind))
    available=[q for q in pool if q['id'] not in used]
    if not available:
        recent=set(get_recent_question_ids(chat_id,kind,limit=150))
        reset_used_questions(chat_id,kind)
        available=[q for q in pool if q['id'] not in recent] or pool
    q=random.choice(available).copy()
    # A new match uses one ID only once, even when database unavailable.
    mark_question_used(chat_id,kind,q['id'])
    ans=q['answer']
    wrong=set()
    while len(wrong)<3:
        delta=random.choice([-24,-18,-12,-9,-7,-5,-3,-2,2,3,5,7,9,12,18,24])
        option=ans+delta
        if option!=ans: wrong.add(option)
    options=list(wrong)[:3]+[ans]
    random.shuffle(options)
    q['options']=options
    q['correct_index']=options.index(ans)
    return q

def snapshot(chat_id):
    with _lock:
        g=_games.get(chat_id)
        if not g: return None
        return dict(g, scores=dict(g['scores']), names=dict(g['names']), answered=set(g['answered']), podium=list(g['podium']), question=dict(g['question']))

def start(chat_id):
    with _lock:
        if chat_id in _games: return False, 'math_battle'
        ok, sess=start_session(chat_id,'math_battle',duration=sum(TIMES)+180)
        if not ok: return False,sess
        try: q=_next_question(chat_id,0)
        except Exception:
            end_session(chat_id,'math_battle')
            raise
        now=time.monotonic()
        g={'id':uuid.uuid4().hex[:14], 'chat_id':chat_id,'round':0,'question':q,
           'deadline':now+TIMES[0], 'answered':set(),'podium':[],'scores':{},'names':{},
           'message_id':None,'version':0,'next_at':None}
        _games[chat_id]=g
        return True,snapshot(chat_id)

def set_message(chat_id, game_id, round_index, message_id):
    with _lock:
        g=_games.get(chat_id)
        if not g or g['id']!=game_id or g['round']!=round_index: return False
        g['message_id']=message_id
        return True

def answer(chat_id, game_id, round_index, user_id, name, index):
    with _lock:
        g=_games.get(chat_id)
        if not g or g['id']!=game_id or g['round']!=round_index: return 'stale',None
        now=time.monotonic()
        if now>=g['deadline']: return 'closed',snapshot(chat_id)
        if user_id in g['answered']: return 'already',snapshot(chat_id)
        g['answered'].add(user_id)
        if index!=g['question']['correct_index']: return 'wrong',snapshot(chat_id)
        if len(g['podium'])>=3: return 'late',snapshot(chat_id)
        # Random MATCH SCORE per correct-answer position.
        # Disjoint ranges preserve 1st > 2nd > 3rd.
        score_ranges = ((10, 18), (5, 9), (1, 4))
        pts = random.randint(*score_ranges[len(g['podium'])])
        g['podium'].append(user_id)
        g['scores'][user_id]=g['scores'].get(user_id,0)+pts
        g['names'][user_id]=(name or 'Player')[:35]
        if len(g['podium'])==1:
            g['deadline']=min(g['deadline'],now+10)
        if len(g['podium'])>=3: g['deadline']=now
        g['version']+=1
        return 'correct',snapshot(chat_id)

def advance(chat_id, game_id, round_index):
    with _lock:
        g=_games.get(chat_id)
        if not g or g['id']!=game_id or g['round']!=round_index: return 'stale',None
        if time.monotonic()<g['deadline']: return 'early',snapshot(chat_id)
        if round_index==4:
            result=snapshot(chat_id)
            _games.pop(chat_id,None)
            end_session(chat_id,'math_battle')
            return 'finished',result
        nxt=round_index+1
        q=_next_question(chat_id,nxt)
        g.update(round=nxt,question=q,deadline=time.monotonic()+TIMES[nxt],answered=set(),podium=[],message_id=None,version=g['version']+1)
        return 'next',snapshot(chat_id)

def stop(chat_id):
    with _lock:
        g=_games.pop(chat_id,None)
        if g: end_session(chat_id,'math_battle')
        return g
