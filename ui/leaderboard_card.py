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
#
# players format:
# [
#     {
#         "name": "Player",
#         "points": 100,
#         "wins": 10,
#         "games": 15,
#     }
# ]
# =========================================================

def generate_leaderboard_card(
    players,
    title="🏆 GROUP RANKING",
):
    players = list(players or [])[:10]

    card = create_card(
        width=1200,
        height=900,
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
            855,
        ),
        fill=(25, 28, 36, 240),
        radius=40,
        outline=(255, 255, 255, 35),
        outline_width=2,
    )

    # -----------------------------------------
    # Title
    # -----------------------------------------

    draw_text(
        card,
        title,
        (90, 85),
        size=48,
    )

    # -----------------------------------------
    # Empty leaderboard
    # -----------------------------------------

    if not players:

        draw_text(
            card,
            "No ranking data yet.",
            (90, 180),
            size=34,
        )

        return card

    # -----------------------------------------
    # Player rows
    # -----------------------------------------

    start_y = 165
    row_height = 62

    medals = {
        1: "🥇",
        2: "🥈",
        3: "🥉",
    }

    for index, player in enumerate(
        players,
        start=1,
    ):
        y = (
            start_y
            + (index - 1) * row_height
        )

        # Top 3 နည်းနည်းပိုထင်ရှားအောင်
        if index <= 3:
            row_fill = (
                255,
                255,
                255,
                24,
            )
        else:
            row_fill = (
                255,
                255,
                255,
                12,
            )

        draw_panel(
            card,
            (
                80,
                y,
                1120,
                y + 50,
            ),
            fill=row_fill,
            radius=18,
        )

        icon = medals.get(
            index,
            f"{index}.",
        )

        name = (
            player.get("name")
            or "Unknown"
        )

        points = int(
            player.get(
                "points",
                0,
            )
        )

        wins = int(
            player.get(
                "wins",
                0,
            )
        )

        games = int(
            player.get(
                "games",
                0,
            )
        )

        rank = get_rank_title(
            points
        )

        # -------------------------------------
        # Position
        # -------------------------------------

        draw_text(
            card,
            icon,
            (105, y + 11),
            size=28,
        )

        # -------------------------------------
        # Name
        # -------------------------------------

        draw_text(
            card,
            name,
            (185, y + 11),
            size=27,
        )

        # -------------------------------------
        # Rank
        # -------------------------------------

        draw_text(
            card,
            rank,
            (500, y + 11),
            size=24,
        )

        # -------------------------------------
        # Points
        # -------------------------------------

        draw_text(
            card,
            f"{points} pts",
            (760, y + 11),
            size=24,
        )

        # -------------------------------------
        # Stats
        # -------------------------------------

        draw_text(
            card,
            f"W {wins}  •  G {games}",
            (915, y + 11),
            size=22,
        )

    return card


# =========================================================
# 📦 TELEGRAM READY BYTES
# =========================================================

def generate_leaderboard_card_bytes(
    players,
    title="🏆 GROUP RANKING",
):
    card = generate_leaderboard_card(
        players=players,
        title=title,
    )

    return card_to_bytes(
        card,
        image_format="PNG",
    )
