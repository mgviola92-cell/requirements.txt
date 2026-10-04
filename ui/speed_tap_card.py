# =========================================================
# SPEED TAP VISUAL CARD
# =========================================================

from PIL import ImageDraw

from core.asset_manager import (
    random_asset_avoiding_recent,
)

from ui.card_generator import (
    create_card,
    add_background_image,
    draw_panel,
    draw_text,
    card_to_bytes,
)


# =========================================================
# CARD SETTINGS
# =========================================================

CARD_WIDTH = 900
CARD_HEIGHT = 560

SPEED_TAP_ASSET_FOLDER = "speed_tap"

BACKGROUND_RECENT_LIMIT = 12


# =========================================================
# BACKGROUND
# =========================================================

def get_speed_tap_background():

    return random_asset_avoiding_recent(
        "speed_tap_background",
        SPEED_TAP_ASSET_FOLDER,
        recent_limit=BACKGROUND_RECENT_LIMIT,
        recursive=True,
    )


# =========================================================
# BASE CARD
# =========================================================

def _create_speed_tap_base(
    background_path=None,
):

    card = create_card(
        width=CARD_WIDTH,
        height=CARD_HEIGHT,
        background=(
            15,
            17,
            24,
            255,
        ),
    )

    if background_path is not None:

        card = add_background_image(
            card,
            background_path,
            blur=1.5,
            darken=120,
        )

    # Dark readable content panel
    draw_panel(
        card,
        (
            50,
            50,
            850,
            510,
        ),
        fill=(
            10,
            12,
            18,
            205,
        ),
        radius=38,
        outline=(
            255,
            255,
            255,
            40,
        ),
        outline_width=2,
    )

    return card


# =========================================================
# DECORATIVE SPEED LINES
# =========================================================

def _draw_speed_lines(
    card,
    state,
):

    draw = ImageDraw.Draw(
        card
    )

    if state == "go":

        line_fill = (
            255,
            235,
            90,
            160,
        )

    elif state == "result":

        line_fill = (
            120,
            220,
            255,
            120,
        )

    else:

        line_fill = (
            255,
            255,
            255,
            65,
        )

    # left speed streaks
    for index in range(5):

        y = 150 + (
            index * 48
        )

        length = 70 + (
            index * 22
        )

        draw.rounded_rectangle(
            (
                70,
                y,
                70 + length,
                y + 8,
            ),
            radius=4,
            fill=line_fill,
        )

    # right speed streaks
    for index in range(5):

        y = 150 + (
            index * 48
        )

        length = 70 + (
            index * 22
        )

        draw.rounded_rectangle(
            (
                830 - length,
                y,
                830,
                y + 8,
            ),
            radius=4,
            fill=line_fill,
        )

    return card


# =========================================================
# WAIT CARD
# =========================================================

def generate_speed_tap_wait_card(
    wait_seconds=None,
    background_path=None,
):

    if background_path is None:
        background_path = (
            get_speed_tap_background()
        )

    card = _create_speed_tap_base(
        background_path
    )

    _draw_speed_lines(
        card,
        "wait",
    )

    draw_text(
        card,
        "SPEED TAP",
        (
            CARD_WIDTH // 2,
            105,
        ),
        size=58,
        fill=(
            255,
            255,
            255,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        "WAIT...",
        (
            CARD_WIDTH // 2,
            245,
        ),
        size=82,
        fill=(
            235,
            235,
            235,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        "GO ပေါ်လာမှ နှိပ်ပါ",
        (
            CARD_WIDTH // 2,
            345,
        ),
        size=34,
        fill=(
            225,
            225,
            225,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        "စောနှိပ်ရင် အနိုင်မရပါ",
        (
            CARD_WIDTH // 2,
            405,
        ),
        size=27,
        fill=(
            180,
            185,
            195,
            255,
        ),
        anchor="mm",
    )

    return card


# =========================================================
# GO CARD
# =========================================================

def generate_speed_tap_go_card(
    background_path=None,
):

    if background_path is None:
        background_path = (
            get_speed_tap_background()
        )

    card = _create_speed_tap_base(
        background_path
    )

    _draw_speed_lines(
        card,
        "go",
    )

    draw_text(
        card,
        "SPEED TAP",
        (
            CARD_WIDTH // 2,
            105,
        ),
        size=54,
        fill=(
            255,
            255,
            255,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        "GO!",
        (
            CARD_WIDTH // 2,
            250,
        ),
        size=125,
        fill=(
            255,
            235,
            90,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        "TAP NOW",
        (
            CARD_WIDTH // 2,
            365,
        ),
        size=46,
        fill=(
            255,
            255,
            255,
            255,
        ),
        anchor="mm",
    )

    return card


# =========================================================
# RESULT CARD
# =========================================================

def generate_speed_tap_result_card(
    winner_name,
    reaction_ms,
    reward_points=10,
    background_path=None,
):

    if background_path is None:
        background_path = (
            get_speed_tap_background()
        )

    winner_name = str(
        winner_name or "Player"
    )

    if len(winner_name) > 22:
        winner_name = (
            winner_name[:19]
            + "..."
        )

    try:
        reaction_ms = int(
            reaction_ms
        )
    except Exception:
        reaction_ms = 0

    try:
        reward_points = int(
            reward_points
        )
    except Exception:
        reward_points = 0

    card = _create_speed_tap_base(
        background_path
    )

    _draw_speed_lines(
        card,
        "result",
    )

    draw_text(
        card,
        "SPEED TAP RESULT",
        (
            CARD_WIDTH // 2,
            100,
        ),
        size=48,
        fill=(
            255,
            255,
            255,
            255,
        ),
        anchor="mm",
    )

    # Winner panel
    draw_panel(
        card,
        (
            185,
            160,
            715,
            275,
        ),
        fill=(
            255,
            255,
            255,
            28,
        ),
        radius=28,
    )

    draw_text(
        card,
        "WINNER",
        (
            CARD_WIDTH // 2,
            190,
        ),
        size=25,
        fill=(
            185,
            190,
            205,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        winner_name,
        (
            CARD_WIDTH // 2,
            235,
        ),
        size=43,
        fill=(
            255,
            255,
            255,
            255,
        ),
        anchor="mm",
    )

    # Stats
    draw_panel(
        card,
        (
            185,
            305,
            440,
            430,
        ),
        fill=(
            255,
            255,
            255,
            22,
        ),
        radius=25,
    )

    draw_panel(
        card,
        (
            460,
            305,
            715,
            430,
        ),
        fill=(
            255,
            255,
            255,
            22,
        ),
        radius=25,
    )

    draw_text(
        card,
        "REACTION",
        (
            312,
            340,
        ),
        size=22,
        fill=(
            180,
            185,
            200,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        f"{reaction_ms} ms",
        (
            312,
            390,
        ),
        size=38,
        fill=(
            255,
            255,
            255,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        "REWARD",
        (
            587,
            340,
        ),
        size=22,
        fill=(
            180,
            185,
            200,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        f"+{reward_points} Points",
        (
            587,
            390,
        ),
        size=34,
        fill=(
            255,
            235,
            90,
            255,
        ),
        anchor="mm",
    )

    return card


# =========================================================
# TIMEOUT CARD
# =========================================================

def generate_speed_tap_timeout_card(
    background_path=None,
):

    if background_path is None:
        background_path = (
            get_speed_tap_background()
        )

    card = _create_speed_tap_base(
        background_path
    )

    _draw_speed_lines(
        card,
        "wait",
    )

    draw_text(
        card,
        "SPEED TAP",
        (
            CARD_WIDTH // 2,
            115,
        ),
        size=52,
        fill=(
            255,
            255,
            255,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        "TIME'S UP",
        (
            CARD_WIDTH // 2,
            255,
        ),
        size=74,
        fill=(
            235,
            235,
            235,
            255,
        ),
        anchor="mm",
    )

    draw_text(
        card,
        "ဘယ်သူမှ အချိန်မီ မနှိပ်လိုက်ဘူး",
        (
            CARD_WIDTH // 2,
            355,
        ),
        size=31,
        fill=(
            200,
            205,
            215,
            255,
        ),
        anchor="mm",
    )

    return card


# =========================================================
# BYTES HELPERS
# =========================================================

def generate_speed_tap_wait_card_bytes(
    wait_seconds=None,
    background_path=None,
):

    card = generate_speed_tap_wait_card(
        wait_seconds=wait_seconds,
        background_path=background_path,
    )

    return card_to_bytes(
        card,
        image_format="JPEG",
        quality=88,
    )


def generate_speed_tap_go_card_bytes(
    background_path=None,
):

    card = generate_speed_tap_go_card(
        background_path=background_path,
    )

    return card_to_bytes(
        card,
        image_format="JPEG",
        quality=88,
    )


def generate_speed_tap_result_card_bytes(
    winner_name,
    reaction_ms,
    reward_points=10,
    background_path=None,
):

    card = generate_speed_tap_result_card(
        winner_name=winner_name,
        reaction_ms=reaction_ms,
        reward_points=reward_points,
        background_path=background_path,
    )

    return card_to_bytes(
        card,
        image_format="JPEG",
        quality=90,
    )


def generate_speed_tap_timeout_card_bytes(
    background_path=None,
):

    card = generate_speed_tap_timeout_card(
        background_path=background_path,
    )

    return card_to_bytes(
        card,
        image_format="JPEG",
        quality=88,
    )
