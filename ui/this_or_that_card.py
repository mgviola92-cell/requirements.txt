"""Local photo atlas and labeled typography for abstract concepts; no remote URLs."""
import io,random,unicodedata
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
ROOT=Path(__file__).resolve().parent.parent
ATLAS=ROOT/'assets/this_or_that/options.jpg'
def _lines(d,label,font,width):
    # Burmese phrases often lack spaces: wrap characters without truncating the answer.
    lines=[];line=''
    clusters=[]
    for ch in label:
        if clusters and unicodedata.category(ch).startswith('M'):clusters[-1]+=ch
        else:clusters.append(ch)
    for cluster in clusters:
        if line and d.textlength(line+cluster,font=font)>width:lines.append(line);line=''
        line+=cluster
    if line:lines.append(line)
    return lines

def card(q,seed=0,style=None):
    rng=random.Random(seed);themes=[('#14213d','#fca311'),('#16324f','#5ce1b9'),('#2b193d','#e6a3ff'),('#252c3a','#ffc857')]
    bg,accent=themes[style] if style is not None else rng.choice(themes);im=Image.new('RGB',(1200,760),bg);d=ImageDraw.Draw(im)
    font=ImageFont.truetype(str(ROOT/'assets/fonts/myanmar.ttf'),30);big=ImageFont.truetype(str(ROOT/'assets/fonts/myanmar.ttf'),48)
    atlas=None
    try:atlas=Image.open(ATLAS).convert('RGB')
    except (OSError,ValueError):pass
    for column,side in enumerate(('a','b')):
        item=q[side];x=28+column*600;box=(x,80,x+544,590)
        d.rounded_rectangle(box,24,fill='#eef2f8')
        if item['photo'] is not None and atlas is not None:
            row,col=divmod(item['photo'],6);w,h=atlas.size
            tile=atlas.crop((round(col*w/6)+4,round(row*h/4)+4,round((col+1)*w/6)-4,round((row+1)*h/4)-4))
            im.paste(ImageOps.fit(tile,(524,490),centering=(rng.uniform(.35,.65),rng.uniform(.35,.65))),(x+10,90))
        else:
            d.rounded_rectangle((x+12,92,x+532,578),20,fill=accent)
            lines=_lines(d,item['label'],big,440)
            start=300-len(lines)*38
            for i,line in enumerate(lines):d.text((x+272,start+i*76),line,font=big,fill=bg,anchor='mt')
        d.text((x+20,20),side.upper(),font=big,fill=accent)
        lines=_lines(d,item['label'],font,530)
        for i,line in enumerate(lines):d.text((x+272,610+i*46),line,font=font,fill='white',anchor='mt')
    data=io.BytesIO();im.save(data,'JPEG',quality=85);data.seek(0);data.name='this_or_that.jpg'
    if atlas:atlas.close()
    return data
