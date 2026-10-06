from PIL import Image
from ui.card_generator import draw_text, draw_panel, card_to_bytes

W, H = 1100, 650

def _base(title, subtitle=""):
    image = Image.new("RGBA", (W, H), (16, 19, 30, 255))
    draw_panel(image, (35, 30, 1065, 620), fill=(24, 29, 45, 245), radius=30, outline=(105, 115, 160, 255), outline_width=2)
    draw_text(image, title, (550, 78), size=42, anchor="mm")
    if subtitle:
        draw_text(image, subtitle, (550, 130), size=23, fill=(190, 198, 225, 255), anchor="mm")
    return image

def _short(text, limit=42):
    text = str(text or "")
    return text if len(text) <= limit else text[:limit-1] + "…"

def lobby_card(game):
    labels = {"duo":"CO-OP DUO • 2", "squad":"CO-OP SQUAD • 2-4", "versus":"TEAM VERSUS • 2v2"}
    image = _base("PAIR CHALLENGE", labels.get(game.get("mode"), "CHOOSE A MODE"))
    players = list(game.get("players", {}).values())
    draw_text(image, f"PLAYERS  {len(players)}", (550, 190), size=27, anchor="mm")
    y = 245
    for index, row in enumerate(players[:4], 1):
        draw_panel(image, (170, y-28, 930, y+30), fill=(34, 40, 60, 255), radius=18)
        draw_text(image, f"{index}. {_short(row.get('name','Player'), 28)}", (550, y), size=25, anchor="mm")
        y += 75
    if not players:
        draw_text(image, "Waiting for players…", (550, 320), size=28, anchor="mm")
    return card_to_bytes(image, "JPEG", 94)

def challenge_card(game):
    challenge = game.get("challenge") or {}
    options = challenge.get("options", ["A", "B"])
    round_no = game.get("round_no", 1)
    total = game.get("total_rounds", 5)
    kind = str(challenge.get("kind", "challenge")).upper()
    image = _base("PAIR CHALLENGE", f"ROUND {round_no}/{total} • {kind}")
    draw_panel(image, (95, 175, 1005, 335), fill=(31, 37, 57, 255), radius=24)
    draw_text(image, _short(challenge.get("question", ""), 58), (550, 255), size=29, anchor="mm")
    draw_panel(image, (95, 390, 520, 540), fill=(42, 48, 72, 255), radius=22)
    draw_panel(image, (580, 390, 1005, 540), fill=(42, 48, 72, 255), radius=22)
    draw_text(image, "A", (145, 430), size=25, anchor="mm")
    draw_text(image, _short(options[0], 24), (307, 475), size=28, anchor="mm")
    draw_text(image, "B", (630, 430), size=25, anchor="mm")
    draw_text(image, _short(options[1], 24), (792, 475), size=28, anchor="mm")
    return card_to_bytes(image, "JPEG", 94)

def result_card(game):
    mode = game.get("mode")
    image = _base("PAIR CHALLENGE RESULT", "5-ROUND MATCH COMPLETE")
    if mode == "versus":
        scores = game.get("match_scores", {})
        red, blue = scores.get("red", 0), scores.get("blue", 0)
        draw_text(image, "RED", (300, 235), size=34, anchor="mm")
        draw_text(image, str(red), (300, 335), size=82, anchor="mm")
        draw_text(image, "BLUE", (800, 235), size=34, anchor="mm")
        draw_text(image, str(blue), (800, 335), size=82, anchor="mm")
        winner = game.get("match_winner", "draw")
        label = "DRAW" if winner == "draw" else ("RED TEAM WINS" if winner == "red" else "BLUE TEAM WINS")
        draw_text(image, label, (550, 500), size=38, anchor="mm")
    else:
        cleared = game.get("cleared_rounds", 0)
        total = game.get("total_rounds", 5)
        draw_text(image, "TEAM RESULT", (550, 230), size=30, anchor="mm")
        draw_text(image, f"{cleared} / {total}", (550, 350), size=82, anchor="mm")
        draw_text(image, "CHALLENGES CLEARED", (550, 455), size=29, anchor="mm")
        draw_text(image, "SUCCESS" if game.get("success") else "TRY AGAIN", (550, 530), size=35, anchor="mm")
    return card_to_bytes(image, "JPEG", 94)
