# =========================================================
# 👹 BOSS RAID DYNAMIC VISUAL CARDS
# Base artwork is optional. As assets/boss_raid grows, variants grow automatically.
# =========================================================
import random
from PIL import ImageDraw
from core.asset_manager import random_asset_avoiding_recent
from ui.card_generator import create_card,add_background_image,draw_panel,draw_text,draw_progress_bar,card_to_bytes

W,H=1100,720
VARIANTS=("crimson","obsidian","ember","storm")
ACCENTS={"crimson":(240,70,70,255),"obsidian":(185,140,255,255),"ember":(255,170,60,255),"storm":(90,190,255,255)}

def get_boss_artwork(boss_name):
    slug=str(boss_name).lower().replace(" ","_")
    # Prefer boss-specific art; fall back to the shared pool.
    p=random_asset_avoiding_recent("boss:"+slug,"boss_raid",slug,recent_limit=4,recursive=True)
    if p:return p
    return random_asset_avoiding_recent("boss:generic","boss_raid","generic",recent_limit=10,recursive=True)

def _base(art,variant):
    # Artwork-first cinematic scene: keep the boss visible instead of covering
    # the whole image with a dashboard panel.
    card=create_card(W,H,(10,12,18,255))
    if art:card=add_background_image(card,art,blur=.12,darken=42)
    accent=ACCENTS.get(variant,ACCENTS["crimson"])
    draw_panel(card,(24,22,1076,698),fill=(7,9,14,35),radius=32,outline=accent,outline_width=3)
    return card,accent

def live_card(raid,art=None,variant=None):
    variant=variant or random.choice(VARIANTS)
    card,accent=_base(art,variant)
    b=raid["boss"]
    # The JPEG is intentionally mostly artwork. Exact HP/timer/damage/raiders
    # are live Telegram caption data, so the image never shows stale stats.
    draw_panel(card,(48,42,1052,148),fill=(7,9,14,145),radius=26,outline=accent,outline_width=2)
    draw_text(card,"GROUP BOSS RAID",(82,78),size=24,fill=accent)
    draw_text(card,b["name"].upper(),(82,128),size=48)
    draw_panel(card,(760,604,1048,672),fill=(7,9,14,150),radius=22,outline=accent,outline_width=2)
    draw_text(card,f'{b["tier"]}  •  RAID LIVE',(1012,646),size=24,fill=(238,240,245,255),anchor="ra")
    return card_to_bytes(card,"JPEG",95),variant

def result_card(raid,won,line,muted=0,protected=0,art=None,variant=None):
    variant=variant or random.choice(VARIANTS);card,accent=_base(art,variant);b=raid["boss"]
    title="RAID VICTORY" if won else "PARTY DEFEATED";icon="🏆" if won else "☠"
    draw_text(card,f"{icon} {title}",(550,105),size=58,fill=accent,anchor="mm")
    draw_text(card,b["name"].upper(),(550,175),size=42,anchor="mm")
    draw_panel(card,(90,230,1010,390),fill=(16,20,29,230),radius=28)
    draw_text(card,"BOSS SAYS",(550,268),size=23,fill=accent,anchor="mm")
    # Keep result readable; reaction is also sent in caption for full text.
    short=str(line)
    if len(short)>65:short=short[:62]+"..."
    draw_text(card,f'“{short}”',(550,325),size=29,anchor="mm")
    draw_panel(card,(90,430,1010,615),fill=(16,20,29,225),radius=28)
    draw_text(card,f'⚔ TOTAL DAMAGE   {raid["total_damage"]:,}',(130,478),size=29)
    draw_text(card,f'👥 RAIDERS        {len(raid["fighters"])}',(130,528),size=29)
    if not won:draw_text(card,f'🔒 PENALTY        {muted} muted / {protected} protected',(130,578),size=27,fill=accent)
    else:draw_text(card,'✨ BOSS DEFEATED — RAID CLEARED',(130,578),size=27,fill=accent)
    return card_to_bytes(card,"JPEG",93)
