# =========================================================
# 🎁 REWARD / POINT SYSTEM
# =========================================================

from database.players import (
    add_game_result,
    add_bonus_points as db_add_bonus_points,
)



def _team_battle_points(chat_id, user_id, points):
    """Mirror positive game rewards into an active Team Battle only."""
    try:
        points = int(points)
        if points <= 0:
            return
        from games.team_battle import record_points
        record_points(chat_id, user_id, points)
    except Exception as exc:
        print(f"Team Battle reward hook error: {exc}")


# =========================================================
# ⚙️ DEFAULT REWARD CONFIG
# =========================================================

GAME_REWARDS = {
    "coin": {
        "win": 5,
        "loss": -1,
        "draw": 0
    },

    "trivia": {
        "win": 10,
        "loss": 0,
        "draw": 0
    },

    "guess": {
        "win": 10,
        "loss": 0,
        "draw": 0
    },

    "emoji_guess": {
    "win": 10,
    "loss": 0,
    "draw": 0
    },

    "speed_tap": {
    "win": 10,
    "loss": 0,
    "draw": 0
    },
    
    "competitive_10": {
        "win": 10,
        "loss": -2,
        "draw": 0
    },

    "competitive_15": {
        "win": 15,
        "loss": -3,
        "draw": 0
    }
}


def get_reward(game_key, result):
    game = GAME_REWARDS.get(game_key)

    if game is None:
        return 0

    return int(game.get(result, 0))


def apply_game_result(
    chat_id,
    user_id,
    game_key,
    result
):
    if result not in (
        "win",
        "loss",
        "draw"
    ):
        print(f"❌ Invalid reward result: {result}")
        return False

    points = get_reward(
        game_key,
        result
    )

    success = add_game_result(
        chat_id,
        user_id,
        result,
        points=points
    )
    if success:
        _team_battle_points(chat_id, user_id, points)
    return success


def apply_custom_game_result(
    chat_id,
    user_id,
    result,
    points
):
    if result not in (
        "win",
        "loss",
        "draw"
    ):
        print(f"❌ Invalid custom result: {result}")
        return False

    points = int(points)
    success = add_game_result(
        chat_id,
        user_id,
        result,
        points=points
    )
    if success:
        _team_battle_points(chat_id, user_id, points)
    return success


def add_bonus_points(
    chat_id,
    user_id,
    points,
    reason=None
):
    points = int(points)

    success = db_add_bonus_points(
        chat_id,
        user_id,
        points
    )

    if success:
        _team_battle_points(chat_id, user_id, points)
        print(
            f"⭐ Bonus Points: "
            f"chat={chat_id}, "
            f"user={user_id}, "
            f"points={points}, "
            f"reason={reason}"
        )

    return success
