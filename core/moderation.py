"""Read Telegram's current member state before manual moderation actions."""
from core.customization import message_text

MESSAGES = {
    'missing_target': '❌ ဒီစာက User account ကပို့ထားတဲ့စာ မဟုတ်လို့ ဒီ command ကို သုံးလို့မရပါဘူး။',
    'ban_admin': '❌ {target_first_name} က Group Admin ဖြစ်နေလို့ ဘမ်းလို့မရပါဘူး။',
    'mute_admin': '❌ {target_first_name} က Group Admin ဖြစ်နေလို့ မြုလို့မရပါဘူး။',
    'already_banned': '🚫 {target_first_name} ကို ဘမ်းထားပြီးသားပါ။',
    'not_banned': '🔓 {target_first_name} ကို ဘမ်းထားတာမရှိလို့ ထပ်ဖြည်စရာမလိုပါဘူး။',
    'already_muted': '🔇 {target_first_name} ကို မြုထားပြီးသားပါ။',
    'not_muted': '🔊 {target_first_name} ကို မြုထားတာမရှိလို့ ထပ်ဖြည်စရာမလိုပါဘူး။',
    'banned_mute': '🚫 {target_first_name} ကို ဘမ်းထားလို့ မြုလို့မရပါဘူး။',
    'banned_unmute': '🚫 {target_first_name} ကို ဘမ်းထားပါတယ်။ ပြန်ဝင်ခွင့်ပေးချင်ရင် /မဘမ်း ကိုသုံးပါ။',
    'not_member': '❌ {target_first_name} က Group ထဲမှာ မရှိလို့ မြုလို့မရပါဘူး။',
}

def notice(bot, chat_id, target, action):
    """Return an editable explanation for a no-op; None permits the API action.

    Restricted users who can still send text are not considered muted (they may
    only have media restrictions). get_chat_member provides current expiry state.
    """
    key = None
    if target is None:
        key = 'missing_target'
    else:
        member = bot.get_chat_member(chat_id, target.id)
        status = member.status
        muted = status == 'restricted' and member.can_send_messages is False
        if action in ('ban', 'mute') and status in ('administrator', 'creator'):
            key = action + '_admin'
        elif action == 'ban' and status == 'kicked':
            key = 'already_banned'
        elif action == 'unban' and status != 'kicked':
            key = 'not_banned'
        elif action in ('mute', 'unmute') and status == 'kicked':
            key = 'banned_' + action
        elif action == 'mute' and (status == 'left' or status == 'restricted' and getattr(member, 'is_member', True) is False):
            key = 'not_member'
        elif action == 'mute' and muted:
            key = 'already_muted'
        elif action == 'unmute' and not muted:
            key = 'not_muted'
    if key:
        return message_text('msg.core.moderation.' + key, MESSAGES[key],
                            {'target_first_name': target.first_name if target else ''})
    return None
