"""Bounded feed parsing and conservative duplicate detection; no truth assertions.
Only attributed feed headlines are used automatically. Owner-written briefs can
replace them; full articles are neither copied nor purportedly summarized.
"""
from core.traffic_meter import record as record_traffic
import urllib.error
import hashlib,html,re,unicodedata,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from difflib import SequenceMatcher

MAX_BYTES=1500000
MYANMAR=re.compile(r'\b(?:myanmar|burma|burmese|yangon|mandalay|naypyidaw|rohingya|rakhine|kachin|karenni|chin state|shan state)\b|မြန်မာ|ရန်ကုန်|မန္တလေး|ရခိုင်|ကချင်|ကရင်|စစ်ကိုင်း',re.I)
CORRECTION=re.compile(r'\bcorrection|\bcorrected|ပြင်ဆင်ချက်|မှားယွင်းဖော်ပြ',re.I)
def plain(value):
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>','',str(value or '')))).strip()
def normalized(value):
    return re.sub(r'[\s\W_]+','',unicodedata.normalize('NFC',value).casefold())
def date(value):
    if not value:return None
    try:result=parsedate_to_datetime(value)
    except (ValueError,TypeError,OverflowError):
        try:result=datetime.fromisoformat(value.strip().replace('Z','+00:00'))
        except (ValueError,TypeError):return None
    return result.replace(tzinfo=timezone.utc).timestamp() if result.tzinfo is None else result.timestamp()
def field(item,names):
    for child in item:
        if child.tag.split('}')[-1] in names and child.text:return child.text
    return ''
def safe_url(value):
    p=urllib.parse.urlsplit(value)
    return bool(p.scheme in ('http','https') and p.hostname and not p.username and not p.password)
def excerpt(value,title=''):
    """Short attributed feed extract, never a fabricated summary or full article."""
    value=re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '',str(value or ''),flags=re.I|re.S)
    value=plain(value)
    if not value or normalized(value)==normalized(title):return ''
    words=value.split()
    clipped=' '.join(words[:100])
    clipped=clipped[:1200]
    return clipped.rstrip()+('…' if len(clipped)<len(value) else '')

def parse(raw,source,now):
    if len(raw)>MAX_BYTES:raise ValueError('feed too large')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsafe XML')
    root=ET.fromstring(raw)
    if root.tag.split('}')[-1] not in ('rss','feed','RDF'):raise ValueError('not RSS/Atom')
    accepted=[];missing=0
    for item in [n for n in root.iter() if n.tag.split('}')[-1] in ('item','entry')][:50]:
        title=plain(field(item,('title',)))
        url=field(item,('link',))
        if not url:
            for child in item:
                if child.tag.split('}')[-1]=='link' and child.get('rel','alternate')=='alternate':url=child.get('href','');break
        stamp=date(field(item,('pubDate','published','date')))
        if stamp is None:missing+=1;continue
        if not 8<=len(title)<=400 or not safe_url(url) or stamp>now+300 or stamp<now-30*86400:continue
        if not source['local'] and not MYANMAR.search(title):continue
        if source['id'] in ('reuters','ap'):
            credited=plain(field(item,('source',)))
            if source['id']=='reuters' and credited.casefold()!='reuters':continue
            if source['id']=='ap' and credited.casefold() not in ('associated press','ap news','apnews'):continue
        key=hashlib.sha256(url.encode()).hexdigest()[:24]
        accepted.append({'key':key,'source':source['id'],'family':source['family'],'name':source['name'],'title':title,'url':url,'published':stamp,'excerpt':excerpt(field(item,('description','summary')) or field(item,('encoded','content')),title),'brief':'','revision':hashlib.sha256(title.encode()).hexdigest()[:16],'correction':bool(CORRECTION.search(title))})
    return accepted,missing

def fetch(source,now,validators=None):
    headers={'User-Agent':'MyanmarNewsDigest/1.0 (RSS reader)','Accept':'application/rss+xml, application/atom+xml, application/xml,text/xml'}
    if validators:
        if validators.get('etag'):headers['If-None-Match']=validators['etag']
        if validators.get('modified'):headers['If-Modified-Since']=validators['modified']
    record_traffic('news_payload',source.get('id','feed'),sent=sum(len(k.encode())+len(str(v).encode()) for k,v in headers.items()))
    request=urllib.request.Request(source['url'],headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=8) as response:
            if getattr(response,'status',None)==304:return None,0
            raw=response.read(MAX_BYTES+1)
            record_traffic('news_payload',source.get('id','feed'),received=len(raw),calls=0)
            result=parse(raw,source,now)
            if validators is not None:
                validators.clear()
                validators.update(etag=response.headers.get('ETag'),modified=response.headers.get('Last-Modified'))
            return result
    except urllib.error.HTTPError as exc:
        if exc.code==304:exc.close();return None,0
        raise

def similar(a,b):
    if abs(a['published']-b['published'])>24*3600:return False
    x,y=normalized(a['title']),normalized(b['title'])
    # Conflicting numbers cannot be collapsed as an agreeing event.
    if set(re.findall(r'[0-9၀-၉]+',a['title']))!=set(re.findall(r'[0-9၀-၉]+',b['title'])):return False
    return x==y or min(len(x),len(y))>=30 and SequenceMatcher(None,x,y,autojunk=False).ratio()>=.90

def clusters(items):
    result=[]
    for item in sorted(items,key=lambda x:x['published'],reverse=True):
        group=next((g for g in result if similar(g[0],item)),None)
        if group is None:result.append([item])
        else:group.append(item)
    return result

def families(group):
    # A syndicated wire item is not an independent corroboration.
    result=set()
    for item in group:
        title=item['title'].casefold()
        family='reuters' if re.search(r'\breuters\b',title) else 'ap' if '(ap)' in title else item['family']
        result.add(family)
    return result

def headline(item):
    # Translation is deliberately not automatic for sensitive news: a failed
    # paraphrase must not alter people, places, casualty figures or attribution.
    return item.get('brief') or item['title']
