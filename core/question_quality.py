"""Bounded API cache and robust multiple-choice question validation."""
import copy
import json
import random
import threading
import time
import urllib.error
import urllib.request

_lock=threading.RLock()
_cache={}
_inflight={}
_MAX_ITEMS=120

def cached_json(url, ttl=1800, timeout=5):
    now=time.monotonic()
    with _lock:
        record=_cache.get(url)
        if record and now-record[0]<ttl:
            return copy.deepcopy(record[1])
        event=_inflight.get(url)
        if event is None:
            event=threading.Event()
            _inflight[url]=event
            leader=True
        else:
            leader=False
    if not leader:
        event.wait(timeout+1)
        with _lock:
            record=_cache.get(url)
            if record:
                return copy.deepcopy(record[1])
        raise TimeoutError("Provider cache wait expired")
    try:
        req=urllib.request.Request(url,headers={
            "User-Agent":"MyanmarGroupGamesBot/1.0 (quiz data cache)",
            "Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=timeout) as response:
            result=json.load(response)
        with _lock:
            if len(_cache)>=_MAX_ITEMS:
                oldest=min(_cache,key=lambda key:_cache[key][0])
                _cache.pop(oldest,None)
            _cache[url]=(time.monotonic(),result)
        return copy.deepcopy(result)
    finally:
        with _lock:
            _inflight.pop(url,None)
            event.set()

def validate_question(item):
    if not isinstance(item,dict):
        return None
    question=item.get("question")
    answers=item.get("answers")
    try:
        index=int(item["correct_index"])
    except (TypeError,ValueError,KeyError):
        return None
    if not isinstance(question,str) or not 8<=len(question.strip())<=350:
        return None
    if not isinstance(answers,list) or len(answers)!=4 or index not in range(4):
        return None
    clean=[str(a).strip() for a in answers]
    if any(not x or len(x)>160 for x in clean):
        return None
    if len({x.casefold() for x in clean})!=4:
        return None
    item=dict(item)
    item["question"]=question.strip()
    item["answers"]=clean
    item["correct_index"]=index
    return item

def make_mcq(question,correct,wrong,source):
    answer=str(correct).strip()
    options=list({str(x).strip() for x in wrong if str(x).strip().casefold()!=answer.casefold()})
    options=[x for x in options if x and len(x)<=160]
    if len(options)<3:
        return None
    answers=[answer]+random.sample(options,3)
    random.shuffle(answers)
    return validate_question({"question":question,"answers":answers,
                              "correct_index":answers.index(answer),"source":source})
