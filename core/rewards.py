# =========================================================
# 🎁 REWARD / POINT SYSTEM
# =========================================================

from database.players import (
    add_game_result,
    add_bonus_points as db_add_bonus_points,
)


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

    return add_game_result(
        chat_id,
        user_id,
        result,
        points=points
    )


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

    return add_game_result(
        chat_id,
        user_id,
        result,
        points=int(points)
    )


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
        print(
            f"⭐ Bonus Points: "
            f"chat={chat_id}, "
            f"user={user_id}, "
            f"points={points}, "
            f"reason={reason}"
        )

    return success
