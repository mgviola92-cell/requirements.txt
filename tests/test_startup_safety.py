import contextlib
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, MagicMock, patch
from core.startup_safety import FreshUpdatesBot, AutoPostGate, abandoned

class StartupSafetyTests(unittest.TestCase):
    def test_stale_activity_filtered_but_old_menu_click_kept(self):
        bot=object.__new__(FreshUpdatesBot);bot.started_at=1000
        old=NS(message=NS(date=999));delayed=NS(message=NS(date=1050))
        click=NS(callback_query=NS(message=NS(date=10)));member=NS(my_chat_member=NS())
        with patch('core.startup_safety.time.time',return_value=1200),patch('telebot.TeleBot.process_new_updates') as dispatch:
            bot.process_new_updates([old,delayed,click,member]);dispatch.assert_called_once_with([click,member])

    def test_current_command_and_recent_edit_kept(self):
        bot=object.__new__(FreshUpdatesBot);bot.started_at=1000
        command=NS(message=NS(date=1010));edit=NS(edited_message=NS(date=5,edit_date=1011))
        with patch('core.startup_safety.time.time',return_value=1020),patch('telebot.TeleBot.process_new_updates') as dispatch:
            bot.process_new_updates([command,edit]);dispatch.assert_called_once_with([command,edit])

    def test_empty_stale_batch_not_dispatched(self):
        bot=object.__new__(FreshUpdatesBot);bot.started_at=1000
        with patch('core.startup_safety.time.time',return_value=1005),patch('telebot.TeleBot.process_new_updates') as dispatch:
            bot.process_new_updates([NS(message=NS(date=900))]);dispatch.assert_not_called()

    def test_startup_jitter_and_shared_rate_limit(self):
        clock=Mock(return_value=0);gate=AutoPostGate(clock)
        self.assertFalse(gate.allow('daily',-1));clock.return_value=331
        self.assertTrue(all(gate.allow('daily',-i) for i in range(5)))
        self.assertFalse(gate.allow('news',-100));clock.return_value=391
        self.assertTrue(gate.allow('news',-100))

    def test_short_outage_recovers_long_outage_expires(self):
        self.assertFalse(abandoned({'deadline':100,'updated':90},200))
        self.assertTrue(abandoned({'deadline':100,'updated':90},4000))
        self.assertFalse(abandoned({'deadline':5000,'updated':90},4000))

    def test_auto_speedtap_accepts_required_update_wrapper(self):
        import ast
        from pathlib import Path
        tree=ast.parse(Path('bot.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and any(isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='speed_tap_command' for x in ast.walk(n)))
        calls=[]
        def wrapped(update,*args,**kwargs):calls.append((update,kwargs));return True
        ns={'speed_tap_command':wrapped,'can_auto_spawn_speed_tap':lambda *a:True}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'bot.py','exec'),ns)
        ns[node.name](-1)
        self.assertEqual(calls,[(None,{'auto_chat_id':-1})])

    def test_imposter_outage_does_not_finish_or_pay(self):
        from features import imposter
        s={'phase':'final','deadline':100,'message_id':5}
        bot=Mock()
        with patch.object(imposter.time,'time',return_value=4000),patch.object(imposter,'_save'),patch.object(imposter,'end_session'),patch.object(imposter,'_finish') as finish:
            imposter._tick(bot,-1,s)
        self.assertEqual(s['phase'],'cancelled');finish.assert_not_called()
        bot.send_message.assert_not_called()

    def test_draw_and_nan_outage_supersede_pending_panels(self):
        from features import draw_guess as draw,nan_yate as nan
        for module,lock_name in ((draw,'tx'),(nan,'transaction')):
            with self.subTest(module=module.__name__):
                s={'id':'game','chat_id':-1,'phase':'playing','deadline':100,'updated':90,'events':[], 'epoch':1,'awardees':[]}
                cur=Mock();con=MagicMock();con.__enter__.return_value=con;con.cursor.return_value.__enter__.return_value=cur
                cur.fetchall.return_value=[(-1,)]
                @contextlib.contextmanager
                def locked(**kwargs):yield cur,s,-1
                def cancel(state):state['phase']='cancelled';state['events']=[{'kind':'cancelled'}]
                alias='g' if module is draw else 'game'
                with patch.object(module,'get_db_connection',return_value=con),patch.object(module,lock_name,locked),patch.object(module.time,'time',return_value=4000),patch.object(module,'start_session'),patch.object(module,'end_session'),patch.object(module,'persist') as persist,patch.object(module,'drain'),patch.object(getattr(module,alias),'cancel',side_effect=cancel):
                    module.tick(Mock())
                self.assertEqual(s['phase'],'cancelled');persist.assert_called_once()
                self.assertTrue(any('SET done=TRUE' in call.args[0] for call in cur.execute.call_args_list))
