"""Photo-matched 5-round This or That card renderer.

Requires actual tagged option images: never invent or reuse unrelated photos.
"""
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from ui.card_generator import create_card, draw_panel, draw_text, paste_image, card_to_bytes, load_font
from core.this_or_that_visuals import get_visuals

W,H=1000,640

def round_card(question, round_no, votes=(0,0), manifest=None):
    paths=get_visuals(question,manifest)
    if not paths:
        return None
    card=create_card(W,H,background=(13,20,37,255))
    draw_panel(card,(25,18,975,618),fill=(24,34,53,255),radius=28)
    draw_text(card,"THIS OR THAT",(500,48),size=45,anchor="mm")
    draw_text(card,f"ROUND {round_no} / 5",(500,103),size=25,fill=(166,184,205,255),anchor="mm")
    for i, path in enumerate(paths):
        left=45+i*460
        paste_image(card,path,(left,145,left+445,440),rounded_radius=23)
        draw_panel(card,(left,454,left+445,571),fill=(41,52,75,255),radius=18)
        text=question["options"][i]
        text_size=28 if len(text)>18 else 36
        draw_text(card,text,(left+222,500),size=text_size,anchor="mm")
        count=votes[i]
        draw_text(card,f"{'A' if i==0 else 'B'}  •  {count} Votes",
                  (left+222,548),size=22,fill=(175,205,236,255),anchor="mm")
    return card_to_bytes(card,image_format="JPEG",quality=90)

def illustrated_card(question, round_no, votes=(0, 0)):
    """Readably typeset the *actual* choices when photos are not yet available.

    This is a text/graphic card, not a substitute unrelated photograph.
    """
    card=create_card(W,H,background=(12,18,34,255))
    draw_panel(card,(25,20,975,620),fill=(26,35,56,255),radius=32)
    draw_text(card,"THIS OR THAT",(500,62),size=46,anchor="mm")
    draw_text(card,f"ROUND {round_no} / 5",(500,120),size=28,fill=(175,194,218,255),anchor="mm")
    draw_text(card,question["category"],(500,178),size=32,fill=(221,227,237,255),anchor="mm")
    total=sum(votes)
    for i,choice in enumerate(question["options"]):
        left=45+i*460
        draw_panel(card,(left,225,left+444,548),fill=(42,55,84,255) if i==0 else (63,46,80,255),radius=28)
        draw_text(card,"A" if i==0 else "B",(left+222,278),size=64,anchor="mm")
        size=26 if len(choice)>27 else (31 if len(choice)>19 else 37)
        draw_text(card,choice,(left+222,380),size=size,anchor="mm")
        pct=round(votes[i]*100/total) if total else 0
        draw_text(card,f"{pct}%  •  {votes[i]} Votes",(left+222,490),
                  size=25,fill=(184,207,233,255),anchor="mm")
    return card_to_bytes(card,image_format="JPEG",quality=90)


def result_card(people, rounds=5):
    card=create_card(W,H,background=(11,20,38,255))
    draw_panel(card,(70,60,930,575),fill=(29,42,67,255),radius=40)
    draw_text(card,"THIS OR THAT",(500,165),size=57,anchor="mm")
    draw_text(card,"FINISHED",(500,275),size=70,fill=(155,226,190,255),anchor="mm")
    draw_text(card,f"{rounds} / 5 ROUNDS",(500,375),size=37,anchor="mm")
    draw_text(card,f"{people} Players Voted",(500,475),size=32,
              fill=(174,194,214,255),anchor="mm")
    return card_to_bytes(card,image_format="JPEG",quality=90)
