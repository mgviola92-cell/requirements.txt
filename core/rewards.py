# =========================================================
# 🎁 REWARD / POINT SYSTEM
# =========================================================

from database.players import add_game_result


# =========================================================
# ⚙️ DEFAULT REWARD CONFIG
#
# Permanent Rank Points
# =========================================================

GAME_REWARDS = {

    # -----------------------------------------
    # EXISTING GAMES
    # -----------------------------------------

    "coin": {
        "win": 5,
        "loss": -1,
        "draw": 0
    },

    "trivia": {
        "win": 10,
        # Wrong answer = loss မဟုတ်ပါ
        "loss": 0,
        "draw": 0
    },

    "guess": {
        "win": 10,
        # Wrong guess = loss မဟုတ်ပါ
        "loss": 0,
        "draw": 0
    },

    # -----------------------------------------
    # FUTURE / COMPETITIVE DEFAULTS
    # -----------------------------------------

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


# =========================================================
# 🔎 GET REWARD VALUE
# =========================================================

def get_reward(game_key, result):

    game = GAME_REWARDS.get(game_key)

    if game is None:
        return 0

    return int(
        game.get(result, 0)
    )


# =========================================================
# 🎮 APPLY STANDARD GAME RESULT
#
# Example:
#
# apply_game_result(
#     chat_id,
#     user_id,
#     "coin",
#     "win"
# )
#
# =========================================================

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
        print(
            f"❌ Invalid reward result: {result}"
        )
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


# =========================================================
# ⭐ CUSTOM POINT RESULT
#
# Future games:
# Boss Raid
# Team Battle
# Daily Challenge
# Achievements
# etc.
#
# တိကျတဲ့ reward amount ကို manually သတ်မှတ်ချင်ရင် သုံးမည်။
# =========================================================

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
        print(
            f"❌ Invalid custom result: {result}"
        )
        return False

    return add_game_result(
        chat_id,
        user_id,
        result,
        points=int(points)
    )


# =========================================================
# 🛡️ NON-GAME BONUS
#
# Achievement / Daily Challenge / Event rewards တွေအတွက်
# Games/Wins/Losses counters မတိုးသင့်တာကြောင့်
# အခုတော့ placeholder ပဲထားမည်။
#
# Database reward transaction system ထည့်တဲ့အဆင့်မှာ
# ဒီ function ကို complete လုပ်မည်။
# =========================================================

def add_bonus_points(
    chat_id,
    user_id,
    points,
    reason=None
):

    raise NotImplementedError(
        "Bonus Point System ကို "
        "Reward Transactions Database အဆင့်မှာ "
        "ချိတ်ဆက်မည်။"
    )
