from PIL import Image, ImageDraw
from ui.card_generator import draw_text, card_to_bytes

W, H = 1100, 620

def base_card():
    image = Image.new("RGBA", (W, H), (14, 15, 24, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((28, 28, 1072, 592), radius=34, fill=(24, 26, 40, 255), outline=(110, 100, 210, 255), width=3)
    return image, draw

def challenge_card(game):
    image, draw = base_card()
    draw_text(image, "PAIR CHALLENGE", (550, 85), size=42, anchor="mm")
    draw_text(image, game["question"], (550, 225), size=34, anchor="mm")
    draw.rounded_rectangle((90, 310, 510, 475), radius=28, fill=(50, 38, 88, 255), outline=(155, 125, 255, 255), width=3)
    draw.rounded_rectangle((590, 310, 1010, 475), radius=28, fill=(35, 65, 90, 255), outline=(90, 185, 255, 255), width=3)
    draw_text(image, "A", (300, 355), size=25, anchor="mm")
    draw_text(image, game["left"], (300, 420), size=31, anchor="mm")
    draw_text(image, "B", (800, 355), size=25, anchor="mm")
    draw_text(image, game["right"], (800, 420), size=31, anchor="mm")
    draw_text(image, "Choose one. Matching answers are paired.", (550, 535), size=20, fill=(195, 200, 220, 255), anchor="mm")
    return card_to_bytes(image, "JPEG", 94)

def result_card(game, rows):
    image, draw = base_card()
    draw_text(image, "PAIR CHALLENGE - RESULT", (550, 80), size=38, anchor="mm")
    draw_text(image, game["question"], (550, 135), size=25, fill=(205, 210, 225, 255), anchor="mm")
    if not rows:
        draw_text(image, "No complete pair this round", (550, 320), size=34, anchor="mm")
    else:
        y = 205
        for index, row in enumerate(rows[:6], 1):
            choice, first, second = row
            label = game["left"] if choice == "a" else game["right"]
            draw.rounded_rectangle((120, y - 30, 980, y + 38), radius=18, fill=(35, 38, 56, 255))
            draw_text(image, str(index) + ". " + first[1] + " + " + second[1], (155, y + 5), size=23)
            draw_text(image, label, (940, y + 5), size=19, fill=(190, 195, 220, 255), anchor="ra")
            y += 72
    return card_to_bytes(image, "JPEG", 94)
