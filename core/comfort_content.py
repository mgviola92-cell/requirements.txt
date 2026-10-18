"""Pure helpers for comfort content and Telegram custom-emoji preservation."""
import hashlib
import html
import re


EMOJI_KEY='cfg.features.comfort.emojis'


def encode_emojis(message):
    value=message.text or ''
    raw=value.encode('utf-16-le')
    replacements=[]
    for entity in getattr(message,'entities',None) or []:
        if entity.type=='custom_emoji' and str(entity.custom_emoji_id).isdigit():
            start,end=entity.offset*2,(entity.offset+entity.length)*2
            fallback=raw[start:end].decode('utf-16-le')
            replacements.append((start,end,'ce:'+str(entity.custom_emoji_id)+':'+fallback))
    for start,end,token in sorted(replacements,reverse=True):
        raw=raw[:start]+token.encode('utf-16-le')+raw[end:]
    return raw.decode('utf-16-le').strip()


def emoji_pair(token):
    match=re.fullmatch(r'ce:(\d{1,30}):(.{1,30})',token)
    if match:
        fallback=html.escape(match[2])
        return '<tg-emoji emoji-id="'+match[1]+'">'+fallback+'</tg-emoji>',fallback
    safe=html.escape(token[:40])
    return safe,safe


def body_hash(line):return hashlib.sha256(line.encode()).hexdigest()


def choose_line(lines,used,rng):
    """No identical text even when owner customizations duplicate two entries."""
    unique={}
    for key,line in lines:
        if line.strip():unique.setdefault(body_hash(line), (key,line))
    choices=[(key,line,digest) for digest,(key,line) in unique.items() if digest not in used]
    return rng.choice(choices) if choices else None


def render_line(target,name,line,emoji=''):
    label=html.escape(name[:40])
    rendered=line.replace('{name}',name[:40])
    return '<a href="tg://user?id='+str(int(target))+'">'+label+'</a> '+html.escape(rendered[:500])+(' '+emoji if emoji else '')
