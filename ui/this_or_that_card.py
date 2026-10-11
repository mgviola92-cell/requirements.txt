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
