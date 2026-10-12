"""Pure, serializable Nan Yate rules. No Telegram, database or wall-clock effects."""
import random
from collections import Counter

# id: Burmese label, faction, action, uses (-1 unlimited), description
ROLE_ROWS = [
 ('noble','မှူးမတ်','court','search',-1,'သက်သေရှာရာတွင် အခွင့်အရေးပိုကောင်းသည်။'),
 ('seer','နက္ခတ်ဆရာ','court','seer',-1,'ပစ်မှတ်၏ဘက်ကိုစစ်သည်။ မျက်နှာဖုံးအစွမ်းက လှည့်စားနိုင်သည်။'),
 ('detective','နန်းတွင်းစုံထောက်','court','verify',-1,'မိမိပိုင်သက်သေ အတု/အစစ် စစ်သည်။'),
 ('tracker','ခြေရာခံမုဆိုး','court','track',-1,'ပစ်မှတ်သွားခဲ့သော နေရာကိုကြည့်သည်။'),
 ('watcher','ကင်းထောက်','court','watch',-1,'နေရာတစ်ခုသို့လာသူ အများဆုံးသုံးဦးကိုကြည့်သည်။'),
 ('listener','နားစွင့်သူ','court','listen',-1,'ပစ်မှတ် အစွမ်းသုံးခဲ့လား စစ်သည်။'),
 ('doctor','သမားတော်','court','protect',-1,'တိုက်ခိုက်မှုတစ်ကြိမ်ကိုကာသည်။ တူညီသူကိုဆက်တိုက်မကာနိုင်။'),
 ('guard','အမတ်စောင့်','court','guard',2,'ပစ်မှတ်အစား တိုက်ခိုက်မှုတစ်ကြိမ်ခံသည်။ ကိုယ်ကိုကာမရ။'),
 ('healer','ဆေးမြစ်ဆရာ','court','heal',-1,'အဆိပ်ကိုကုသည်။'),
 ('cleanser','ကျိန်စာဖြေဆရာ','court','cleanse',-1,'သက်သေဖော်ပြခွင့်ကျိန်စာကိုဖြေသည်။'),
 ('blocker','တံခါးမှူး','court','block',2,'ပစ်မှတ်၏ ညအစွမ်းကိုပိတ်သည်။'),
 ('smith','ပန်းပဲဆရာ','court','armor',2,'တိုက်ခိုက်မှုတစ်ကြိမ်ခံနိုင်သည့်ချပ်ဝတ်ပေးသည်။'),
 ('scribe','နန်းစာရေး','court','recover',2,'သေသူပိုင်သက်သေတစ်ခုကိုရယူသည်။ Role မရ။'),
 ('diplomat','တော်ဝင်သံတမန်','court','link',2,'ကိုယ်နှင့်ပစ်မှတ်ကို နောက်ညအထိ လျှို့ဝှက်ဆွေးနွေးခွင့်ပေးသည်။'),
 ('minister','အမိန့်ပြန်အမတ်','court','pardon',1,'နေ့ဆွေးနွေးချိန် ရွေးသူ၏ထုတ်ပယ်မှုကို တစ်ကြိမ်တားသည်။ မိမိ Role ပေါ်မည်။'),
 ('lamp','မီးအိမ်စောင့်','court','illuminate',1,'နေရာတစ်ခုမှ အစစ်သက်သေကို လူတိုင်းထံဖော်သည်။'),
 ('judge','တော်ဝင်တရားသူကြီး','court','judge',1,'နေ့ဆွေးနွေးချိန်ရွေးသူကို ထပ်မဲတူလျှင် ဆုံးဖြတ်ပေးသည်။'),
 ('soldier','သံချပ်ဝတ်စစ်သည်','court','search',-1,'ပထမတိုက်ခိုက်မှုတစ်ကြိမ်ခံနိုင်သည်။'),
 ('leader','လုပ်ကြံခေါင်းဆောင်','plot','search',-1,'အဖွဲ့တိုက်ခိုက်မဲတူလျှင် မိမိရွေးသူကိုဦးစားပေးသည်။'),
 ('blade','ဓားဝှက်သမား','plot','search',-1,'အဖွဲ့၏တိုက်ခိုက်မှုဆောင်ရွက်သူအဖြစ်ဦးစားပေးခံရသည်။'),
 ('poisoner','အဆိပ်ခတ်သူ','plot','poison',1,'တစ်ကြိမ်အဆိပ်ခတ်သည်။ ပစ်မှတ်သည်နောက်ညကုန်မှသေမည်။'),
 ('hider','ခြေရာဖျောက်သူ','plot','hide',2,'လုပ်ကြံအဖွဲ့ဝင်တစ်ဦး၏ခြေရာကိုဖျောက်သည်။'),
 ('forger','စာတုရေးသူ','plot','forge',2,'ပစ်မှတ်သွားခဲ့သကဲ့သို့ သက်သေအတုတစ်ခုဖန်တီးသည်။'),
 ('mask','မျက်နှာဖုံးသူ','plot','mask',1,'ကိုယ့်ဘက်ကို တစ်ညတာနန်းတော်ဟုစစ်တွေ့စေသည်။'),
 ('spy','အတွင်းသတင်းပေး','plot','spy',-1,'ပစ်မှတ်၏အစွမ်းအုပ်စုကိုစစ်သည်။'),
 ('curser','ကျိန်စာတိုက်သူ','plot','curse',2,'ပစ်မှတ်သည် နောက်နေ့သက်သေတစ်ခုသာဖော်နိုင်မည်။'),
 ('jester','ပွဲလှန့်သူ','neutral','search',-1,'မဲဖြင့်ထုတ်ပယ်ခံရလျှင် တစ်ဦးချင်းနိုင်သည်။'),
 ('hunter','ပစ်မှတ်မုဆိုး','neutral','search',-1,'မိမိပစ်မှတ် မဲဖြင့်ထုတ်ပယ်ခံရလျှင်နိုင်သည်။ ညသေပါကအသက်ရှင်ရန်ပြောင်းသည်။'),
 ('treasure','ရတနာရှာသူ','neutral','search',-1,'နေရာမတူသုံးခုမှ ရတနာစု၍ ဆန္ဒအလျောက်ထွက်ခွာလျှင်နိုင်သည်။'),
 ('keeper','အစောင့်အရှောက်','neutral','protect',2,'မိမိပစ်မှတ် ပွဲဆုံးချိန်အသက်ရှင်လျှင်နိုင်သည်။'),
 ('mimic','အစွမ်းကူးဆရာ','neutral','copy',1,'သေသူ၏ခွင့်ပြုအစွမ်းကိုတစ်ကြိမ်ကူးယူပြီး နောက်ညသုံးနိုင်သည်။ အသက်ရှင်လျှင်နိုင်။'),
 ('merchant','နန်းတွင်းကုန်သည်','neutral','gift',3,'လူမတူသုံးဦးကိုသက်သေစစ်ပစ္စည်းပေးပြီး ပွဲဆုံးချိန်အသက်ရှင်လျှင်နိုင်သည်။'),
]
ROLES={r[0]:dict(zip(('name','side','action','uses','description'),r[1:])) for r in ROLE_ROWS}
LOCATIONS=['နန်းဆောင်','ဆေးတိုက်','လက်နက်တိုက်','ရတနာတိုက်','နတ်ကွန်း','တံခါးမကြီး']
SIDES={'court':'နန်းတော်','plot':'လုပ်ကြံသူ','neutral':'သီးခြား'}
DEFAULTS=dict(lobby_seconds=180,night_seconds=90,day_seconds=150,vote_seconds=45,
              runoff_seconds=30,max_days=8,min_players=8,max_players=40,win_reward=15,
              participation_reward=3,anonymous=False,traitor=False,quests=True,shop=True,
              ghosts=True,events=True,curse=True,seal_cost=2,armor_cost=4,quest_coins=1,
              role_enabled={r:True for r in ROLES},
              role_uses={r:d['uses'] for r,d in ROLES.items() if d['uses']>0})
EVENTS=['normal','rain','festival','lantern']
ACTION_LOCATION={'protect':1,'guard':0,'heal':1,'cleanse':4,'armor':2,'block':5,
                 'poison':1,'forge':0,'mask':4,'curse':4,'link':0,'gift':3,
                 'seer':4,'verify':0,'spy':0,'listen':0,'track':5,'recover':0,'copy':4}
DAY_ACTIONS={'pardon','judge'}
COPYABLE={'track','listen','verify','heal','cleanse'}


def alive(s):return [p for p in s['players'] if p['alive']]
def player(s,uid):return next((p for p in s['players'] if p['id']==str(uid)),None)
def emit(s,dest,kind,**data):
    if kind=='evidence':
        public=s.setdefault('public_evidence',[])
        if data['eid'] not in public:public.append(data['eid'])
    s['events'].append(dict(dest=str(dest),kind=kind,**data))
def notice(s,p,code,**data):emit(s,p['id'],'notice',code=code,**data)


def role_pack(n,rng,settings):
    """Constrained role families; no duplicate unlimited full-faction scanners."""
    plot_n=max(2,n//4)
    neutral_n=1 if n<=12 else 2 if n<=20 else 3
    plot=['leader','blade']
    extra=['hider','forger','mask','spy']
    if n>=16:extra+=['poisoner']
    if settings['curse']:extra+=['curser']
    extra=[r for r in extra if settings['role_enabled'][r] and (r!='poisoner' or settings['role_enabled']['healer']) and (r!='curser' or settings['role_enabled']['cleanser'])]
    rng.shuffle(extra)
    plot+=extra[:plot_n-2]
    plot+=['blade']*max(0,plot_n-len(plot))
    neutrals=[r for r in ('jester','hunter','treasure','keeper','mimic','merchant') if settings['role_enabled'][r]]
    neutral=rng.sample(neutrals,min(neutral_n,len(neutrals)))
    neutral_n=len(neutral)
    court_n=n-plot_n-neutral_n
    court=['seer','doctor','detective']
    if 'poisoner' in plot:court+=['healer']
    if 'curser' in plot:court+=['cleanser']
    # Add breadth first. Strong control/defense roles unlock only for larger rooms.
    pool=['tracker','watcher','listener','scribe','diplomat','lamp','soldier']
    if n>=16:pool+=['guard','blocker','smith','minister','judge']
    pool=[r for r in pool if settings['role_enabled'][r]]
    rng.shuffle(pool)
    court+=pool[:max(0,court_n-len(court))]
    court+=['noble']*max(0,court_n-len(court))
    result=court[:court_n]+plot+neutral
    rng.shuffle(result)
    return result


def create(gid,cid,creator,settings,now):
    rules=dict(DEFAULTS,**settings)
    if rules['min_players']>rules['max_players']:raise ValueError('player_limits')
    return dict(id=gid,chat_id=cid,creator=str(creator),rules=rules,phase='lobby',epoch=0,
                day=0,deadline=now+rules['lobby_seconds'],players=[],events=[],evidence=[],
                votes={},actions={},attack={},ghost_votes={},links=[],event='normal',winner=None,
                awardees=[],updated=now,day_events=[],runoff=[],traitor_offer=None,armor_stock=0)


def join(s,uid,name):
    if s['phase']!='lobby':raise ValueError('closed')
    if player(s,uid):return
    if len(s['players'])>=s['rules']['max_players']:raise ValueError('full')
    s['players'].append(dict(id=str(uid),name=name[:40],alive=True,role=None,side=None,
                            coins=0,bag=[],published=[],uses=0,afk=0,participated=False,
                            active=False,armor=0,poison=None,cursed=False,private=[],
                            wins=False,departed=False,last_protect=None,gifts=[],relics=[],
                            quest=None,quest_done=False,item=None,copied=None))


def begin(s,now,rng):
    if s['phase']!='lobby':raise ValueError('closed')
    if len(s['players'])<s['rules']['min_players']:raise ValueError('not_enough')
    roles=role_pack(len(s['players']),rng,s['rules'])
    s['armor_stock']=max(1,len(s['players'])//10)
    for i,(p,r) in enumerate(zip(s['players'],roles),1):
        p.update(role=r,side=ROLES[r]['side'],number=i,uses=s['rules']['role_uses'].get(r,ROLES[r]['uses']),armor=int(r=='soldier'))
        if r in ('hunter','keeper'):
            candidates=[q for q in s['players'] if q is not p and ROLES[roles[s['players'].index(q)]]['side']=='court']
            p['objective']=rng.choice(candidates)['id']
    night(s,now,rng)


def night(s,now,rng):
    s['day']+=1;s['epoch']+=1;s['phase']='night';s['deadline']=now+s['rules']['night_seconds']
    s['actions']={};s['attack']={};s['votes']={};s['ghost_votes']={};s['links']=[];s['runoff']=[]
    s['event']=rng.choice(EVENTS) if s['rules']['events'] else 'normal'
    s['traitor_offer']=None
    if s['day']==2 and s['rules']['traitor']:
        choices=[p for p in alive(s) if p['role']=='noble']
        if choices:s['traitor_offer']=rng.choice(choices)['id']
    for p in s['players']:
        p['active']=False;p['published']=[];p['cursed']=False;p['item']=None;p['quest_done']=False
        p['private']=[];p['quest']=[rng.randint(11,39),rng.randint(11,39)]
    emit(s,s['chat_id'],'phase')
    for p in s['players']:emit(s,p['id'],'panel')


def role_action(p):return p['copied'] or ROLES[p['role']]['action']


def available_targets(s,p,action):
    live=alive(s)
    if action in ('watch','illuminate'):return [str(i) for i in range(len(LOCATIONS))]
    if action=='verify':return list(p['bag'])
    if action in ('recover','copy'):
        return [q['id'] for q in s['players'] if not q['alive'] and not q['departed'] and
                (action!='copy' or ROLES[q['role']]['action'] in COPYABLE)]
    if action=='mask':return [p['id']]
    if action=='hide':return [q['id'] for q in live if q['side']=='plot']
    if action in ('protect','guard'):
        return [q['id'] for q in live if (action!='guard' or q is not p) and q['id']!=p['last_protect']
                and (q is not p or not p.get('self_protected'))]
    if action=='gift':return [q['id'] for q in live if q is not p and q['id'] not in p['gifts']]
    if action=='armor':return [q['id'] for q in live if not q['armor']]
    if action=='search':return []
    return [q['id'] for q in live if q is not p]


def act(s,uid,kind,value):
    p=player(s,uid)
    if not p:raise ValueError('not_player')
    value=str(value)
    if kind=='ghost':
        if p['alive'] or p['departed'] or not s['rules']['ghosts'] or s['phase']!='night':raise ValueError('unavailable')
        if value not in map(str,range(len(LOCATIONS))):raise ValueError('target')
        s['ghost_votes'][p['id']]=value;return
    if not p['alive']:raise ValueError('dead')
    if kind=='vote':
        if s['phase'] not in ('vote','runoff'):raise ValueError('unavailable')
        q=player(s,value)
        if value!='skip' and (not q or not q['alive'] or q is p):raise ValueError('target')
        if s['phase']=='runoff' and value!='skip' and value not in s['runoff']:raise ValueError('target')
        s['votes'][p['id']]=value
    elif kind in ('pardon','judge'):
        if s['phase']!='day' or role_action(p)!=kind or p['uses']==0:raise ValueError('unavailable')
        if value not in available_targets(s,p,kind):raise ValueError('target')
        s['actions'][p['id']]=dict(action=kind,target=value,loc=0)
    elif kind=='publish':
        if s['phase']!='day' or value not in p['bag'] or value in p['published']:raise ValueError('unavailable')
        if len(p['published'])>= (1 if p['cursed'] else 3):raise ValueError('publish_limit')
        e=next(e for e in s['evidence'] if e['id']==value)
        p['published'].append(value);emit(s,s['chat_id'],'evidence',eid=e['id'],owner=p['id'])
    elif kind=='quest':
        if s['phase']!='night' or not s['rules']['quests'] or p['quest_done']:raise ValueError('unavailable')
        if value!=str(sum(p['quest'])):raise ValueError('wrong')
        p['quest_done']=True;p['coins']=min(8,p['coins']+s['rules']['quest_coins'])
    elif kind=='buy':
        if s['phase']!='day' or not s['rules']['shop'] or value not in ('seal','armor') or p['item']:raise ValueError('unavailable')
        cost=s['rules']['seal_cost'] if value=='seal' else s['rules']['armor_cost']
        if p['coins']<cost:raise ValueError('coins')
        if value=='armor' and (p['armor'] or p.get('bought_armor') or s['armor_stock']<=0):raise ValueError('unavailable')
        if value=='seal' and (not p['bag'] or p.get('seal_day')==s['day']):raise ValueError('unavailable')
        p['coins']-=cost;p['item']=value
        if value=='armor':p['armor']=1;p['bought_armor']=True;s['armor_stock']-=1
        else:
            p['seal_day']=s['day'];e=next(e for e in s['evidence'] if e['id']==p['bag'][-1])
            notice(s,p,'verified',eid=e['id'],fake=e['fake'])
    elif kind=='escape':
        if s['phase']!='day' or p['role']!='treasure' or len(p['relics'])<3:raise ValueError('unavailable')
        p['wins']=True;p['alive']=False;p['departed']=True;emit(s,s['chat_id'],'escaped',uid=p['id'])
    elif kind=='traitor':
        if s['phase']!='night' or s['traitor_offer']!=p['id'] or value not in ('yes','no'):raise ValueError('unavailable')
        s['traitor_offer']=None
        if value=='yes':
            p['side']='plot';p['role']='blade';p['uses']=-1
            # No faction information is delivered until the completed night.
            p['turned']=True;notice(s,p,'turned')
    elif kind=='attack':
        if s['phase']!='night' or p['side']!='plot':raise ValueError('unavailable')
        q=player(s,value)
        if value!='skip' and (not q or not q['alive'] or q['side']=='plot'):raise ValueError('target')
        s['attack'][p['id']]=value
    elif kind in ('loc','ability','skip'):
        if s['phase']!='night':raise ValueError('unavailable')
        a=s['actions'].setdefault(p['id'],dict(action='search',loc=None,target=None))
        if kind=='loc':
            if value not in map(str,range(len(LOCATIONS))):raise ValueError('target')
            a.update(action='search',loc=int(value),target=None)
        elif kind=='skip':a.update(action='search',loc=None,target=None)
        else:
            action=role_action(p)
            if action in DAY_ACTIONS or action=='search' or p['uses']==0:raise ValueError('unavailable')
            if value not in available_targets(s,p,action):raise ValueError('target')
            a.update(action=action,target=value,loc=int(value) if action in ('watch','illuminate') else ACTION_LOCATION.get(action,0))
    else:raise ValueError('unavailable')
    p['active']=True;p['participated']=True


def evidence(s,loc,subject,fake=False):
    e=dict(id=str(len(s['evidence'])+1),day=s['day'],loc=loc,subject=subject,fake=fake)
    s['evidence'].append(e);return e


def die(s,p,cause):
    if not p['alive']:return
    p['alive']=False
    if cause=='vote':
        if p['role']=='jester':p['wins']=True
        for q in s['players']:
            if q['role']=='hunter' and q.get('objective')==p['id'] and q['alive']:q['wins']=True
    else:
        for q in s['players']:
            if q['role']=='hunter' and q.get('objective')==p['id']:q['survive_objective']=True
    emit(s,s['chat_id'],'death',uid=p['id'],cause=cause,side=p['side'])


def resolve_night(s,rng):
    living=alive(s)[:];actions=s['actions'];blocked=set()
    for p in living:
        a=actions.get(p['id'],{})
        if a.get('action')=='block':blocked.add(a['target'])
    active={uid:a for uid,a in actions.items() if uid not in blocked and player(s,uid) in living}
    for p in living:
        if p['id'] in blocked:notice(s,p,'blocked')
    hidden={a['target'] for a in active.values() if a['action']=='hide'}
    masked={uid for uid,a in active.items() if a['action']=='mask'}
    protect={};guards={};healed=set();cleaned=set();cursed=set()
    for p in living:
        a=active.get(p['id'])
        if not a:continue
        action=a['action'];t=a.get('target');q=player(s,t)
        if action!='search' and p['uses']>0:p['uses']-=1
        if p['copied'] and action==p['copied']:p['copied']=None
        if action in ('protect','guard'):
            p['last_protect']=t
            if t==p['id']:p['self_protected']=True
            if action=='protect':protect[t]=True
            else:guards.setdefault(t,[]).append(p)
        elif action=='heal':healed.add(t)
        elif action=='cleanse':cleaned.add(t)
        elif action=='curse':cursed.add(t)
        elif action=='armor' and q:q['armor']=1
        elif action=='poison' and q and q['poison'] is None:q['poison']=s['day']+1;notice(s,q,'poisoned')
        elif action=='forge':evidence(s,a['loc'],t,True)
        elif action=='link' and q:s['links'].append([p['id'],t])
        elif action=='gift' and q:
            if t not in p['gifts']:p['gifts'].append(t);q['coins']=min(8,q['coins']+2);notice(s,q,'gift')
        elif action=='copy' and q:
            p['copied']=ROLES[q['role']]['action'];p['uses']=1;notice(s,p,'copied',action=p['copied'])
    # Family attack is one action, even with many assassins.
    attackers=[p for p in living if p['side']=='plot']
    ballots={p['id']:s['attack'].get(p['id']) for p in attackers}
    ballots={uid:t for uid,t in ballots.items() if t and t!='skip' and player(s,t) in living and player(s,t)['side']!='plot'}
    if ballots:
        counts=Counter(ballots.values());top=max(counts.values());targets=sorted(t for t,c in counts.items() if c==top)
        leader=next((p for p in attackers if p['role']=='leader'),None)
        target=ballots.get(leader['id']) if leader else None
        if target not in targets:target=targets[0]
        executor=sorted(attackers,key=lambda p:(p['role']!='blade',p['number']))[0]
        if executor['id'] not in blocked:
            # Attack leaves a real trace in the weapon store, regardless of investigation location.
            if executor['id'] not in hidden:evidence(s,2,executor['id'])
            q=player(s,target)
            if protect.get(target):notice(s,q,'protected')
            elif guards.get(target):die(s,sorted(guards[target],key=lambda p:p['number'])[0],'guard')
            elif q['armor']:q['armor']-=1;notice(s,q,'protected')
            else:die(s,q,'attack')
    for p in living:
        if p['id'] in healed:p['poison']=None
        if p['poison'] is not None and p['poison']<=s['day']:die(s,p,'poison');p['poison']=None
        p['cursed']=p['id'] in cursed and p['id'] not in cleaned
    for uid,a in active.items():
        if a['loc'] is not None and uid not in hidden:evidence(s,a['loc'],uid)
    today=[e for e in s['evidence'] if e['day']==s['day']]
    for p in living:
        a=active.get(p['id'],{});action=a.get('action');q=player(s,a.get('target'))
        if action=='seer' and q:notice(s,p,'side',uid=q['id'],side='court' if q['id'] in masked else q['side'])
        elif action=='spy' and q:notice(s,p,'role_group',uid=q['id'],action=role_action(q))
        elif action=='track' and q:
            qa=active.get(q['id'],{});loc=qa.get('loc') if q['id'] not in hidden else None
            notice(s,p,'location',uid=q['id'],loc=loc)
        elif action=='watch':
            visitors=sorted({e['subject'] for e in today if e['loc']==a['loc'] and not e['fake']},key=lambda u:player(s,u)['number'])
            notice(s,p,'visitors',loc=a['loc'],uids=visitors[:3])
        elif action=='listen' and q:notice(s,p,'used',uid=q['id'],used=active.get(q['id'],{}).get('action','search')!='search' or q['id'] in ballots)
        elif action=='verify':
            e=next(e for e in s['evidence'] if e['id']==a['target']);notice(s,p,'verified',eid=e['id'],fake=e['fake'])
        elif action=='recover' and q and q['bag']:
            eid=q['bag'][-1]
            if eid not in p['bag']:p['bag'].append(eid)
            notice(s,p,'found',eid=eid)
        elif action=='illuminate':
            pool=[e for e in today if e['loc']==a['loc'] and not e['fake']]
            if pool:emit(s,s['chat_id'],'evidence',eid=rng.choice(pool)['id'],owner=p['id'])
        if a.get('loc') is not None:
            pool=[e for e in today if e['loc']==a['loc'] and e['subject']!=p['id']]
            chance=.85 if p['role']=='noble' else .65
            if s['event']=='rain':chance*=.65
            if s['event']=='lantern':chance=1
            if pool and rng.random()<chance:
                e=rng.choice(pool);p['bag'].append(e['id']);notice(s,p,'found',eid=e['id'])
            else:notice(s,p,'empty')
            if p['role']=='treasure' and a['loc'] not in p['relics']:p['relics'].append(a['loc'])
        if p.get('turned'):
            p['turned']=False;notice(s,p,'allies')
    if s['rules']['ghosts'] and s['ghost_votes']:
        counts=Counter(s['ghost_votes'].values());loc=int(sorted(counts,key=lambda k:(-counts[k],int(k)))[0])
        pool=[e for e in today if e['loc']==loc and not e['fake']]
        if pool:emit(s,s['chat_id'],'evidence',eid=rng.choice(pool)['id'],owner=None)
    s['actions']={}


def check_win(s):
    live=alive(s);plots=sum(p['side']=='plot' for p in live)
    if not live:s['winner']='draw'
    elif not plots:s['winner']='court'
    elif plots>=len(live)-plots:s['winner']='plot'
    else:return False
    finish(s);return True


def finish(s):
    if s['phase'] in ('finished','cancelled'):return
    s['phase']='finished';s['epoch']+=1
    for p in s['players']:
        if p['side']=='neutral':
            r=p['role']
            if r=='keeper':p['wins']=bool(player(s,p.get('objective')) and player(s,p['objective'])['alive'])
            elif r=='merchant':p['wins']=p['alive'] and len(set(p['gifts']))>=3
            elif r=='mimic' or r=='hunter' and p.get('survive_objective'):p['wins']=p['alive']
        elif p['side']==s['winner']:p['wins']=True
        if p['participated'] and not p.get('forfeit'):
            s['awardees'].append(dict(uid=p['id'],points=s['rules']['win_reward'] if p['wins'] else s['rules']['participation_reward']))
    emit(s,s['chat_id'],'result')


def eliminate_vote(s,target):
    p=player(s,target)
    pardon=next((q for q in alive(s) if s['actions'].get(q['id'],{}).get('action')=='pardon' and s['actions'][q['id']]['target']==target),None)
    if pardon and pardon['uses']:
        pardon['uses']-=1;emit(s,s['chat_id'],'pardon',uid=pardon['id'],target=target);return
    die(s,p,'vote')
    # Coins reward correct public votes after faction reveal, not the hidden role.
    if p['side']=='plot':
        for uid,t in s['votes'].items():
            if t==target:player(s,uid)['coins']=min(8,player(s,uid)['coins']+1)


def advance(s,now,rng):
    if s['phase'] in ('finished','cancelled') or now<s['deadline']:return False
    phase=s['phase']
    if phase=='lobby':
        if len(s['players'])<s['rules']['min_players']:
            s['phase']='cancelled';s['epoch']+=1;emit(s,s['chat_id'],'cancelled');return True
        begin(s,now,rng);return True
    if phase=='night':
        resolve_night(s,rng)
        if s['event']=='festival':
            for p in alive(s):p['coins']=min(8,p['coins']+1)
        if check_win(s):return True
        s['phase']='day';s['epoch']+=1;s['deadline']=now+s['rules']['day_seconds']+(len(alive(s))*5 if s['rules']['anonymous'] else 30 if len(alive(s))>20 else 0)
        emit(s,s['chat_id'],'phase')
        for p in s['players']:emit(s,p['id'],'panel')
    elif phase=='day':
        s['phase']='vote';s['epoch']+=1;s['deadline']=now+s['rules']['vote_seconds'];s['votes']={}
        emit(s,s['chat_id'],'phase')
    else:
        counts=Counter(t for uid,t in s['votes'].items() if player(s,uid)['alive'] and
                       (t=='skip' or player(s,t) and player(s,t)['alive']))
        skip=counts.pop('skip',0);top=max(counts.values(),default=0)
        targets=sorted(t for t,c in counts.items() if c==top) if top>skip else []
        emit(s,s['chat_id'],'votes',votes=dict(s['votes']))
        if len(targets)>1 and phase=='vote':
            s['phase']='runoff';s['epoch']+=1;s['runoff']=targets;s['votes']={};s['deadline']=now+s['rules']['runoff_seconds']
            emit(s,s['chat_id'],'phase');return True
        if len(targets)>1:
            judges=[p for p in alive(s) if p['uses'] and s['actions'].get(p['id'],{}).get('action')=='judge' and s['actions'][p['id']]['target'] in targets]
            if judges:
                j=sorted(judges,key=lambda p:p['number'])[0];j['uses']-=1;targets=[s['actions'][j['id']]['target']]
                emit(s,s['chat_id'],'judge',uid=j['id'])
        if len(targets)==1:eliminate_vote(s,targets[0])
        else:emit(s,s['chat_id'],'no_execution')
        for p in alive(s)[:]:
            p['afk']=0 if p['active'] else p['afk']+1
            if p['afk']>=2:
                p['forfeit']=True;p['departed']=True;die(s,p,'afk')
            elif p['afk']==1:notice(s,p,'afk')
        if check_win(s):return True
        if s['day']>=s['rules']['max_days']:s['winner']='draw';finish(s)
        else:night(s,now,rng)
    return True


def cancel(s):
    if s['phase'] not in ('finished','cancelled'):
        s['phase']='cancelled';s['epoch']+=1;s['awardees']=[];emit(s,s['chat_id'],'cancelled')
