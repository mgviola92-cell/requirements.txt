# =========================================================
# 👹 BOSS RAID DYNAMIC VISUAL CARDS
# One base artwork per boss -> live visual states generated at runtime.
# =========================================================
import random
from PIL import Image, ImageEnhance, ImageFilter
from core.asset_manager import random_asset_avoiding_recent
from ui.card_generator import create_card,add_background_image,draw_panel,draw_text,card_to_bytes,open_image

W,H=1100,720
VARIANTS=("crimson","obsidian","ember","storm")
ACCENTS={"crimson":(240,70,70,255),"obsidian":(185,140,255,255),"ember":(255,170,60,255),"storm":(90,190,255,255)}
VISUAL_STAGES=("normal","damaged","rage","final")

def get_boss_artwork(boss_name):
    slug=str(boss_name).lower().replace(" ","_")
    from core.asset_manager import get_asset_path
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
    """Generate a fresh treatment from the base artwork without changing the source file."""
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

def _base(art,variant,stage="normal"):
    card=create_card(W,H,(10,12,18,255))
    treated=_stage_art(art,stage) if art else None
    if treated:
        darken={"normal":38,"damaged":44,"rage":34,"final":28}.get(stage,38)
        card=add_background_image(card,treated,blur=.12,darken=darken)
    accent=ACCENTS.get(variant,ACCENTS["crimson"])
    draw_panel(card,(24,22,1076,698),fill=(7,9,14,35),radius=32,outline=accent,outline_width=3)
    return card,accent

def live_card(raid,art=None,variant=None):
    variant=variant or random.choice(VARIANTS)
    stage=visual_stage(raid)
    card,accent=_base(art,variant,stage)
    b=raid["boss"]
    draw_panel(card,(48,42,1052,148),fill=(7,9,14,145),radius=26,outline=accent,outline_width=2)
    draw_text(card,"GROUP BOSS RAID",(82,78),size=24,fill=accent)
    draw_text(card,b["name"].upper(),(82,128),size=48)
    draw_panel(card,(730,604,1048,672),fill=(7,9,14,150),radius=22,outline=accent,outline_width=2)
    label={"normal":"RAID LIVE","damaged":"DAMAGED","rage":"RAGE","final":"FINAL STAND"}[stage]
    draw_text(card,f'{b["tier"]}  •  {label}',(1012,646),size=24,fill=(238,240,245,255),anchor="ra")
    return card_to_bytes(card,"JPEG",95),variant

def result_card(raid,won,line,muted=0,protected=0,art=None,variant=None):
    variant=variant or random.choice(VARIANTS);card,accent=_base(art,variant,"final");b=raid["boss"]
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
