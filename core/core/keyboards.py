# =========================================================
# ⌨️ INLINE KEYBOARD HELPERS
# =========================================================

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# =========================================================
# 🔘 SINGLE BUTTON
# =========================================================

def single_button(
    text,
    callback_data
):
    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            text=text,
            callback_data=callback_data
        )
    )

    return markup


# =========================================================
# ↔️ TWO BUTTONS
# =========================================================

def two_buttons(
    text_a,
    callback_a,
    text_b,
    callback_b
):
    markup = InlineKeyboardMarkup(
        row_width=2
    )

    markup.add(
        InlineKeyboardButton(
            text=text_a,
            callback_data=callback_a
        ),
        InlineKeyboardButton(
            text=text_b,
            callback_data=callback_b
        )
    )

    return markup


# =========================================================
# 🗳️ VOTE KEYBOARD
#
# WYR / This or That / Roast Battle
# =========================================================

def vote_keyboard(
    option_a_text,
    option_b_text,
    vote_prefix,
    session_id
):
    return two_buttons(
        f"🅰️ {option_a_text}",
        f"{vote_prefix}:{session_id}:A",

        f"🅱️ {option_b_text}",
        f"{vote_prefix}:{session_id}:B"
    )


# =========================================================
# ✅ ACCEPT / ❌ DECLINE
#
# Pair Challenge / Roast Battle
# =========================================================

def accept_decline_keyboard(
    prefix,
    session_id
):
    return two_buttons(
        "✅ ACCEPT",
        f"{prefix}:{session_id}:accept",

        "❌ DECLINE",
        f"{prefix}:{session_id}:decline"
    )


# =========================================================
# ⚔️ ATTACK BUTTON
#
# Boss Raid
# =========================================================

def boss_attack_keyboard(
    raid_id,
    disabled=False
):
    markup = InlineKeyboardMarkup()

    if disabled:
        text = "🏁 RAID FINISHED"
        callback = f"boss:{raid_id}:closed"
    else:
        text = "⚔️ ATTACK"
        callback = f"boss:{raid_id}:attack"

    markup.add(
        InlineKeyboardButton(
            text=text,
            callback_data=callback
        )
    )

    return markup


# =========================================================
# ⚡ SPEED TAP BUTTON
# =========================================================

def speed_tap_keyboard(
    game_id,
    active=True
):
    markup = InlineKeyboardMarkup()

    if active:
        text = "⚡ TAP NOW"
        callback = f"speedtap:{game_id}:tap"
    else:
        text = "🏁 FINISHED"
        callback = f"speedtap:{game_id}:closed"

    markup.add(
        InlineKeyboardButton(
            text=text,
            callback_data=callback
        )
    )

    return markup


# =========================================================
# 🎁 CLAIM BUTTON
#
# Lucky Drop / Random Events
# =========================================================

def claim_keyboard(
    event_type,
    event_id,
    active=True
):
    markup = InlineKeyboardMarkup()

    if active:
        text = "🎁 CLAIM"
        callback = (
            f"{event_type}:"
            f"{event_id}:claim"
        )
    else:
        text = "🏁 EVENT ENDED"
        callback = (
            f"{event_type}:"
            f"{event_id}:closed"
        )

    markup.add(
        InlineKeyboardButton(
            text=text,
            callback_data=callback
        )
    )

    return markup


# =========================================================
# 📄 PAGINATION
#
# Achievement Gallery / Leaderboard
# =========================================================

def pagination_keyboard(
    prefix,
    page,
    total_pages
):
    markup = InlineKeyboardMarkup(
        row_width=3
    )

    buttons = []

    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=(
                    f"{prefix}:page:{page - 1}"
                )
            )
        )

    buttons.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data=(
                f"{prefix}:noop"
            )
        )
    )

    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=(
                    f"{prefix}:page:{page + 1}"
                )
            )
        )

    markup.add(*buttons)

    return markup
