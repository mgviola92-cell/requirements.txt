from PIL import Image
from ui.card_generator import draw_text, card_to_bytes

def _card(title, lines):
    image = Image.new("RGBA", (1100, 650), (20, 22, 34, 255))
    draw_text(image, title, (550, 90), size=42, anchor="mm")
    y = 190
    for line in lines:
        draw_text(image, str(line), (550, y), size=27, anchor="mm")
        y += 70
    return card_to_bytes(image, "JPEG", 94)

def lobby_card(game):
    labels = {"duo":"DUO - 2", "squad":"SQUAD - 2 TO 4", "versus":"TEAM - 2v2"}
    lines = [labels.get(game.get("mode"), "CHOOSE MODE")]
    lines += [row.get("name", "Player") for row in game.get("players", {}).values()]
    return _card("PAIR CHALLENGE", lines)

def challenge_card(game):
    challenge = game.get("challenge") or {}
    options = challenge.get("options", ["A", "B"])
    return _card("PAIR CHALLENGE", [challenge.get("question", ""), "A - " + options[0], "B - " + options[1]])

def result_card(game):
    lines = ["SUCCESS" if game.get("success") else "ROUND OVER"]
    if game.get("mode") == "versus":
        scores = game.get("team_scores", {})
        lines.append("RED " + str(scores.get("red", 0)) + " - " + str(scores.get("blue", 0)) + " BLUE")
    return _card("PAIR CHALLENGE RESULT", lines)
