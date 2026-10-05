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
    card=create_card(W,H,(10,12,18,255))
    if art:card=add_background_image(card,art,blur=.4,darken=125)
    accent=ACCENTS.get(variant,ACCENTS["crimson"])
    draw_panel(card,(30,28,1070,692),fill=(10,13,20,205),radius=34,outline=accent,outline_width=3)
    return card,accent

def _top(raid):
    fs=list(raid.get("fighters",{}).values());fs.sort(key=lambda x:(x.get("damage",0),x.get("hits",0)),reverse=True);return fs[:3]

def live_card(raid,art=None,variant=None):
    variant=variant or random.choice(VARIANTS);card,accent=_base(art,variant);b=raid["boss"]
    hp=max(0,raid["hp"]);mx=max(1,raid["max_hp"]);pct=hp/mx*100
    draw_text(card,"GROUP BOSS RAID",(70,72),size=34,fill=accent)
    draw_text(card,b["name"].upper(),(70,125),size=58)
    draw_text(card,f'{b["tier"]}  •  PHASE {raid["phase"]}',(72,174),size=27,fill=(205,210,220,255))
    draw_panel(card,(70,215,1030,330),fill=(16,20,29,225),radius=24)
    draw_text(card,"BOSS HP",(95,244),size=24,fill=(210,215,225,255))
    draw_progress_bar(card,(95,276,1005,307),pct,background=(50,55,66,255),foreground=accent,radius=14)
    draw_text(card,f'{hp:,} / {mx:,}  ({pct:.1f}%)',(550,318),size=22,anchor="mm")
    left=max(0,int(raid["ends_at"]-__import__("time").time()));m,s=divmod(left,60)
    draw_text(card,f'⏳ {m:02d}:{s:02d}',(90,390),size=30);draw_text(card,f'⚔ {raid["total_damage"]:,} DMG',(405,390),size=30);draw_text(card,f'👥 {len(raid["fighters"])}',(840,390),size=30)
    draw_panel(card,(70,440,1030,640),fill=(16,20,29,220),radius=24)
    draw_text(card,"TOP RAIDERS",(95,475),size=27,fill=accent)
    medals=("1","2","3")
    for i,p in enumerate(_top(raid)):
        name=str(p.get("name","Player"))[:20];draw_text(card,f'{medals[i]}. {name}',(105,525+i*43),size=25);draw_text(card,f'{p.get("damage",0):,} DMG',(985,525+i*43),size=25,anchor="ra")
    return card_to_bytes(card,"JPEG",91),variant

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
