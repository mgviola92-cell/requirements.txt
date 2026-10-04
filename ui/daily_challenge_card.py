"""Compact daily group mission card; optional user-owned assets/daily_challenge artwork."""
from io import BytesIO
from pathlib import Path
import hashlib
from PIL import Image, ImageDraw, ImageFont, ImageOps
from database.daily_challenge import missions_for, game_progress
ROOT=Path(__file__).resolve().parent.parent
W,H=900,510

def _font(sz):
    for p in (ROOT/'assets/fonts/myanmar.ttf',Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')):
        if p.exists():return ImageFont.truetype(str(p),sz)
    return ImageFont.load_default()

def card(stats):
    from core.asset_manager import list_images
    im=Image.new('RGB',(W,H),'#101c30')
    try:
        images=list_images('daily_challenge',recursive=True)
        if images:
            k=int(hashlib.sha256(str(stats['day']).encode()).hexdigest(),16)%len(images)
            im=ImageOps.fit(Image.open(images[k]).convert('RGB'),(W,H),method=Image.Resampling.LANCZOS)
    except Exception:pass
    im=im.convert('RGBA')
    im=Image.alpha_composite(im,Image.new('RGBA',(W,H),(5,13,28,177)))
    d=ImageDraw.Draw(im,'RGBA')
    d.rounded_rectangle((20,18,880,494),radius=24,outline=(80,220,220,190),width=2)
    d.rounded_rectangle((39,34,861,105),radius=15,fill=(9,19,38,215))
    d.text((60,48),'DAILY CHALLENGE',font=_font(31),fill='#f8fbff')
    double=int(hashlib.sha256(f"{stats.get('chat_id')}:{stats['day']}:double".encode()).hexdigest(),16)%7==0
    d.text((835,67),'x2 DAY' if double else '3 MISSIONS',font=_font(19),anchor='rm',fill='#facc72' if double else '#65e8e6')
    for i,(kind,need,unique,personal,(lo,hi)) in enumerate(missions_for(stats['chat_id'],stats['day']),1):
        total,users,_ = (stats['total'],stats['users'],0) if kind=='message' else game_progress(stats['chat_id'],stats['day'],kind)
        y=121+(i-1)*113
        d.rounded_rectangle((42,y,858,y+101),radius=15,fill=(9,22,43,216))
        d.text((59,y+10),f'{i:02d}   {"EASY" if i==1 else "MEDIUM" if i==2 else "HARD"}',font=_font(21),fill='#ffffff')
        d.text((795,y+11),f'{lo*(2 if double else 1)}-{hi*(2 if double else 1)} PTS',font=_font(19),anchor='ra',fill='#facc72')
        d.text((61,y+42),f'{kind.upper()} {min(total,need)}/{need}    MEMBERS {min(users,unique)}/{unique}',font=_font(17),fill='#d3e3ef')
        prog=min(1.0,total/need,users/unique)
        d.rounded_rectangle((61,y+78,829,y+87),radius=4,fill=(61,75,97,255))
        if prog>0:d.rounded_rectangle((61,y+78,61+int(768*prog),y+87),radius=4,fill=(78,219,196,255))
    d.text((61,469),f"{stats['day']}  |  /daily  |  /dailyclaim 1-3",font=_font(17),fill='#ceddea')
    out=BytesIO(); im.convert('RGB').save(out,'JPEG',quality=90);out.seek(0);out.name='daily_challenge.jpg'
    return out
