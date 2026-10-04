# =========================================================
# ⚡ SPEED TAP VISUAL CARD
# =========================================================

from PIL import ImageDraw

from core.asset_manager import random_asset_avoiding_recent
from ui.card_generator import (
    create_card,
    add_background_image,
    draw_panel,
    draw_text,
    card_to_bytes,
)

CARD_WIDTH = 900
CARD_HEIGHT = 560
SPEED_TAP_ASSET_FOLDER = "speed_tap"
BACKGROUND_RECENT_LIMIT = 12

BG_DARK = (13, 16, 24, 255)
PANEL_MAIN = (20, 25, 36, 255)
PANEL_SOFT = (31, 38, 52, 255)
PANEL_ACCENT = (42, 50, 66, 255)
TEXT_MAIN = (245, 247, 250, 255)
TEXT_MUTED = (170, 180, 196, 255)
ACCENT_YELLOW = (255, 221, 78, 255)
ACCENT_GREEN = (102, 232, 154, 255)
ACCENT_BLUE = (103, 193, 255, 255)
ACCENT_PURPLE = (180, 130, 255, 255)
ACCENT_RED = (255, 117, 117, 255)


def get_speed_tap_background():
    return random_asset_avoiding_recent(
        "speed_tap_background",
        SPEED_TAP_ASSET_FOLDER,
        recent_limit=BACKGROUND_RECENT_LIMIT,
        recursive=True,
    )


def _create_speed_tap_base(background_path=None):
    card = create_card(
        width=CARD_WIDTH,
        height=CARD_HEIGHT,
        background=BG_DARK,
    )

    if background_path is not None:
        card = add_background_image(
            card,
            background_path,
            blur=2.0,
            darken=165,
        )

    draw_panel(
        card,
        (42, 38, 858, 522),
        fill=PANEL_MAIN,
        radius=42,
        outline=(76, 88, 110, 255),
        outline_width=2,
    )
    return card


def _draw_speed_lines(card, state):
    draw = ImageDraw.Draw(card)

    if state == "go":
        line_fill = ACCENT_YELLOW
    elif state == "result":
        line_fill = ACCENT_BLUE
    elif state == "pending":
        line_fill = ACCENT_PURPLE
    elif state == "timeout":
        line_fill = ACCENT_RED
    else:
        line_fill = (110, 122, 142, 255)

    for index in range(5):
        y = 158 + (index * 47)
        length = 68 + (index * 18)
        draw.rounded_rectangle((72, y, 72 + length, y + 7), radius=4, fill=line_fill)
        draw.rounded_rectangle((828 - length, y, 828, y + 7), radius=4, fill=line_fill)

    return card


def generate_speed_tap_pending_card(background_path=None):
    if background_path is None:
        background_path = get_speed_tap_background()

    card = _create_speed_tap_base(background_path)
    _draw_speed_lines(card, "pending")

    draw_text(card, "SPEED TAP", (CARD_WIDTH // 2, 95), size=50, fill=TEXT_MAIN, anchor="mm")
    draw_text(card, "∞", (CARD_WIDTH // 2, 255), size=155, fill=ACCENT_PURPLE, anchor="mm")
    draw_text(card, "RANDOM START", (CARD_WIDTH // 2, 365), size=35, fill=TEXT_MAIN, anchor="mm")
    draw_text(card, "ဘယ်အချိန်စမလဲ မသိရဘူး 👀", (CARD_WIDTH // 2, 420), size=28, fill=TEXT_MUTED, anchor="mm")
    return card


def generate_speed_tap_wait_card(wait_seconds=None, background_path=None):
    if background_path is None:
        background_path = get_speed_tap_background()

    card = _create_speed_tap_base(background_path)
    _draw_speed_lines(card, "wait")

    draw_text(card, "SPEED TAP", (CARD_WIDTH // 2, 95), size=50, fill=TEXT_MAIN, anchor="mm")
    draw_text(card, "WAIT...", (CARD_WIDTH // 2, 245), size=88, fill=TEXT_MAIN, anchor="mm")
    draw_text(card, "GO ပေါ်လာမှ နှိပ်ပါ", (CARD_WIDTH // 2, 350), size=36, fill=ACCENT_YELLOW, anchor="mm")
    draw_text(card, "စောနှိပ်ရင် အနိုင်မရပါ", (CARD_WIDTH // 2, 412), size=27, fill=TEXT_MUTED, anchor="mm")
    return card


def generate_speed_tap_go_card(background_path=None):
    if background_path is None:
        background_path = get_speed_tap_background()

    card = _create_speed_tap_base(background_path)
    _draw_speed_lines(card, "go")

    draw_text(card, "SPEED TAP", (CARD_WIDTH // 2, 90), size=46, fill=TEXT_MAIN, anchor="mm")
    draw_text(card, "GO!", (CARD_WIDTH // 2, 245), size=135, fill=ACCENT_GREEN, anchor="mm")
    draw_text(card, "⚡ TAP NOW ⚡", (CARD_WIDTH // 2, 375), size=43, fill=ACCENT_YELLOW, anchor="mm")
    return card


def generate_speed_tap_result_card(
    winner_name,
    reaction_ms,
    reward_points,
    jackpot_bonus=0,
    background_path=None,
):
    if background_path is None:
        background_path = get_speed_tap_background()

    winner_name = str(winner_name or "Player")
    if len(winner_name) > 22:
        winner_name = winner_name[:19] + "..."

    try:
        reaction_ms = int(reaction_ms)
    except Exception:
        reaction_ms = 0

    try:
        reward_points = int(reward_points)
    except Exception:
        reward_points = 0

    try:
        jackpot_bonus = int(jackpot_bonus)
    except Exception:
        jackpot_bonus = 0

    card = _create_speed_tap_base(background_path)
    _draw_speed_lines(card, "result")

    draw_text(card, "SPEED TAP RESULT", (CARD_WIDTH // 2, 82), size=43, fill=TEXT_MAIN, anchor="mm")

    draw_panel(
        card,
        (190, 130, 710, 252),
        fill=PANEL_SOFT,
        radius=28,
        outline=(74, 88, 112, 255),
        outline_width=2,
    )
    draw_text(card, "🏆 WINNER", (CARD_WIDTH // 2, 162), size=24, fill=ACCENT_YELLOW, anchor="mm")
    draw_text(card, winner_name, (CARD_WIDTH // 2, 210), size=42, fill=TEXT_MAIN, anchor="mm")

    draw_panel(
        card,
        (175, 292, 430, 430),
        fill=PANEL_SOFT,
        radius=26,
        outline=(70, 84, 108, 255),
        outline_width=2,
    )
    draw_text(card, "REACTION", (302, 327), size=21, fill=TEXT_MUTED, anchor="mm")
    draw_text(card, f"{reaction_ms} ms", (302, 383), size=38, fill=ACCENT_BLUE, anchor="mm")

    draw_panel(
        card,
        (470, 292, 725, 430),
        fill=PANEL_ACCENT,
        radius=26,
        outline=(96, 104, 126, 255),
        outline_width=2,
    )
    draw_text(card, "REWARD", (597, 327), size=21, fill=TEXT_MUTED, anchor="mm")
    draw_text(card, f"+{reward_points} Points", (597, 383), size=33, fill=ACCENT_YELLOW, anchor="mm")

    if jackpot_bonus > 0:
        draw_panel(
            card,
            (285, 458, 615, 505),
            fill=(72, 50, 96, 255),
            radius=22,
            outline=ACCENT_PURPLE,
            outline_width=2,
        )
        draw_text(card, f"✨ JACKPOT +{jackpot_bonus}", (CARD_WIDTH // 2, 482), size=24, fill=TEXT_MAIN, anchor="mm")

    return card


def generate_speed_tap_timeout_card(background_path=None):
    if background_path is None:
        background_path = get_speed_tap_background()

    card = _create_speed_tap_base(background_path)
    _draw_speed_lines(card, "timeout")

    draw_text(card, "SPEED TAP", (CARD_WIDTH // 2, 105), size=48, fill=TEXT_MAIN, anchor="mm")
    draw_text(card, "TIME'S UP", (CARD_WIDTH // 2, 255), size=78, fill=ACCENT_RED, anchor="mm")
    draw_text(card, "ဘယ်သူမှ အချိန်မီ မနှိပ်လိုက်ဘူး", (CARD_WIDTH // 2, 370), size=31, fill=TEXT_MUTED, anchor="mm")
    return card


def generate_speed_tap_pending_card_bytes(background_path=None):
    card = generate_speed_tap_pending_card(background_path=background_path)
    return card_to_bytes(card, image_format="JPEG", quality=90)


def generate_speed_tap_wait_card_bytes(wait_seconds=None, background_path=None):
    card = generate_speed_tap_wait_card(
        wait_seconds=wait_seconds,
        background_path=background_path,
    )
    return card_to_bytes(card, image_format="JPEG", quality=90)


def generate_speed_tap_go_card_bytes(background_path=None):
    card = generate_speed_tap_go_card(background_path=background_path)
    return card_to_bytes(card, image_format="JPEG", quality=90)


def generate_speed_tap_result_card_bytes(
    winner_name,
    reaction_ms,
    reward_points,
    jackpot_bonus=0,
    background_path=None,
):
    card = generate_speed_tap_result_card(
        winner_name=winner_name,
        reaction_ms=reaction_ms,
        reward_points=reward_points,
        jackpot_bonus=jackpot_bonus,
        background_path=background_path,
    )
    return card_to_bytes(card, image_format="JPEG", quality=92)


def generate_speed_tap_timeout_card_bytes(background_path=None):
    card = generate_speed_tap_timeout_card(background_path=background_path)
    return card_to_bytes(card, image_format="JPEG", quality=90)
