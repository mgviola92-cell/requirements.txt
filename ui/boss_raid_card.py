# =========================================================
# 👹 BOSS RAID DYNAMIC VISUAL CARDS
# One base artwork per boss -> many runtime cinematic variants.
# =========================================================
import random
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from core.asset_manager import random_asset_avoiding_recent
from ui.card_generator import create_card,add_background_image,draw_panel,draw_text,card_to_bytes,open_image

W,H=1100,720
VARIANTS=("crimson","obsidian","ember","storm")
ACCENTS={"crimson":(240,70,70,255),"obsidian":(185,140,255,255),"ember":(255,170,60,255),"storm":(90,190,255,255)}
VISUAL_STAGES=("normal","damaged","rage","final")
COMPOSITIONS=("center","close","left","right")
_STAGE_DARKEN={"normal":38,"damaged":44,"rage":34,"final":28}
BOSS_ELEMENTS={"Slime King":"poison","Cave Troll":"earth","Wild Golem":"nature","Venom Spider":"poison","Goblin Chief":"earth","Frost Wolf":"ice","Orc Warlord":"fire","Stone Guardian":"earth","Sand Serpent":"sand","Dark Knight":"shadow","Thunder Beast":"lightning","Swamp Hydra":"poison","Inferno Giant":"fire","Abyss Reaper":"shadow","Storm Titan":"lightning","Ancient Hydra":"nature","Demon Lord":"fire","Void Colossus":"void","Celestial Dragon":"celestial","World Eater":"void","Chaos Emperor":"chaos","Eclipse Titan":"shadow","Immortal Demon":"chaos","Neon Destroyer":"neon"}
ELEMENT_ACCENTS={"fire":(255,92,35,255),"ice":(105,215,255,255),"poison":(105,235,95,255),"lightning":(245,225,75,255),"void":(145,80,245,255),"celestial":(245,220,145,255),"shadow":(145,115,190,255),"earth":(190,135,75,255),"nature":(85,205,110,255),"sand":(235,190,105,255),"chaos":(245,70,160,255),"neon":(45,245,225,255)}

def boss_element(boss_name):
    return BOSS_ELEMENTS.get(str(boss_name),"shadow")

def _element_treatment(image,element):
    if image is None:return None
    a=ELEMENT_ACCENTS.get(element,ELEMENT_ACCENTS["shadow"])
    return Image.alpha_composite(image,Image.new("RGBA",image.size,(a[0],a[1],a[2],18)))

def _element_effects(card,element,stage):
    overlay=Image.new("RGBA",card.size,(0,0,0,0));d=ImageDraw.Draw(overlay)
    a=ELEMENT_ACCENTS.get(element,ELEMENT_ACCENTS["shadow"]);alpha=24 if stage in ("normal","damaged") else (38 if stage=="rage" else 52)
    if element in ("fire","chaos"):
        for x in range(70,W,150):d.polygon([(x,H),(x+48,H),(x+22,H-105),(x-12,H-42)],fill=(a[0],a[1],a[2],alpha))
    elif element=="ice":
        for x in range(40,W,125):d.line((x,H,x+65,H-120),fill=(a[0],a[1],a[2],alpha),width=5)
    elif element=="lightning":
        for x in (160,490,820):d.line((x,80,x+55,245,x+10,390,x+90,610),fill=(a[0],a[1],a[2],alpha),width=7)
    elif element in ("poison","nature"):
        for x,y,r in ((120,570,42),(310,625,25),(760,590,38),(930,635,22)):d.ellipse((x-r,y-r,x+r,y+r),outline=(a[0],a[1],a[2],alpha),width=5)
    elif element in ("void","shadow"):
        for r in (70,130,195):d.ellipse((W//2-r,H//2-r,W//2+r,H//2+r),outline=(a[0],a[1],a[2],max(12,alpha-r//10)),width=5)
    elif element=="celestial":
        for x,y in ((100,110),(250,230),(860,120),(980,310),(690,210)):d.ellipse((x-5,y-5,x+5,y+5),fill=(a[0],a[1],a[2],alpha+35))
    elif element in ("earth","sand"):
        for y in (535,585,635):d.line((0,y,W,y-45),fill=(a[0],a[1],a[2],alpha),width=8)
    elif element=="neon":
        for y in (190,365,540):d.line((0,y,W,y),fill=(a[0],a[1],a[2],alpha),width=5)
    return Image.alpha_composite(card,overlay)

def get_boss_artwork(boss_name,stage=None):
    """AI asset preferred, then stage pool, then the original 24 base images."""
    slug=str(boss_name).lower().replace(" ","_")
    from core.asset_manager import get_asset_path
    stage=str(stage or "").lower()

    # Optional future AI library:
    # assets/boss_raid/ai/<boss_slug>/<stage>/*.(png|jpg|jpeg|webp)
    # assets/boss_raid/ai/<boss_slug>/*.(png|jpg|jpeg|webp)
    if stage in VISUAL_STAGES:
        p=random_asset_avoiding_recent(
            "boss-ai:"+slug+":"+stage,"boss_raid","ai",slug,stage,
            recent_limit=4,recursive=True
        )
        if p:return p
    p=random_asset_avoiding_recent(
        "boss-ai:"+slug,"boss_raid","ai",slug,
        recent_limit=6,recursive=False
    )
    if p:return p

    # Legacy/stage-specific artwork remains supported.
    if stage in VISUAL_STAGES:
        p=random_asset_avoiding_recent(
            "boss-stage:"+slug+":"+stage,"boss_raid",slug,stage,
            recent_limit=4,recursive=True
        )
        if p:return p

    # Current flat 24-image base library.
    for ext in (".jpg",".jpeg",".png",".webp"):
        p=get_asset_path("boss_raid",slug+ext)
        if p:return p

    p=random_asset_avoiding_recent("boss:"+slug,"boss_raid",slug,recent_limit=4,recursive=True)
    if p:return p
    return random_asset_avoiding_recent("boss:generic","boss_raid","generic",recent_limit=10,recursive=True)

def visual_stage(raid):
    mx=max(1,int(raid.get("max_hp") or raid.get("boss",{}).get("hp") or 1))
    pct=max(0.0,float(raid.get("hp",mx))/mx*100.0)
    if pct<=25:return "final"
    if pct<=50:return "rage"
    if pct<=75:return "damaged"
    return "normal"

def _stage_art(art,stage):
    image=open_image(art)
    if image is None:return None
    stage=stage if stage in VISUAL_STAGES else "normal"
    if stage=="normal":
        return ImageEnhance.Contrast(image).enhance(1.05)
    if stage=="damaged":
        image=ImageEnhance.Contrast(image).enhance(1.18)
        image=ImageEnhance.Color(image).enhance(.78)
        return Image.alpha_composite(image,Image.new("RGBA",image.size,(70,35,20,34)))
    if stage=="rage":
        image=ImageEnhance.Contrast(image).enhance(1.32)
        image=ImageEnhance.Color(image).enhance(1.28)
        return Image.alpha_composite(image,Image.new("RGBA",image.size,(125,12,8,58)))
    image=ImageEnhance.Contrast(image).enhance(1.48)
    image=image.filter(ImageFilter.UnsharpMask(radius=2,percent=145,threshold=3))
    return Image.alpha_composite(image,Image.new("RGBA",image.size,(65,0,90,70)))

def _compose_art(image,composition):
    """Crop/zoom a base boss image into different cinematic compositions."""
    if image is None:return None
    composition=composition if composition in COMPOSITIONS else "center"
    w,h=image.size
    zoom={"center":1.0,"close":1.28,"left":1.16,"right":1.16}[composition]
    crop_w=max(1,int(w/zoom));crop_h=max(1,int(h/zoom))
    if composition=="left":cx=int(w*.42)
    elif composition=="right":cx=int(w*.58)
    else:cx=w//2
    cy=int(h*.48) if composition=="close" else h//2
    left=max(0,min(w-crop_w,cx-crop_w//2))
    top=max(0,min(h-crop_h,cy-crop_h//2))
    return image.crop((left,top,left+crop_w,top+crop_h)).resize((w,h),Image.Resampling.LANCZOS)

def _effects(card,stage,variant):
    """Lightweight procedural overlays; no extra image assets required."""
    overlay=Image.new("RGBA",card.size,(0,0,0,0))
    d=ImageDraw.Draw(overlay)
    accent=ACCENTS.get(variant,ACCENTS["crimson"])
    # Cinematic edge vignette.
    for i,a in ((0,105),(18,72),(36,44)):
        d.rounded_rectangle((i,i,W-i,H-i),radius=34,outline=(0,0,0,a),width=18)
    # Stage-specific energy bands.
    if stage in ("rage","final"):
        for x in range(-H,W,190):
            d.line((x,H,x+260,0),fill=(accent[0],accent[1],accent[2],28 if stage=="rage" else 42),width=9)
    if stage=="damaged":
        for x in (210,520,835):
            d.line((x,80,x-75,650),fill=(205,150,105,24),width=5)
    return Image.alpha_composite(card,overlay)

def _base(art,variant,stage="normal",composition="center",element="shadow"):
    card=create_card(W,H,(10,12,18,255))
    treated=_stage_art(art,stage) if art else None
    treated=_compose_art(treated,composition)
    treated=_element_treatment(treated,element)
    if treated:
        card=add_background_image(card,treated,blur=.12,darken=_STAGE_DARKEN.get(stage,38))
    card=_effects(card,stage,variant)
    card=_element_effects(card,element,stage)
    accent=ELEMENT_ACCENTS.get(element,ACCENTS.get(variant,ACCENTS["crimson"]))
    frame_alpha={"normal":35,"damaged":50,"rage":72,"final":90}.get(stage,35)
    draw_panel(card,(24,22,1076,698),fill=(7,9,14,frame_alpha),radius=32,outline=accent,outline_width=3)
    return card,accent

def live_card(raid,art=None,variant=None,composition=None):
    variant=variant or random.choice(VARIANTS)
    composition=composition or random.choice(COMPOSITIONS)
    stage=visual_stage(raid)
    b=raid["boss"];element=boss_element(b["name"])
    card,accent=_base(art,variant,stage,composition,element)
    draw_panel(card,(48,42,1052,148),fill=(7,9,14,145),radius=26,outline=accent,outline_width=2)
    draw_text(card,"GROUP BOSS RAID",(82,78),size=24,fill=accent)
    draw_text(card,b["name"].upper(),(82,128),size=48)
    draw_panel(card,(730,604,1048,672),fill=(7,9,14,150),radius=22,outline=accent,outline_width=2)
    label={"normal":"RAID LIVE","damaged":"DAMAGED","rage":"RAGE","final":"FINAL STAND"}[stage]
    draw_text(card,f'{b["tier"]}  •  {label}',(1012,646),size=24,fill=(238,240,245,255),anchor="ra")
    phase_label={"normal":"PHASE I","damaged":"PHASE II","rage":"PHASE III","final":"FINAL PHASE"}[stage]
    draw_panel(card,(48,604,310,672),fill=(7,9,14,175),radius=22,outline=accent,outline_width=2)
    draw_text(card,phase_label,(179,646),size=22,fill=accent,anchor="mm")
    return card_to_bytes(card,"JPEG",95),variant,composition

def result_card(raid,won,line,muted=0,protected=0,art=None,variant=None,composition=None):
    variant=variant or random.choice(VARIANTS);composition=composition or random.choice(COMPOSITIONS)
    b=raid["boss"];element=boss_element(b["name"])
    # Victory should feel cleared/bright; defeat keeps the threatening final-phase look.
    result_stage="normal" if won else "final"
    card,accent=_base(art,variant,result_stage,composition,element)
    if won:
        glow=Image.new("RGBA",card.size,(255,230,150,18))
        card=Image.alpha_composite(card,glow)
    else:
        shade=Image.new("RGBA",card.size,(35,0,45,24))
        card=Image.alpha_composite(card,shade)
    title="RAID VICTORY" if won else "PARTY DEFEATED";icon="🏆" if won else "☠"
    draw_text(card,f"{icon} {title}",(550,105),size=58,fill=accent,anchor="mm")
    draw_text(card,b["name"].upper(),(550,175),size=42,anchor="mm")
    draw_panel(card,(90,230,1010,390),fill=(16,20,29,230),radius=28)
    draw_text(card,"BOSS SAYS",(550,268),size=23,fill=accent,anchor="mm")
    short=str(line)
    if len(short)>65:short=short[:62]+"..."
    draw_text(card,f'“{short}”',(550,325),size=29,anchor="mm")
    draw_panel(card,(90,430,1010,615),fill=(16,20,29,225),radius=28)
    draw_text(card,f'⚔ TOTAL DAMAGE   {raid["total_damage"]:,}',(130,478),size=29)
    draw_text(card,f'👥 RAIDERS        {len(raid["fighters"])}',(130,528),size=29)
    if not won:draw_text(card,f'🔒 PENALTY        {muted} muted / {protected} protected',(130,578),size=27,fill=accent)
    else:draw_text(card,'✨ BOSS DEFEATED — RAID CLEARED',(130,578),size=27,fill=accent)
    return card_to_bytes(card,"JPEG",93)
