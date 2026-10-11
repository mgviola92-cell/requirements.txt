import ast
import contextlib
import io
import json
import os
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,Mock,patch
from flask import Flask
from core import customization as c
from features import owner_controls as controls
from features import owner_dashboard as owner


class CustomizationTests(unittest.TestCase):
    def setUp(self):
        self.previous=c._values.copy();self.ready=c._ready
        c._values={};c._ready=False
        self.message_key=next(k for k,e in c.CATALOG.items() if e['kind']=='message' and e['fields'])
        self.setting_key='cfg.games.boss_raid.RAID_DURATION'
    def tearDown(self):c._values=self.previous;c._ready=self.ready

    def test_all_catalog_defaults_validate(self):
        for key,entry in c.CATALOG.items():
            with self.subTest(key=key):c.validate(key,entry['default'])

    def test_global_and_group_override_and_isolation(self):
        c._values[(0,self.setting_key)]=300;c._values[(-100,self.setting_key)]=120
        self.assertEqual(c.setting_value(self.setting_key,180,scope=-100),120)
        self.assertEqual(c.setting_value(self.setting_key,180,scope=-200),300)
        self.assertEqual(c.setting_value(self.setting_key,180,scope=0),300)

    def test_nested_scope_restores_previous_group(self):
        with c.group_scope(-100):
            self.assertEqual(c.current_group(),-100)
            with c.group_scope(-200):self.assertEqual(c.current_group(),-200)
            self.assertEqual(c.current_group(),-100)
        self.assertEqual(c.current_group(),0)

    def test_timer_function_resolves_group_from_chat_id(self):
        def callback(chat_id):return c.setting_value(self.setting_key,180)
        c._values[(-100,self.setting_key)]=222
        self.assertEqual(callback(-100),222)

    def test_placeholder_is_substituted_without_eval(self):
        fields=c.CATALOG[self.message_key]['fields'];template='Hello {'+fields[0]+'}'
        c._values[(-100,self.message_key)]=template
        self.assertEqual(c.message_text(self.message_key,'original',{fields[0]:'Player'},scope=-100),'Hello Player')
        with self.assertRaises(ValueError):c.validate(self.message_key,'{__import__(os)}')
        with self.assertRaises(ValueError):c.validate(self.message_key,'{target.__class__}')
        with self.assertRaises(ValueError):c.validate(self.message_key,'{not_registered}')

    def test_non_finite_and_invalid_types_rejected(self):
        for value in (float('nan'),float('inf'),True,'180',-3):
            with self.subTest(value=value),self.assertRaises(ValueError):c.validate(self.setting_key,value)

    def test_bounded_probabilities(self):
        c.validate('cfg.boss_auto.chance',.5)
        for value in (1.5,-.1):
            with self.assertRaises(ValueError):c.validate('cfg.boss_auto.chance',value)

    def test_ranges_and_round_lengths_validated(self):
        with self.assertRaises(ValueError):c.validate('cfg.boss_auto.threshold',[125,60])
        with self.assertRaises(ValueError):c.validate('cfg.games.math_battle.TIMES',[10,20])

    def test_html_rejects_script_and_bad_link(self):
        key=next(k for k,e in c.CATALOG.items() if e.get('html'))
        c.validate(key,'<b>Allowed</b>')
        for value in ('<script>bad</script>','<b>unclosed','<a href="javascript:alert(1)">bad</a>'):
            with self.assertRaises(ValueError):c.validate(key,value)

    def test_burmese_bank_customization_is_live(self):
        key=next(k for k,e in c.CATALOG.items() if e.get('bank') and e['category']=='games.boss_raid')
        entry=c.CATALOG[key];c._values[(-100,key)]='ပြင်ထားတဲ့စာ'
        with c.group_scope(-100):self.assertEqual(c.bank_text('games.boss_raid',[entry['default']]),['ပြင်ထားတဲ့စာ'])
        with c.group_scope(-200):self.assertEqual(c.bank_text('games.boss_raid',[entry['default']]),[entry['default']])

    def test_numeric_tuple_preserves_original_runtime_type(self):
        c._values[(-100,'cfg.games.math_battle.TIMES')]=[50,65,80,95,110]
        self.assertEqual(c.setting_value('cfg.games.math_battle.TIMES',(45,60,75,90,105),scope=-100),(50,65,80,95,110))

    def test_real_reward_engine_uses_group_override(self):
        from core.rewards import get_reward
        key='cfg.core.rewards.GAME_REWARDS';value=json.loads(json.dumps(c.CATALOG[key]['default']))
        value['coin']['win']=15;c._values[(-100,key)]=value
        with c.group_scope(-100):self.assertEqual(get_reward('coin','win'),15)
        with c.group_scope(-200):self.assertEqual(get_reward('coin','win'),5)

    def test_real_ban_reply_uses_custom_message(self):
        tree=ast.parse(Path('bot.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and any(isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='message_handler' and any(kw.arg=='commands' and isinstance(kw.value,ast.List) and any(isinstance(x,ast.Constant) and x.value=='ဘမ်း' for x in kw.value.elts) for kw in d.keywords) for d in n.decorator_list))
        fn.decorator_list=[]
        calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_custom_text']
        key=next(ast.literal_eval(n.args[0]) for n in calls if 'Reply' in ast.literal_eval(n.args[1]))
        c._values[(-100,key)]='မင်းစိတ်ကြိုက် ပြင်ထားတဲ့စာ'
        bot=Mock();msg=NS(chat=NS(id=-100,type='supergroup'),from_user=NS(id=42),reply_to_message=None,message_id=3)
        env=dict(bot=bot,is_admin=lambda m:True,is_bot_admin=lambda m:True,_custom_text=c.message_text,_custom_setting=c.setting_value,_custom_bank=c.bank_text,delay_delete_message=Mock(),GAME_DELETE_TIME=120,INFO_DELETE_TIME=180)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'bot.py','exec'),env)
        with c.group_scope(-100):env[fn.name](msg)
        self.assertTrue(any('မင်းစိတ်ကြိုက် ပြင်ထားတဲ့စာ' in str(call) for call in bot.mock_calls))

    def test_real_auto_gate_respects_group_disable(self):
        from features.activity_spawn import ActivitySpawner
        c._values[(-100,'cfg.boss_auto.enabled')]=False
        spawn=Mock(return_value=True)
        gate=ActivitySpawner(spawn,threshold=(2,2),chance=1,quiet=(1,1),config_key='boss_auto')
        gate.record(-100,1);gate.record(-100,2)
        spawn.assert_not_called()

    def test_handler_disable_keeps_other_groups_enabled(self):
        bot=MagicMock();registered={}
        def decorator(**kw):
            def bind(fn):registered['fn']=fn;return fn
            return bind
        bot.message_handler.side_effect=decorator
        c.install_handler_controls(bot)
        def target(msg):return 'ran'
        target.__module__='bot';target.__name__='profile_command'
        wrapped=bot.message_handler(commands=['profile'])(target)
        key='enabled.bot.profile_command';c._values[(-100,key)]=False
        self.assertIsNone(wrapped(NS(chat=NS(id=-100),from_user=NS(id=1))))
        self.assertEqual(wrapped(NS(chat=NS(id=-200),from_user=NS(id=1))),'ran')

    def test_save_and_reset_update_effective_values_and_audit(self):
        conn=MagicMock();conn.__enter__.return_value=conn
        cur=conn.cursor.return_value.__enter__.return_value;cur.fetchone.return_value=None
        with patch('database.db.get_db_connection',return_value=conn):
            c.save(-100,self.setting_key,240,42)
            self.assertEqual(c.effective(self.setting_key,-100),240)
            c.save(-100,self.setting_key,None,42,reset=True)
        self.assertEqual(c.effective(self.setting_key,-100),180)
        self.assertTrue(any('owner_customization_log' in call.args[0] for call in cur.execute.call_args_list))

    def test_restart_refresh_restores_saved_override(self):
        conn=MagicMock();conn.__enter__.return_value=conn
        conn.cursor.return_value.__enter__.return_value.fetchall.return_value=[(-100,self.setting_key,240)]
        c._ready=True
        with patch('database.db.get_db_connection',return_value=conn):c.refresh(force=True)
        c._ready=False
        self.assertEqual(c.effective(self.setting_key,-100),240)

    def web_app(self):
        app=Flask(__name__);app.secret_key='test'
        app.register_blueprint(owner.dashboard)
        controls.register(app,MagicMock(),Mock(),Mock(),Mock())
        return app

    def test_web_editor_requires_login(self):
        app=self.web_app()
        with patch.object(owner,'_ready',return_value=True),app.test_client() as client:
            response=client.get('/owner/control/')
        self.assertEqual(response.status_code,302)
        self.assertIn('/owner/login',response.location)

    def test_web_editor_requires_csrf(self):
        app=self.web_app()
        with patch.object(owner,'_ready',return_value=True),app.test_client() as client,patch.object(controls,'save') as save:
            with client.session_transaction() as session:session['owner']=True;session['csrf']='right'
            response=client.post('/owner/control/edit',data={'key':self.setting_key,'scope':0,'csrf':'wrong','action':'save','value':'240'})
        self.assertEqual(response.status_code,403);save.assert_not_called()

    def test_web_editor_save_is_used_by_real_game(self):
        app=self.web_app();conn=MagicMock();conn.__enter__.return_value=conn
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value=(1,)
        with patch.dict(os.environ,OWNER_TELEGRAM_ID='42'),patch.object(owner,'_ready',return_value=True),patch('database.db.get_db_connection',return_value=conn),patch.object(controls,'get_db_connection',return_value=conn),app.test_client() as client:
            with client.session_transaction() as session:session['owner']=True;session['csrf']='right'
            response=client.post('/owner/control/edit',data={'key':self.setting_key,'scope':-100,'csrf':'right','action':'save','value':'240'})
        self.assertEqual(response.status_code,200)
        from games.boss_raid import start_raid,finish_raid
        # The bot's caller passes the effective duration into this existing game engine.
        with c.group_scope(-100):duration=c.setting_value(self.setting_key,180)
        ok,raid=start_raid(-999,duration=duration)
        self.assertTrue(ok);self.assertEqual(raid['ends_at']-raid['started_at'],240)
        finish_raid(-999,raid['id'],'cancelled')

    def test_new_private_editor_is_owner_only(self):
        bot=MagicMock();handlers={}
        def register(**kw):
            def bind(fn):handlers[fn.__name__]=fn;return fn
            return bind
        bot.message_handler.side_effect=register;bot.callback_query_handler.side_effect=register
        app=Flask(__name__)
        controls.register(app,bot,Mock(),Mock(),Mock())
        with patch.dict(os.environ,OWNER_TELEGRAM_ID='42'),patch.object(controls,'get_db_connection') as db:
            handlers['owner_control_command'](NS(chat=NS(type='group',id=-100),from_user=NS(id=42)))
            handlers['owner_control_command'](NS(chat=NS(type='private',id=43),from_user=NS(id=43)))
        db.assert_not_called()

    def test_bot_startup_with_isolated_database_and_telegram(self):
        fakebot=MagicMock()
        for method in ('message_handler','callback_query_handler','poll_answer_handler','my_chat_member_handler'):
            getattr(fakebot,method).side_effect=lambda *a,**kw:lambda fn:fn
        conn=MagicMock();conn.__enter__.return_value=conn
        cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value=[];cur.fetchone.return_value=(0,0,0)
        with patch.dict(__import__('sys').modules,{'yt_dlp':MagicMock()}),patch.dict(os.environ,{'BOT_TOKEN':'123456:TEST','DATABASE_URL':'postgresql://test'},clear=False),patch('telebot.TeleBot',return_value=fakebot),patch('database.db.get_db_connection',return_value=conn),patch('database.db.DATABASE_URL','postgresql://test'),patch('psycopg.connect',return_value=conn),patch('threading.Thread.start'),patch('threading.Timer.start'),patch('flask.Flask.run'),contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path('bot.py',run_name='__main__')

    def test_settings_are_not_frozen_in_function_defaults(self):
        for path in Path('.').rglob('*.py'):
            if '__pycache__' in str(path):continue
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node,ast.FunctionDef):continue
                for default in node.args.defaults+node.args.kw_defaults:
                    if default is None:continue
                    calls=[n for n in ast.walk(default) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_custom_setting']
                    self.assertFalse(calls,(str(path),node.name))

    def test_command_aliases_cannot_be_changed_by_message_editor(self):
        for path in [Path('bot.py'),*Path('features').glob('*.py')]:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,ast.FunctionDef):
                    for decorator in node.decorator_list:
                        calls=[n for n in ast.walk(decorator) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_custom_text']
                        self.assertFalse(calls,(str(path),node.name))
