"""Readable Burmese quiz wording, bounded translation, stable answer identity."""
import html
import json
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor,TimeoutError
from collections import OrderedDict

_CACHE=OrderedDict()
_LOCK=threading.RLock()
PREFIX=re.compile(r'^(?:ရွေးပါ|မှန်တဲ့အဖြေက ဘာလဲ|မြန်မြန်ဖြေပါ)\s*[—:၊]\s*|^(?:General Quiz|သိပ္ပံမေးခွန်း|ကွန်ပျူတာမေးခွန်း|အခြေခံဗဟုသုတ)\s*:\s*')
GLOSSARY={'Earth':'ကမ္ဘာ','Mars':'အင်္ဂါဂြိုဟ်','Venus':'သောကြာဂြိုဟ်','Jupiter':'ကြာသပတေးဂြိုဟ်','Saturn':'စနေဂြိုဟ်','Moon':'လ','Sun':'နေ','Oxygen':'အောက်ဆီဂျင်','Carbon dioxide':'ကာဗွန်ဒိုင်အောက်ဆိုဒ်','Hydrogen':'ဟိုက်ဒရိုဂျင်','Nitrogen':'နိုက်ထရိုဂျင်','Red':'အနီ','Blue':'အပြာ','Green':'အစိမ်း','Yellow':'အဝါ','White':'အဖြူ','Black':'အနက်','Heart':'နှလုံး','Lungs':'အဆုတ်','Kidney':'ကျောက်ကပ်','Brain':'ဦးနှောက်','Pacific Ocean':'ပစိဖိတ်သမုဒ္ဒရာ','Atlantic Ocean':'အတ္တလန္တိတ်သမုဒ္ဒရာ','Indian Ocean':'အိန္ဒိယသမုဒ္ဒရာ','Asia':'အာရှ','Europe':'ဥရောပ','Africa':'အာဖရိက','Antarctica':'အန္တာတိက','North America':'မြောက်အမေရိက','South America':'တောင်အမေရိက'}
PATTERNS=[
(r'What is the capital of (.+)\?',lambda x:f'{x} ၏ မြို့တော်က ဘယ်မြို့လဲ?'),
(r'Which currency is used in (.+)\?',lambda x:f'{x} တွင် အသုံးပြုသည့် ငွေကြေးက ဘာလဲ?'),
(r'On which continent is (.+)\?',lambda x:f'{x} က ဘယ်တိုက်တွင် တည်ရှိသလဲ?'),
(r'What is the calling code of (.+)\?',lambda x:f'{x} ၏ နိုင်ငံတကာ ဖုန်းခေါ်ဆိုမှုကုဒ်က ဘာလဲ?'),
(r'What is the atomic number of (.+)\?',lambda x:f'{x} ၏ အက်တမ်အမှတ်စဉ်က ဘယ်လောက်လဲ?'),
(r'What is the chemical symbol for (.+)\?',lambda x:f'{x} ၏ ဓာတုသင်္ကေတက ဘာလဲ?'),
(r'Who wrote (.+)\?',lambda x:f'{x} စာအုပ်ကို ဘယ်သူရေးသားခဲ့သလဲ?'),
(r'Who directed (.+)\?',lambda x:f'{x} ရုပ်ရှင်ကို ဘယ်သူဒါရိုက်တာလုပ်ခဲ့သလဲ?'),
(r'Who founded (.+)\?',lambda x:f'{x} ကို ဘယ်သူတည်ထောင်ခဲ့သလဲ?'),
(r'Who invented (.+)\?',lambda x:f'{x} ကို ဘယ်သူတီထွင်ခဲ့သလဲ?'),
(r'In what year was the book (.+) first published\?',lambda x:f'{x} စာအုပ်ကို ဘယ်နှစ်တွင် ပထမဆုံးထုတ်ဝေခဲ့သလဲ?'),
(r'Which language is listed for the book (.+)\?',lambda x:f'{x} စာအုပ်အတွက် မှတ်တမ်းတင်ထားသော ဘာသာစကားက ဘာလဲ?'),
(r"In which year was the research '(.+)' published\?",lambda x:f'{x} သုတေသနကို ဘယ်နှစ်တွင် ထုတ်ဝေခဲ့သလဲ?'),
(r"What exact publication date is recorded for '(.+)'\?",lambda x:f'{x} ၏ ထုတ်ဝေရက်အတိအကျက ဘယ်နေ့လဲ?'),
(r"What primary research topic is assigned to '(.+)'\?",lambda x:f'{x} အတွက် သတ်မှတ်ထားသော အဓိကသုတေသနအကြောင်းအရာက ဘာလဲ?'),
(r'What year does NASA\x27s catalog give for the image titled (.+)\?',lambda x:f'{x} ပုံအတွက် NASA မှတ်တမ်းတွင် ဖော်ပြထားသောနှစ်က ဘယ်နှစ်လဲ?'),
(r'Which NASA center is credited for the image titled (.+)\?',lambda x:f'{x} ပုံအတွက် ဖော်ပြထားသော NASA ဌာနက ဘယ်ဌာနလဲ?'),
]

def clean(text):
    value=unicodedata.normalize('NFC',html.unescape(str(text))).strip()
    while True:
        new=PREFIX.sub('',value).strip()
        if new==value:break
        value=new
    return value.replace('အောက်က sequence ကိုဆက်ပါ','အောက်ပါ ကိန်းစဉ်၏ နောက်ကိန်းကို ရွေးပါ').replace('Solar System','နေအဖွဲ့အစည်း').replace('မြန်မာ နိုင်ငံ','မြန်မာနိုင်ငံ')

def local_wording(text):
    value=clean(text)
    if value in GLOSSARY:return GLOSSARY[value]
    if re.search('[\u1000-\u109f]',value) or re.fullmatch(r'[\d\s.,%+−×÷*/()²³=?:-]+',value):return value
    for pattern,render in PATTERNS:
        match=re.fullmatch(pattern,value)
        if match:return render(match[1])
    match=re.fullmatch(r'What was the (.+) \((.+)\) in (.+) in (\d{4})\?',value)
    if match:
        metric,unit,country,year=match.groups()
        metric={'population':'လူဦးရေ','life expectancy':'ပျမ်းမျှမျှော်မှန်းသက်တမ်း','surface area':'မျက်နှာပြင်ဧရိယာ','GDP':'ပြည်တွင်းအသားတင်ထုတ်လုပ်မှုတန်ဖိုး'}.get(metric,metric)
        return f'{year} ခုနှစ်တွင် {country} ၏ {metric} ({unit}) က ဘယ်လောက်လဲ?'
    return None

def translate(text):
    original=clean(text);local=local_wording(original)
    if local is not None:return local
    with _LOCK:
        if original in _CACHE:
            _CACHE.move_to_end(original);return _CACHE[original]
    result=original
    try:
        url='https://api.mymemory.translated.net/get?'+urllib.parse.urlencode({'q':original,'langpair':'en|my'})
        with urllib.request.urlopen(url,timeout=3) as response:data=json.load(response)
        candidate=clean((data.get('responseData') or {}).get('translatedText') or '')
        if data.get('responseStatus')==200 and re.search('[\u1000-\u109f]',candidate) and not re.search(r'<[^>]+>|MYMEMORY|QUOTA|WARNING|INVALID',candidate,re.I) and len(candidate)<=350:
            # Number/date identity must survive translation.
            if set(re.findall(r'\d+(?:\.\d+)?',original))==set(re.findall(r'\d+(?:\.\d+)?',candidate)):
                result=candidate
    except (OSError,ValueError,TypeError):pass
    # Don't cache temporary failures, so a later round may recover.
    if result!=original:
        with _LOCK:
            _CACHE[original]=result
            if len(_CACHE)>1000:_CACHE.popitem(last=False)
    return result

def translate_question(question):
    result=dict(question);original_answers=[clean(a) for a in question['answers']]
    fields=[clean(question['question']),*original_answers]
    executor=ThreadPoolExecutor(max_workers=5)
    pending=[executor.submit(translate,v) for v in fields];deadline=time.monotonic()+4
    values=[]
    try:
        for original,future in zip(fields,pending):
            try:values.append(future.result(timeout=max(0,deadline-time.monotonic())))
            except Exception:values.append(original)
    finally:executor.shutdown(wait=False,cancel_futures=True)
    result['question']=values[0]
    answers=[]
    for original,translated in zip(original_answers,values[1:]):
        # Preserve names/technical terms alongside uncertain machine wording.
        if translated!=original and local_wording(original) is None:
            translated=f'{translated} ({original})'
        answers.append(translated if len(translated)<=160 else original)
    # Never let translation turn distinct choices into indistinguishable answers.
    if len({a.casefold() for a in answers})!=4:answers=original_answers
    result['answers']=answers
    return result
