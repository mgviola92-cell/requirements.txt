from core.customization import message_text as _custom_text, setting_value as _custom_setting, bank_text as _custom_bank
from PIL import Image, ImageDraw
from ui.card_generator import draw_text, card_to_bytes
from games.team_battle import top_members

W, H = 1100, 650

def _short(name, limit=22):
    name = str(name or "Player")
    return name if len(name) <= limit else name[:limit-1] + "…"

def generate_team_battle_card(battle, stage="live"):
    img = Image.new("RGBA", (W, H), (12, 14, 22, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((28, 28, 1072, 622), radius=34, fill=(20, 23, 34, 255), outline=(85, 90, 110, 255), width=3)
    d.rounded_rectangle((48, 130, 536, 575), radius=28, fill=(76, 20, 30, 255), outline=(245, 72, 92, 255), width=4)
    d.rounded_rectangle((564, 130, 1052, 575), radius=28, fill=(20, 42, 82, 255), outline=(65, 145, 255, 255), width=4)

    label = {"live": "LIVE BATTLE", "half": "HALF-TIME", "final": "FINAL RESULT"}.get(stage, "TEAM BATTLE")
    draw_text(img, _custom_text('msg.ui.team_battle_card.generate_team_battle_card.039e89b7b0', 'TEAM BATTLE  •  RED vs BLUE', {}), (550, 70), size=38, anchor="mm")
    draw_text(img, label, (550, 108), size=20, fill=(205, 210, 225, 255), anchor="mm")

    red = int(battle.get("scores", {}).get("red", 0))
    blue = int(battle.get("scores", {}).get("blue", 0))
    draw_text(img, _custom_text('msg.ui.team_battle_card.generate_team_battle_card.66e64e5eb3', '🔴 RED', {}), (292, 180), size=34, anchor="mm")
    draw_text(img, str(red), (292, 245), size=62, anchor="mm")
    draw_text(img, _custom_text('msg.ui.team_battle_card.generate_team_battle_card.b3fe66b9a2', '🔵 BLUE', {}), (808, 180), size=34, anchor="mm")
    draw_text(img, str(blue), (808, 245), size=62, anchor="mm")

    draw_text(img, _custom_text('msg.ui.team_battle_card.generate_team_battle_card.528eda0fd9', 'TOP CONTRIBUTORS', {}), (292, 315), size=22, anchor="mm")
    draw_text(img, _custom_text('msg.ui.team_battle_card.generate_team_battle_card.528eda0fd9', 'TOP CONTRIBUTORS', {}), (808, 315), size=22, anchor="mm")
    for team, x in (("red", 95), ("blue", 611)):
        rows = top_members(battle, team, 3)
        if not rows:
            draw_text(img, _custom_text('msg.ui.team_battle_card.generate_team_battle_card.c07df0bbf9', 'Waiting for points…', {}), (x, 365), size=20, fill=(190, 195, 210, 255))
        for i, row in enumerate(rows, 1):
            draw_text(img, f"{i}. {_short(row.get('name'))}", (x, 350 + i*55), size=22)
            draw_text(img, f"+{int(row.get('points',0))}", (x+390, 350 + i*55), size=22, anchor="ra")

    if stage == "final":
        if red > blue:
            result = _custom_text('msg.ui.team_battle_card.generate_team_battle_card.0aeddd57fe', '🔴 RED TEAM WINS!', {})
        elif blue > red:
            result = _custom_text('msg.ui.team_battle_card.generate_team_battle_card.61397559d7', '🔵 BLUE TEAM WINS!', {})
        else:
            result = _custom_text('msg.ui.team_battle_card.generate_team_battle_card.3cbe00b61b', '🤝 DRAW!', {})
        draw_text(img, result, (550, 605), size=27, anchor="mm")
    else:
        draw_text(img, _custom_text('msg.ui.team_battle_card.generate_team_battle_card.bc3cdb6f32', 'Game points = Rank Points + Team Battle score', {}), (550, 605), size=19, fill=(185, 190, 205, 255), anchor="mm")
    return card_to_bytes(img, "JPEG", 94)
