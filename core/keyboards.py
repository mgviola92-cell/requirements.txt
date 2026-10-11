from core.customization import message_text as _custom_text, setting_value as _custom_setting, bank_text as _custom_bank
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
        _custom_text('msg.core.keyboards.vote_keyboard.1502f51af1', '🅰️ {option_a_text}', {'option_a_text': f'{option_a_text}'}),
        f"{vote_prefix}:{session_id}:A",

        _custom_text('msg.core.keyboards.vote_keyboard.dc02ec4fc9', '🅱️ {option_b_text}', {'option_b_text': f'{option_b_text}'}),
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
        _custom_text('msg.core.keyboards.accept_decline_keyboard.a7ecf6a0fc', '✅ ACCEPT', {}),
        f"{prefix}:{session_id}:accept",

        _custom_text('msg.core.keyboards.accept_decline_keyboard.ebdb099f62', '❌ DECLINE', {}),
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
        text = _custom_text('msg.core.keyboards.boss_attack_keyboard.87bd70daf1', '🏁 RAID FINISHED', {})
        callback = f"boss:{raid_id}:closed"
    else:
        text = _custom_text('msg.core.keyboards.boss_attack_keyboard.750ba0278d', '⚔️ ATTACK', {})
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
        text = _custom_text('msg.core.keyboards.speed_tap_keyboard.a4231c927e', '⚡ TAP NOW', {})
        callback = f"speedtap:{game_id}:tap"
    else:
        text = _custom_text('msg.core.keyboards.speed_tap_keyboard.5e26cfbffb', '🏁 FINISHED', {})
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
        text = _custom_text('msg.core.keyboards.claim_keyboard.56ff3c13b9', '🎁 CLAIM', {})
        callback = (
            f"{event_type}:"
            f"{event_id}:claim"
        )
    else:
        text = _custom_text('msg.core.keyboards.claim_keyboard.a63c5ef091', '🏁 EVENT ENDED', {})
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
