# =========================================================
# 🏆 VISUAL RANK CARD
# =========================================================

from config.ranks import (
    get_rank_data,
    get_rank_progress,
)

from ui.card_generator import (
    create_card,
    add_background_image,
    draw_panel,
    draw_text,
    draw_progress_bar,
    paste_image,
    card_to_bytes,
)


# =========================================================
# 🎨 GENERATE PLAYER RANK CARD
# =========================================================

def generate_rank_card(
    player_name,
    points,
    wins,
    games,
    losses=0,
    draws=0,
    background_path=None,
    badge_path=None,
):
    points = max(0, int(points))
    wins = max(0, int(wins))
    games = max(0, int(games))
    losses = max(0, int(losses))
    draws = max(0, int(draws))

    rank = get_rank_data(points)
    progress = get_rank_progress(points)

    # -----------------------------------------
    # Base card
    # -----------------------------------------

    card = create_card(
        width=1200,
        height=675,
        background=(20, 22, 28, 255),
    )

    # -----------------------------------------
    # Optional background artwork
    # -----------------------------------------

    if background_path:
        card = add_background_image(
            card,
            background_path,
            blur=1.5,
            darken=105,
        )

    # -----------------------------------------
    # Main panel
    # -----------------------------------------

    draw_panel(
        card,
        (
            55,
            55,
            1145,
            620,
        ),
        fill=(18, 20, 27, 225),
        radius=40,
        outline=(255, 255, 255, 40),
        outline_width=2,
    )

    # -----------------------------------------
    # Rank badge area
    # -----------------------------------------

    draw_panel(
        card,
        (
            85,
            105,
            385,
            405,
        ),
        fill=(255, 255, 255, 18),
        radius=32,
    )

    if badge_path:
        paste_image(
            card,
            badge_path,
            (
                110,
                130,
                360,
                380,
            ),
            rounded_radius=24,
        )

    # -----------------------------------------
    # Player info
    # -----------------------------------------

    draw_text(
        card,
        player_name,
        (440, 115),
        size=52,
    )

    draw_text(
        card,
        rank["name"],
        (440, 180),
        size=44,
    )

    draw_text(
        card,
        f"{points} POINTS",
        (440, 245),
        size=38,
    )

    # -----------------------------------------
    # Progress
    # -----------------------------------------

    if progress["next_rank"] is None:
        progress_text = "MAX RANK"
    else:
        progress_text = (
            f"{progress['current']} / "
            f"{progress['needed']} → "
            f"{progress['next_rank']}"
        )

    draw_text(
        card,
        progress_text,
        (440, 320),
        size=28,
    )

    draw_progress_bar(
        card,
        (
            440,
            365,
            1070,
            405,
        ),
        progress["percent"],
    )

    draw_text(
        card,
        f"{progress['percent']}%",
        (1070, 330),
        size=24,
        anchor="ra",
    )

    # -----------------------------------------
    # Stats area
    # -----------------------------------------

    stat_y = 485

    draw_text(
        card,
        f"WINS  {wins}",
        (130, stat_y),
        size=28,
    )

    draw_text(
        card,
        f"GAMES  {games}",
        (390, stat_y),
        size=28,
    )

    draw_text(
        card,
        f"LOSSES  {losses}",
        (680, stat_y),
        size=28,
    )

    draw_text(
        card,
        f"DRAWS  {draws}",
        (950, stat_y),
        size=28,
    )

    return card


# =========================================================
# 📦 TELEGRAM READY BYTES
# =========================================================

def generate_rank_card_bytes(
    player_name,
    points,
    wins,
    games,
    losses=0,
    draws=0,
    background_path=None,
    badge_path=None,
):
    card = generate_rank_card(
        player_name=player_name,
        points=points,
        wins=wins,
        games=games,
        losses=losses,
        draws=draws,
        background_path=background_path,
        badge_path=badge_path,
    )

    return card_to_bytes(
        card,
        image_format="PNG",
    )
