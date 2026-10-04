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
    ranked = sorted(game['scores'].items(), key=lambda x: (-x[1], x[0]))[:3]
    # Compact three-column leaderboard fits inside the existing footer.
    # Show equal word counts as tied ranks, matching the end-result rewards.
    last_count = None
    rank = 0
    for index, (uid, score) in enumerate(ranked):
        if score != last_count:
            rank = index + 1
            last_count = score
        x = 73 + index * 255
        name = str(game['names'].get(uid, 'Player'))
        label = f'#{rank} {name}  {score}'
        color = gold if rank == 1 else white
        d.text((x, 419), label,
               font=fit_text(d, label, 235, 18, 12, True), fill=color)
    if not ranked:
        d.text((73, 419), 'TOP 3  —', font=font(19), fill=gold)
    out=BytesIO(); im.convert('RGB').save(out,'JPEG',quality=93,optimize=True)
    out.seek(0); out.name='word_chain.jpg'; return out


# =========================================================
# FINISHED WORD CHAIN — COMPACT RESULT CARD
# Drawn with the same fonts, background and visual language
# as the live status card. Background is selected once for
# the result card, not for each countdown tick.
# =========================================================
def result_card(game, rows, reason):
    im = _card_background(game['id'], 'result').copy()
    d = ImageDraw.Draw(im, 'RGBA')
    white = (250, 252, 255, 255)
    cyan = (93, 245, 220, 255)
    muted = (194, 211, 226, 255)
    gold = (255, 214, 110, 255)

    d.rounded_rectangle((22, 18, 878, 462), radius=28,
                        fill=(7, 16, 32, 100), outline=(125, 213, 235, 160), width=2)
    d.rounded_rectangle((40, 32, 860, 111), radius=20, fill=(8, 18, 36, 215))
    d.rounded_rectangle((55, 48, 65, 95), radius=5, fill=cyan)
    d.text((82, 50), 'WORD CHAIN', font=font(34), fill=white)
    d.text((824, 79), 'RESULT', font=font(21), fill=gold, anchor='rm')

    reason = str(reason or 'Game ended')
    d.text((57, 126), reason, font=fit_text(d, reason, 780, 23, 16), fill=muted)

    head_y = 168
    d.rounded_rectangle((54, head_y, 846, head_y + 41), radius=12, fill=(19, 46, 65, 230))
    d.text((78, head_y + 7), 'RANK', font=font(19), fill=cyan)
    d.text((183, head_y + 7), 'PLAYER', font=font(19), fill=cyan)
    d.text((646, head_y + 7), 'WORDS', font=font(19), fill=cyan, anchor='rm')
    d.text((822, head_y + 7), 'REWARD', font=font(19), fill=cyan, anchor='rm')

    if not rows:
        d.text((450, 279), 'No valid answers', font=font(29), fill=white, anchor='mm')
    else:
        # Five visible rows for legibility on compact Telegram photos.
        for idx, row in enumerate(rows[:5]):
            y = 219 + idx * 43
            if idx % 2 == 0:
                d.rounded_rectangle((54, y, 846, y + 41), radius=10, fill=(14, 27, 46, 190))
            d.text((85, y + 6), f"#{row['rank']}", font=font(21), fill=gold)
            name = str(row['name'])
            d.text((183, y + 7), name,
                   font=fit_text(d, name, 330, 21, 16, True), fill=white)
            d.text((638, y + 7), str(row['words']), font=font(21), fill=white, anchor='rm')
            reward = 'ERROR' if row.get('reward_error') else (
                f"+{row['points']}" if row['points'] else '—'
            )
            d.text((813, y + 7), reward, font=font(21),
                   fill=gold if row['points'] else muted, anchor='rm')
        if len(rows) > 5:
            d.text((450, 449), f"+{len(rows)-5} more players", font=font(14),
                   fill=muted, anchor='mm')

    out = BytesIO()
    im.convert('RGB').save(out, 'JPEG', quality=93, optimize=True)
    out.seek(0)
    out.name = 'word_chain_result.jpg'
    return out
