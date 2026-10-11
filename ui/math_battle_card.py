from core.customization import message_text as _custom_text, setting_value as _custom_setting, bank_text as _custom_bank
"""Compact image cards for Math Battle. Optional assets/math_battle backgrounds."""
from io import BytesIO
from pathlib import Path
import time
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from core.asset_manager import random_asset_avoiding_recent

ROOT=Path(__file__).resolve().parent.parent
W,H=900,530

def font(n,mm=False):
    paths=([ROOT/'assets/fonts/myanmar.ttf'] if mm else []) + [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),ROOT/'assets/fonts/myanmar.ttf']
    for p in paths:
        if p.exists(): return ImageFont.truetype(str(p),n)
    return ImageFont.load_default()

def _background():
    try:
        asset=random_asset_avoiding_recent('math_battle_background','math_battle',recent_limit=10,recursive=True)
        if asset:
            return ImageOps.fit(Image.open(asset).convert('RGB'),(W,H),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    except Exception as e: print('Math background error:',e)
    im=Image.new('RGB',(W,H),'#121d31'); d=ImageDraw.Draw(im)
    for x in range(-H,W,44): d.line((x,0,x+H,H),fill='#1b3652',width=2)
    return im

def _get_bg(game):
    # Caller stores background in game snapshot only while rendering; stable per round via cache.
    key=(game['id'],game['round'])
    if key not in _BGS:
        if len(_BGS)>=80: _BGS.clear()
        _BGS[key]=_background()
    return _BGS[key].copy()
_BGS={}

def _textfit(draw,text,limit,n=30,mm=False):
    while n>15 and draw.textbbox((0,0),text,font=font(n,mm))[2]>limit: n-=2
    return font(n,mm)

def _base(game):
    im=_get_bg(game).convert('RGBA'); veil=Image.new('RGBA',(W,H),(8,14,30,153)); im=Image.alpha_composite(im,veil)
    d=ImageDraw.Draw(im,'RGBA')
    d.rounded_rectangle((20,17,880,513),radius=28,outline=(105,219,245,150),width=2)
    d.rounded_rectangle((36,34,864,105),radius=18,fill=(6,16,35,211))
    d.text((59,51),_custom_text('msg.ui.math_battle_card._base.303fa51fa7', 'MATH BATTLE', {}),font=font(33),fill=_custom_text('msg.ui.math_battle_card._base.9e200f76d6', '#f9fbff', {}))
    d.text((835,58),_custom_text('msg.ui.math_battle_card._base.9b789c62dd', 'ROUND {game__round_____1}/5', {'game__round_____1': f"{game['round'] + 1}"}),font=font(22),fill=_custom_text('msg.ui.math_battle_card._base.d5fc71983e', '#fcd67d', {}),anchor='ra')
    return im,d

def _export(im):
    b=BytesIO();im.convert('RGB').save(b,'JPEG',quality=91,optimize=True);b.seek(0);b.name='math_battle.jpg';return b

def round_card(game):
    im,d=_base(game)
    d.rounded_rectangle((44,120,856,291),radius=22,fill=(6,19,38,211))
    raw_question = str(game['question']['question'])
    # Show algebra's instruction as a clear heading, separate from the equation.
    is_algebra = game['round'] == 3 and '; x = ?' in raw_question
    heading = 'SOLVE FOR X' if is_algebra else 'SOLVE THE QUESTION'
    q = raw_question.split(';', 1)[0].strip() if is_algebra else raw_question
    d.text((450,143),heading,font=font(20),fill=_custom_text('msg.ui.math_battle_card.round_card.0fb5c2c981', '#a2b9ce', {}),anchor='mt')
    d.text((450,212),q,font=_textfit(d,q,750,47),fill=_custom_text('msg.ui.math_battle_card.round_card.c659d630ce', '#ffffff', {}),anchor='mm')
    remain=max(0,int(game['deadline']-time.monotonic()+.99))
    d.rounded_rectangle((45,307,410,365),radius=16,fill=(10,34,54,205))
    d.rounded_rectangle((429,307,855,365),radius=16,fill=(10,34,54,205))
    d.text((66,322),_custom_text('msg.ui.math_battle_card.round_card.313347f075', 'TIME   {remain}s', {'remain': f'{remain:02d}'}),font=font(24),fill=_custom_text('msg.ui.math_battle_card.round_card.a78fc0a3da', '#67e8f9', {}))
    d.text((449,322),_custom_text('msg.ui.math_battle_card.round_card.7b78c497fc', 'FIRST +10  /  +5  /  +3', {}),font=font(20),fill=_custom_text('msg.ui.math_battle_card.round_card.d5fc71983e', '#fcd67d', {}))
    d.text((53,384),_custom_text('msg.ui.math_battle_card.round_card.3c693343e5', 'LIVE TOP 3  ·  MATCH SCORE', {}),font=font(17),fill=_custom_text('msg.ui.math_battle_card.round_card.e3689f943a', '#adbacd', {}))
    ranks=sorted(game['scores'].items(),key=lambda x:(-x[1],x[0]))[:3]
    for i in range(3):
        x=52+i*282
        d.rounded_rectangle((x,410,x+270,493),radius=15,fill=(6,15,31,204))
        if i<len(ranks):
            uid,score=ranks[i]; name=str(game['names'].get(uid,'Player'))
            d.text((x+12,425),f'#{i+1} '+name,font=_textfit(d,f'#{i+1} '+name,242,18,True),fill=(_custom_text('msg.ui.math_battle_card.round_card.fb30ca441f', '#f9dc7c', {}) if i==0 else _custom_text('msg.ui.math_battle_card.round_card.7275a5427c', '#e5edf7', {})))
            d.text((x+12,458),_custom_text('msg.ui.math_battle_card.round_card.8034a6279b', '{score} SCORE', {'score': f'{score}'}),font=font(19),fill=_custom_text('msg.ui.math_battle_card.round_card.a78fc0a3da', '#67e8f9', {}))
        else: d.text((x+18,438),f'#{i+1} —',font=font(19),fill=_custom_text('msg.ui.math_battle_card.round_card.b580cf24f1', '#a2b5c9', {}))
    return _export(im)

def result_card(game, rewards):
    im,d=_base(game)
    d.text((450,146),_custom_text('msg.ui.math_battle_card.result_card.8f72d317fb', 'FINAL RESULTS', {}),font=font(39),fill=_custom_text('msg.ui.math_battle_card.result_card.d5fc71983e', '#fcd67d', {}),anchor='mt')
    ranked=sorted(game['scores'].items(),key=lambda x:(-x[1],x[0]))
    for i,(uid,score) in enumerate(ranked[:5]):
        y=206+i*52
        d.rounded_rectangle((55,y,845,y+46),radius=12,fill=(7,21,40,210))
        name=str(game['names'].get(uid,'Player'))
        d.text((73,y+8),f'#{i+1}  '+name,font=_textfit(d,f'#{i+1}  '+name,460,22,True),fill=_custom_text('msg.ui.math_battle_card.result_card.c659d630ce', '#ffffff', {}))
        d.text((602,y+9),_custom_text('msg.ui.math_battle_card.result_card.8034a6279b', '{score} SCORE', {'score': f'{score}'}),font=font(19),fill=_custom_text('msg.ui.math_battle_card.result_card.a78fc0a3da', '#67e8f9', {}))
        reward=rewards.get(uid)
        if reward is not None: d.text((825,y+9),f'+{reward}',font=font(20),fill=_custom_text('msg.ui.math_battle_card.result_card.d5fc71983e', '#fcd67d', {}),anchor='ra')
    if not ranked: d.text((450,260),_custom_text('msg.ui.math_battle_card.result_card.fea182ba9a', 'NO CORRECT ANSWERS', {}),font=font(23),fill=_custom_text('msg.ui.math_battle_card.result_card.d14f901611', '#fff', {}),anchor='mt')
    return _export(im)
