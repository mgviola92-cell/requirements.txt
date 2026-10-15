import ast,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
from core import moderation,customization

class ModerationTests(unittest.TestCase):
    def setUp(self):
        self.bot=MagicMock();self.target=NS(id=42,first_name='Tester')
    def check(self,action,status,expected,**fields):
        self.bot.get_chat_member.return_value=NS(status=status,**fields)
        result=moderation.notice(self.bot,-42,self.target,action)
        if expected is None:self.assertIsNone(result)
        else:self.assertEqual(result,moderation.MESSAGES[expected].format(target_first_name='Tester'))
    def test_admin_and_creator_protected(self):
        for status in ('administrator','creator'):
            for action in ('ban','mute'):self.check(action,status,action+'_admin')
    def test_ban_and_unban_noops(self):
        self.check('ban','kicked','already_banned')
        for status in ('member','left','restricted','administrator','creator'):
            self.check('unban',status,'not_banned',can_send_messages=True)
        self.check('unban','kicked',None)
        self.check('ban','member',None)
    def test_mute_state_not_media_restrictions(self):
        self.check('mute','restricted','already_muted',can_send_messages=False)
        self.check('unmute','restricted',None,can_send_messages=False)
        self.check('mute','restricted',None,can_send_messages=True)
        self.check('unmute','restricted','not_muted',can_send_messages=True)
        self.check('unmute','member','not_muted')
        self.check('mute','member',None)
        self.check('mute','left','not_member')
        self.check('mute','restricted','not_member',can_send_messages=False,is_member=False)
        for action in ('mute','unmute'):self.check(action,'kicked','banned_'+action)
    def test_anonymous_sender_and_editor_keys(self):
        self.assertEqual(moderation.notice(self.bot,-42,None,'ban'),moderation.MESSAGES['missing_target'])
        self.bot.get_chat_member.assert_not_called()
        for key,value in moderation.MESSAGES.items():
            self.assertEqual(customization.CATALOG['msg.core.moderation.'+key]['default'],value)
    def test_handlers_do_not_mutate_for_noops_and_keep_existing_success(self):
        tree=ast.parse(Path('bot.py').read_text())
        for fn,action,method in [('ban_user','ban','ban_chat_member'),('unban_user','unban','unban_chat_member'),('mute_user','mute','restrict_chat_member'),('unmute_user','unmute','restrict_chat_member')]:
            node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==fn)
            node.decorator_list=[]
            env={'bot':self.bot,'is_admin':lambda m:True,'_custom_text':lambda k,d,f:d.format(**f),'ChatPermissions':lambda **kw:kw}
            exec(compile(ast.Module(body=[node],type_ignores=[]),'bot.py','exec'),env)
            message=NS(chat=NS(id=-42,type='supergroup'),reply_to_message=NS(from_user=self.target))
            status={'ban':'administrator','unban':'member','mute':'administrator','unmute':'member'}[action]
            self.bot.reset_mock();self.bot.get_chat_member.return_value=NS(status=status)
            env[fn](message);getattr(self.bot,method).assert_not_called();self.bot.reply_to.assert_called_once()
            self.bot.reset_mock();self.bot.get_chat_member.return_value=NS(status='kicked' if action=='unban' else 'restricted' if action=='unmute' else 'member',can_send_messages=False)
            env[fn](message);getattr(self.bot,method).assert_called_once()

if __name__=='__main__':unittest.main()
