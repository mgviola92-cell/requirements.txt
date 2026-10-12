"""Serializable Draw & Guess rules, activity-independent explicit group game."""
import re
import unicodedata

DEFAULTS=dict(lobby_seconds=120,draw_seconds=90,guess_seconds=90,min_players=2,max_players=12,
              rounds=5,winner_reward=10,drawer_reward=5)
WORDS=[
 ('ကြောင်',['ကြောင်လေး']),('ခွေး',['ခွေးလေး']),('ငါး',[]),('ဆင်',[]),('ယုန်',[]),('လိပ်',[]),
 ('ကြက်',[]),('ငှက်',[]),('မြွေ',[]),('လိပ်ပြာ',[]),('နေ',[]),('လ',[]),('ကြယ်',[]),
 ('အိမ်',[]),('သစ်ပင်',[]),('ပန်း',[]),('တောင်',[]),('မြစ်',[]),('ပင်လယ်',[]),
 ('ကား',[]),('စက်ဘီး',[]),('လေယာဉ်',[]),('လှေ',[]),('ရထား',[]),('ထီး',[]),
 ('ဖုန်း',[]),('ကွန်ပျူတာ',[]),('စာအုပ်',[]),('ခဲတံ',[]),('နာရီ',[]),('မျက်မှန်',[]),
 ('ဖိနပ်',[]),('ဦးထုပ်',[]),('အိတ်',[]),('ကုလားထိုင်',[]),('စားပွဲ',[]),('သော့',[]),
 ('မီးအိမ်',[]),('တံခါး',[]),('ဘောလုံး',[]),('စွန်',[]),('ဂစ်တာ',[]),('ဒရမ်',[]),
 ('ကိတ်မုန့်',['ကိတ်']),('ရေခဲမုန့်',[]),('ငှက်ပျောသီး',[]),('ဖရဲသီး',[]),('ပန်းသီး',[]),
 ('နာနတ်သီး',[]),('ကြက်ဥ',[]),('မုန့်ဟင်းခါး',[]),('ခေါက်ဆွဲ',[]),('လက်ဖက်ရည်',[]),
 ('ကော်ဖီ',[]),('ပီဇာ',[]),('ဟမ်ဘာဂါ',[]),('စတော်ဘယ်ရီ',[]),('ချယ်ရီ',[]),
 ('နှင်းလူ',['နှင်းလူသား']),('သက်တံ',['သက်တံ့']),('မီးတောင်',[]),('ရဲတိုက်',[]),
 ('ရေတံခွန်',[]),('တံတား',[]),('မီးရထားဘူတာ',['ဘူတာ']),('မီးသတ်ကား',[]),
 ('အာကာသယာဉ်',[]),('ပင့်ကူ',[]),('ပျား',[]),('မိကျောင်း',[]),('ဝက်',[]),('ကျား',[]),
 ('ခြင်္သေ့',[]),('သစ်ကုလားအုတ်',[]),('ပန်ဒါ',[]),('ပင်ဂွင်း',[]),('ဖား',[]),
 ('ရေခွက်',['ခွက်']),('ဇွန်း',[]),('ခက်ရင်း',[]),('ပန်းကန်',[]),('ဒယ်အိုး',[]),
 ('သွားတိုက်တံ',[]),('ဆပ်ပြာ',[]),('ဖြီး',[]),('မိုက်ခရိုဖုန်း',[]),('ကင်မရာ',[]),
 ('လက်စွပ်',[]),('လည်ဆွဲ',[]),('ပူဖောင်း',[]),('လက်ဆောင်',[]),('ရတနာသေတ္တာ',[]),
 ('အလံ',[]),('မီးပွိုင့်',[]),('လှေကား',[]),('ရေတွင်း',[]),('ပန်ကာ',[]),('တီဗီ',[]),
 ('ရေခဲသေတ္တာ',[]),('မီးဖို',[]),('ကတ်ကြေး',[]),('စက္ကူလှေ',[]),('စက္ကူလေယာဉ်',[]),
 ('နတ်သမီး',[]),('နဂါး',[]),('ဒိုင်နိုဆော',[]),('ရုပ်တု',[]),('မျက်နှာဖုံး',[]),
 ('ကြက်တူရွေး',[]),('ဝေလငါး',[]),('ငါးမန်း',[]),('ပင်လယ်ကြယ်',[]),('ကဏန်း',[]),
 ('ခရု',[]),('ပုရွက်ဆိတ်',[]),('သိုး',[]),('ဆိတ်',[]),('နွား',[]),('မြင်း',[]),
 ('နေကြာပန်း',[]),('နှင်းဆီပန်း',[]),('အုန်းပင်',[]),('မှို',[]),('သရက်သီး',[]),
 ('လိမ္မော်သီး',[]),('သံပုရာသီး',[]),('ငရုတ်သီး',[]),('မုန်လာဥနီ',[]),('အာလူး',[])]


from data.draw_words import EXTRA, LEVELS
_original={w for w,_ in WORDS}
WORDS += [(w,a) for w,a in EXTRA if w not in _original]

def word_level(word):
    # Existing owner-created words stay playable without mandatory metadata.
    return LEVELS.get(word,1)

def choose_word(choices,players,rng):
    weights=(90,10,0) if players<=4 else (45,45,10) if players<=7 else (20,45,35)
    tiers={level:[item for item in choices if word_level(item[0])==level] for level in (1,2,3)}
    available=[level for level in tiers if tiers[level] and weights[level-1]]
    if not available:return rng.choice(choices)
    level=rng.choices(available,weights=[weights[level-1] for level in available],k=1)[0]
    return rng.choice(tiers[level])


def normalize(value):return re.sub(r'[\s\u200b\u200c\u200d]+','',unicodedata.normalize('NFC',value).casefold().strip())
def player(s,uid):return next((p for p in s['players'] if p['id']==str(uid)),None)
def event(s,kind,**data):s['events'].append(dict(kind=kind,**data))
def create(gid,cid,uid,rules,now):
    return dict(id=gid,chat_id=cid,creator=str(uid),rules=dict(DEFAULTS,**rules),phase='lobby',epoch=0,
                deadline=now+rules.get('lobby_seconds',120),round=0,players=[],used=[],events=[],
                drawer=None,word=None,aliases=[],image=None,ticket=None,awards=[],updated=now,card=None)
def join(s,uid,label):
    if s['phase']!='lobby':raise ValueError('closed')
    if player(s,uid):return
    if len(s['players'])>=s['rules']['max_players']:raise ValueError('full')
    s['players'].append(dict(id=str(uid),name=label[:40],score=0,active=True))
def begin(s,now,rng,words=WORDS):
    if s['phase']!='lobby':raise ValueError('closed')
    if len(s['players'])<s['rules']['min_players']:raise ValueError('minimum')
    rng.shuffle(s['players']);s['rules']['rounds']=max(s['rules']['rounds'],len(s['players']))
    next_round(s,now,rng,words)
def next_round(s,now,rng,words=WORDS):
    live=[p for p in s['players'] if p['active']]
    if s['round']>=s['rules']['rounds'] or len(live)<2:
        finish(s);return
    s['round']+=1;s['epoch']+=1;s['phase']='draw';s['deadline']=now+s['rules']['draw_seconds']
    s['drawer']=live[(s['round']-1)%len(live)]['id'];s['image']=None;s['ticket']=None;s['card']=None
    choices=[(w,a) for w,a in words if w not in s['used']]
    if not choices:s['used']=[];choices=list(words)
    s['word'],s['aliases']=choose_word(choices,len(live),rng);s['used'].append(s['word'])
    event(s,'round');event(s,'drawer',uid=s['drawer'])
def submit(s,uid,now):
    if str(uid)!=s['drawer'] or s['phase'] not in ('draw','guess') or now>s['deadline']:raise ValueError('closed')
    if s['phase']=='draw':s['phase']='guess';s['deadline']=now+s['rules']['guess_seconds']
    event(s,'image')
def guess(s,uid,value,now,rng,words=WORDS):
    p=player(s,uid)
    if not p or not p['active'] or p['id']==s['drawer'] or s['phase']!='guess' or now>s['deadline']:return False
    if normalize(value) not in {normalize(v) for v in [s['word']]+s['aliases']}:return False
    p['score']+=10;player(s,s['drawer'])['score']+=5
    key=f"{s['id']}:{s['round']}"
    s['awards']+=[dict(key=key+':guess',uid=p['id'],points=s['rules']['winner_reward']),dict(key=key+':draw',uid=s['drawer'],points=s['rules']['drawer_reward'])]
    event(s,'correct',uid=p['id'],word=s['word']);next_round(s,now,rng,words);return True

def finish(s):
    if s['phase'] in ('finished','cancelled'):return
    s['phase']='finished';s['epoch']+=1;s['ticket']=None;event(s,'result')
def cancel(s):
    if s['phase'] in ('finished','cancelled'):return
    s['phase']='cancelled';s['epoch']+=1;s['ticket']=None;event(s,'cancelled')
def advance(s,now,rng,words=WORDS):
    if s['phase'] in ('finished','cancelled') or now<s['deadline']:return
    if s['phase']=='lobby':
        if len(s['players'])<s['rules']['min_players']:cancel(s)
        else:begin(s,now,rng,words)
    else:event(s,'timeout',word=s['word']);next_round(s,now,rng,words)
