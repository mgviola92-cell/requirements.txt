"""Telegram media payloads stored without message forwarding or executable templates."""
import html
import re

KINDS={'text','photo','voice','audio','video','animation','document','sticker','video_note'}
FIELDS={'name','user','group','args'}
NAME=re.compile(r'^[a-z][a-z0-9_]{1,31}$')


def capture(m):
    kind=m.content_type
    if kind not in KINDS:raise ValueError('unsupported')
    data={'kind':kind}
    if kind=='text':data['text']=getattr(m,'html_text',None) or html.escape(m.text or '')
    else:
        media=getattr(m,kind)
        if kind=='photo':media=media[-1]
        data['file_id']=media.file_id
        if kind not in ('sticker','video_note'):data['caption']=getattr(m,'html_caption',None) or html.escape(m.caption or '')
    validate(data);return data


def validate(p):
    if not isinstance(p,dict) or p.get('kind') not in KINDS:raise ValueError('unsupported')
    allowed={'kind','text'} if p['kind']=='text' else {'kind','file_id','caption'}
    if set(p)-allowed:raise ValueError('unsupported')
    key='text' if p['kind']=='text' else 'file_id'
    if not isinstance(p.get(key),str) or not p[key].strip():raise ValueError('empty')
    if len(p.get('text',''))>3500 or len(p.get('caption',''))>900 or len(p.get('file_id',''))>500:raise ValueError('too_long')
    if p['kind']=='text' or p.get('caption'):
        from core.customization import MarkupValidator
        for value in (p.get('text',''),p.get('caption','')):
            parser=MarkupValidator();parser.feed(value);parser.finish()
    return p


def substitute(p,fields):
    out=dict(p)
    for key in ('text','caption'):
        if key in out:
            out[key]=re.sub(r'\{(name|user|group|args)\}',lambda m:html.escape(str(fields.get(m.group(1),''))),out[key])
            out[key]=out[key][:3500 if key=='text' else 900]
    validate(out);return out


def deliver(bot,cid,p):
    validate(p)
    if p['kind']=='text':return bot.send_message(cid,p['text'],parse_mode='HTML')
    kwargs={'caption':p.get('caption',''),'parse_mode':'HTML'} if p['kind'] not in ('sticker','video_note') else {}
    return getattr(bot,'send_'+p['kind'])(cid,p['file_id'],**kwargs)
