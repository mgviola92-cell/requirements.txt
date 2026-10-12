"""Pure five-round preference voting with stale-button protection."""
import uuid
from data.this_or_that import CAPACITY,question
DEFAULTS={'rounds':5,'round_seconds':30,'participation_reward':3}
def new(cid,owner,rules):
    return {'id':uuid.uuid4().hex[:12],'chat_id':cid,'owner':owner,'rules':dict(DEFAULTS,**rules),'phase':'playing','round':0,'deadline':0,'votes':{},'participants':{},'used':[],'results':[],'card':None,'photo':False,'dirty':False,'edited':0,'question':None}
def open_round(s,index,now):
    s['round']+=1;s['question']=question(index);s['used'].append(index)
    s['votes']={};s['deadline']=now+s['rules']['round_seconds'];s['dirty']=False
    return s

def vote(s,gid,round_no,uid,side,now):
    if s['phase']!='playing' or s['id']!=gid or s['round']!=round_no or now>=s['deadline'] or side not in ('a','b'):raise ValueError('expired')
    uid=str(uid)
    if uid in s['votes']:raise ValueError('voted')
    s['votes'][uid]=side;s['participants'][uid]=True;s['dirty']=True

def counts(s):
    a=sum(v=='a' for v in s['votes'].values());b=sum(v=='b' for v in s['votes'].values());total=a+b
    return a,b,round(100*a/total) if total else 0,round(100*b/total) if total else 0

def close_round(s):
    a,b,ap,bp=counts(s);s['results'].append({'round':s['round'],'a':s['question']['a']['label'],'b':s['question']['b']['label'],'av':a,'bv':b})
    if s['round']>=s['rules']['rounds']:s['phase']='finished'

def cancel(s):s['phase']='cancelled';s['dirty']=False
