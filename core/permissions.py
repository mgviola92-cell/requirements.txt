# =========================================================
# 🛡️ TELEGRAM PERMISSION HELPERS
# =========================================================


# =========================================================
# 👑 IS USER ADMIN?
# =========================================================

def is_user_admin(
    bot,
    chat_id,
    user_id
):
    try:
        member = bot.get_chat_member(
            chat_id,
            user_id
        )

        return member.status in (
            "administrator",
            "creator"
        )

    except Exception as e:
        print(
            f"❌ Admin Check Error: {e}"
        )
        return False


# =========================================================
# 🤖 GET BOT MEMBER INFO
# =========================================================

def get_bot_member(
    bot,
    chat_id
):
    try:
        bot_user = bot.get_me()

        return bot.get_chat_member(
            chat_id,
            bot_user.id
        )

    except Exception as e:
        print(
            f"❌ Bot Member Check Error: {e}"
        )
        return None


# =========================================================
# 📌 CAN PIN MESSAGES?
# =========================================================

def can_pin_messages(
    bot,
    chat_id
):
    member = get_bot_member(
        bot,
        chat_id
    )

    if member is None:
        return False

    if member.status == "creator":
        return True

    if member.status != "administrator":
        return False

    return bool(
        getattr(
            member,
            "can_pin_messages",
            False
        )
    )


# =========================================================
# 🗑️ CAN DELETE MESSAGES?
# =========================================================

def can_delete_messages(
    bot,
    chat_id
):
    member = get_bot_member(
        bot,
        chat_id
    )

    if member is None:
        return False

    if member.status == "creator":
        return True

    if member.status != "administrator":
        return False

    return bool(
        getattr(
            member,
            "can_delete_messages",
            False
        )
    )


# =========================================================
# 🚫 CAN RESTRICT MEMBERS?
# =========================================================

def can_restrict_members(
    bot,
    chat_id
):
    member = get_bot_member(
        bot,
        chat_id
    )

    if member is None:
        return False

    if member.status == "creator":
        return True

    if member.status != "administrator":
        return False

    return bool(
        getattr(
            member,
            "can_restrict_members",
            False
        )
    )


# =========================================================
# 📌 SAFE PIN
# =========================================================

def safe_pin_message(
    bot,
    chat_id,
    message_id,
    disable_notification=False
):
    if not can_pin_messages(
        bot,
        chat_id
    ):
        return False

    try:
        bot.pin_chat_message(
            chat_id,
            message_id,
            disable_notification=
                disable_notification
        )

        return True

    except Exception as e:
        print(
            f"❌ Pin Message Error: {e}"
        )
        return False


# =========================================================
# 📌 SAFE UNPIN
# =========================================================

def safe_unpin_message(
    bot,
    chat_id,
    message_id=None
):
    if not can_pin_messages(
        bot,
        chat_id
    ):
        return False

    try:
        if message_id is None:
            bot.unpin_chat_message(
                chat_id
            )
        else:
            bot.unpin_chat_message(
                chat_id,
                message_id
            )

        return True

    except Exception as e:
        print(
            f"❌ Unpin Message Error: {e}"
        )
        return False


# =========================================================
# 🗑️ SAFE DELETE
# =========================================================

def safe_delete_message(
    bot,
    chat_id,
    message_id
):
    try:
        bot.delete_message(
            chat_id,
            message_id
        )

        return True

    except Exception as e:
        print(
            f"❌ Delete Message Error: {e}"
        )
        return False
