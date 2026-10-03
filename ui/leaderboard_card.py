# =========================================================
# 🏆 VISUAL LEADERBOARD CARD
# =========================================================

from ui.card_generator import (
    create_card,
    draw_panel,
    draw_text,
    card_to_bytes,
)

from config.ranks import get_rank_title


# =========================================================
# 🎨 GENERATE LEADERBOARD CARD
# =========================================================

def generate_leaderboard_card(
    players,
    title="GROUP RANKING",
):
    players = list(players or [])[:10]

    # -----------------------------------------
    # Dynamic card height
    # -----------------------------------------

    player_count = max(1, len(players))

    row_height = 78
    start_y = 165
    bottom_padding = 65

    card_height = (
        start_y
        + player_count * row_height
        + bottom_padding
    )

    card_height = max(
        360,
        card_height
    )

    card = create_card(
        width=1200,
        height=card_height,
        background=(18, 20, 26, 255),
    )

    # -----------------------------------------
    # Main panel
    # -----------------------------------------

    draw_panel(
        card,
        (
            45,
            45,
            1155,
            card_height - 45,
        ),
        fill=(32, 35, 44, 255),
        radius=38,
        outline=(210, 215, 225, 255),
        outline_width=2,
    )

    # -----------------------------------------
    # Title
    # -----------------------------------------

    draw_text(
        card,
        title,
        (85, 82),
        size=46,
    )

    if not players:

        draw_text(
            card,
            "No ranking data yet.",
            (85, 175),
            size=32,
        )

        return card

    # -----------------------------------------
    # Player rows
    # -----------------------------------------

    for index, player in enumerate(
        players,
        start=1,
    ):
        y = (
            start_y
            + (index - 1) * row_height
        )

        # Top 3 slightly different
        if index == 1:
            row_fill = (68, 58, 34, 255)

        elif index == 2:
            row_fill = (58, 61, 68, 255)

        elif index == 3:
            row_fill = (67, 48, 39, 255)

        else:
            row_fill = (43, 47, 58, 255)

        draw_panel(
            card,
            (
                78,
                y,
                1122,
                y + 62,
            ),
            fill=row_fill,
            radius=18,
        )

        # -------------------------------------
        # Data
        # -------------------------------------

        name = (
            player.get("name")
            or "Unknown"
        )

        # Name အရမ်းရှည်ရင် card မကျော်အောင်
        if len(name) > 18:
            name = name[:17] + "…"

        points = int(
            player.get(
                "points",
                0
            )
        )

        wins = int(
            player.get(
                "wins",
                0
            )
        )

        games = int(
            player.get(
                "games",
                0
            )
        )

        rank = get_rank_title(
            points
        )

        # Emoji medals ကို font compatibility
        # မသေချာလို့ plain rank number သုံးထားမည်
        position_text = f"#{index}"

        # -------------------------------------
        # Position
        # -------------------------------------

        draw_text(
            card,
            position_text,
            (105, y + 15),
            size=27,
        )

        # -------------------------------------
        # Name
        # -------------------------------------

        draw_text(
            card,
            name,
            (185, y + 13),
            size=29,
        )

        # -------------------------------------
        # Rank
        # -------------------------------------

        draw_text(
            card,
            rank,
            (530, y + 15),
            size=23,
        )

        # -------------------------------------
        # Points
        # -------------------------------------

        draw_text(
            card,
            f"{points} PTS",
            (790, y + 15),
            size=25,
        )

        # -------------------------------------
        # Wins / Games
        # -------------------------------------

        draw_text(
            card,
            f"W {wins}  /  G {games}",
            (960, y + 17),
            size=21,
        )

    return card


# =========================================================
# 📦 TELEGRAM READY BYTES
# =========================================================

def generate_leaderboard_card_bytes(
    players,
    title="GROUP RANKING",
):
    card = generate_leaderboard_card(
        players=players,
        title=title,
    )

    return card_to_bytes(
        card,
        image_format="PNG",
    )
