"""Compact Word Chain card, optionally using user's own assets/word_chain images."""
from io import BytesIO
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from core.asset_manager import random_asset_avoiding_recent
import time

W,H = 900,480
ROOT=Path(__file__).resolve().parent.parent
FONTS=[ROOT/'assets/fonts/myanmar.ttf',Path('/usr/share/fonts/truetype/padauk/Padauk-Bold.ttf'),Path('/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf')]
LATIN=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf')]

def font(size, burmese=False):
    for p in ((FONTS+LATIN) if burmese else (LATIN+FONTS)):
        if p.exists(): return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()

def fit_text(d, text, max_width, size, min_size=19, burmese=False):
    for n in range(size,min_size-1,-2):
        f=font(n,burmese)
        if d.textbbox((0,0),text,font=f)[2]<=max_width: return f
    return font(min_size,burmese)

@lru_cache(maxsize=80)
def _card_background(game_id, moves):
    try:
        asset=random_asset_avoiding_recent('word_chain_background','word_chain',recent_limit=8,recursive=True)
        if asset:
            im=Image.open(asset).convert('RGB')
            im=ImageOps.fit(im,(W,H),method=Image.Resampling.LANCZOS,centering=(.5,.5))
            im=im.filter(ImageFilter.GaussianBlur(1.1))
        else: raise FileNotFoundError()
    except Exception:
        im=Image.new('RGB',(W,H),'#142437')
        draw=ImageDraw.Draw(im)
        for x in range(-H,W,38):
            draw.line((x,0,x+H,H),fill='#193146',width=2)
    # Gradient darkens the center for readable text while retaining imagery at edges.
    veil=Image.new('RGBA',(W,H),(0,0,0,0)); vp=veil.load()
    for y in range(H):
        for x in range(W):
            # stronger behind text but background remains visible
            a=int(125 + 32*(1-abs(x-W/2)/(W/2)) + 26*(y/H))
            vp[x,y]=(5,12,28,min(a,196))
    return Image.alpha_composite(im.convert('RGBA'),veil)

def status_card(game):
    im=_card_background(game['id'],game['moves']).copy()
    d=ImageDraw.Draw(im,'RGBA')
    cyan=(93,245,220,255); white=(249,251,255,255); muted=(187,203,218,255); gold=(255,218,115,255)
    d.rounded_rectangle((22,18,878,462),radius=28,outline=(125,213,235,135),width=2)
    d.rounded_rectangle((40,32,860,108),radius=20,fill=(8,18,36,190))
    d.rounded_rectangle((55,48,65,93),radius=5,fill=cyan)
    d.text((82,50),'WORD CHAIN',font=font(35),fill=white)
    mode='MYANMAR' if game['mode']=='my' else 'ENGLISH'
    mf=font(20)
    d.text((824,72),mode,font=mf,fill=cyan,anchor='rm')
    d.text((64,130),'CURRENT WORD',font=font(18),fill=muted)
    word=str(game['word'])
    d.text((63,161),word,font=fit_text(d,word,740,59,24,game['mode']=='my'),fill=white)
    d.rounded_rectangle((54,255,846,348),radius=22,fill=(12,33,51,205),outline=(93,245,220,185),width=2)
    d.text((78,289),'NEXT',font=font(24),fill=cyan)
    required=str(game['required'])
    d.text((242,279),required,font=fit_text(d,required,555,47,24,game['mode']=='my'),fill=gold)
    now=time.monotonic()
    idle=max(0,int(game['idle_deadline']-now+0.99))
    # Round duration is intentionally hidden; only the 60s answer timer is live.
    d.rounded_rectangle((54,370,846,448),radius=19,fill=(6,16,29,185))
    d.text((73,383),f"MOVES  {game['moves']}",font=font(20),fill=white)
    d.text((289,383),f'ANSWER  00:{idle:02d}',font=font(20),fill=cyan)
    d.text((573,383),'ROUND  ∞',font=font(20),fill=muted)
    ranked=sorted(game['scores'].items(),key=lambda x:(-x[1],x[0]))
    if ranked:
        uid,score=ranked[0]
        name=str(game['names'].get(uid,'Player'))
        name=name[:21]+('…' if len(name)>21 else '')
        d.text((73,419),'TOP  '+name+'  '+str(score),font=fit_text(d,'TOP  '+name+'  '+str(score),715,19,15,True),fill=gold)
    else:
        d.text((73,419),'TOP  —',font=font(19),fill=gold)
    out=BytesIO(); im.convert('RGB').save(out,'JPEG',quality=93,optimize=True)
    out.seek(0); out.name='word_chain.jpg'; return out
