import os
import time
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,Mock,patch
from flask import Flask
from features import owner_operations as ops,owner_dashboard as owner
from core import sessions


class OwnerOperationsTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,OWNER_TELEGRAM_ID='42');self.env.start()
        self.old=(ops._ready,ops._loaded,ops._cache)
        ops._ready=True;ops._loaded=time.monotonic();ops._cache={'groups':{-100},'releases':{}}
    def tearDown(self):
        ops._ready,ops._loaded,ops._cache=self.old;self.env.stop()
        sessions.end_session(-871,'speed_tap')
    def connection(self,rows=()):
        conn=MagicMock();conn.__enter__.return_value=conn
        cur=conn.cursor.return_value.__enter__.return_value;cur.fetchone.side_effect=list(rows);cur.fetchall.return_value=[]
        return conn,cur
    def test_myanmar_time_and_web_datetime_local_are_identical(self):
        now=datetime(2026,10,11,tzinfo=timezone.utc)
        expected=datetime(2026,10,12,2,30,tzinfo=timezone.utc)
        self.assertEqual(ops.parse_when('2026-10-12 09:00',now),expected)
        self.assertEqual(ops.parse_when('2026-10-12T09:00',now),expected)
    def test_invalid_and_past_schedule_rejected(self):
        now=datetime(2026,10,11,tzinfo=timezone.utc)
        for text in ['now','2026-10-10 09:00','2028-10-12 09:00']:
            with self.assertRaises(ValueError):ops.parse_when(text,now)
    def test_assistant_has_only_granted_permission(self):
        conn,cur=self.connection([(['edit'],),(['edit'],)])
        with patch.object(ops,'get_db_connection',return_value=conn):
            self.assertTrue(ops.can(43,'edit'));self.assertFalse(ops.can(43,'announce'))
        self.assertFalse(ops.can(43,'leave'));self.assertTrue(ops.can(42,'announce'))
    def test_assistant_cannot_grant_roles(self):
        with patch.object(ops,'get_db_connection') as db:
            with self.assertRaises(ValueError):ops.set_assistant(43,44,['edit'])
        db.assert_not_called()
    def test_unknown_permission_rejected(self):
        with patch.object(ops,'get_db_connection') as db:
            with self.assertRaises(ValueError):ops.set_assistant(42,44,['leave'])
        db.assert_not_called()
    def test_revoke_removes_permissions(self):
        conn,cur=self.connection()
        with patch.object(ops,'get_db_connection',return_value=conn):ops.set_assistant(42,43,[])
        self.assertIn('DELETE FROM owner_assistants',cur.execute.call_args.args[0])
    def test_staged_feature_only_available_in_test_group(self):
        ops._cache['releases']['game:speed_tap']='test'
        self.assertTrue(ops.feature_allowed('game:speed_tap',-100))
        self.assertFalse(ops.feature_allowed('game:speed_tap',-101))
        self.assertTrue(ops.feature_allowed('game:boss_raid',-101))
    def test_real_speedtap_engine_and_session_are_both_gated(self):
        from games.speed_tap import create_speed_tap_game,end_speed_tap_game
        ops._cache['releases']['game:speed_tap']='test'
        self.assertEqual(create_speed_tap_game(-871,10),(False,None))
        self.assertEqual(sessions.can_start_session(-871,'speed_tap'),(False,'test_group_only'))
        with patch.object(ops,'usage') as usage:
            result=create_speed_tap_game(-100,10)
            self.assertTrue(result[0]);usage.assert_called_once_with(-100,'game','speed_tap')
        end_speed_tap_game(-100)
    def test_ongoing_game_recovery_does_not_count_as_new_game(self):
        ops._cache['releases']['game:speed_tap']='test'
        with patch.object(ops,'usage') as usage:
            self.assertTrue(sessions.start_session(-871,'speed_tap',recover=True)[0])
        usage.assert_not_called()
    def test_staging_requires_a_test_group(self):
        conn,cur=self.connection([None])
        with patch.object(ops,'get_db_connection',return_value=conn):
            with self.assertRaises(ValueError):ops.change_release(42,'game:speed_tap','test')
        self.assertFalse(any('INSERT INTO owner_feature_releases' in c.args[0] for c in cur.execute.call_args_list))
    def test_scheduler_busy_lock_does_not_enqueue(self):
        conn,cur=self.connection([(False,)])
        with patch.object(ops,'get_db_connection',return_value=conn),patch.object(owner,'_queue_broadcast') as queue:
            ops.due_schedules()
        queue.assert_not_called()
    def test_scheduler_recovers_crash_after_broadcast_creation(self):
        conn,cur=self.connection([(True,),(8,)])
        cur.fetchall.return_value=[(7,42,'all','hello',None,None,'token')]
        with patch.object(ops,'get_db_connection',return_value=conn),patch.object(owner,'_queue_broadcast') as queue,patch('threading.Thread'):
            ops.due_schedules()
        queue.assert_not_called()
        self.assertTrue(any("status='queued'" in c.args[0] and c.args[1]==(8,7) for c in cur.execute.call_args_list))
    def test_revoked_assistant_schedule_is_cancelled(self):
        conn,cur=self.connection([(True,),None])
        cur.fetchall.return_value=[(7,43,'all','hello',None,None,'token')]
        with patch.object(ops,'get_db_connection',return_value=conn),patch.object(ops,'can',return_value=False),patch.object(owner,'_queue_broadcast') as queue:
            ops.due_schedules()
        queue.assert_not_called();self.assertTrue(any('Creator permission revoked' in c.args[0] for c in cur.execute.call_args_list))
    def test_cancel_serializes_with_due_worker(self):
        conn,cur=self.connection([(8,)])
        with patch.object(ops,'get_db_connection',return_value=conn):ops.cancel_schedule(42,8)
        self.assertIn('759012350',cur.execute.call_args_list[0].args[0])
        self.assertIn("status='pending'",cur.execute.call_args_list[1].args[0])
    def test_schedule_preserves_telegram_media_source(self):
        conn,cur=self.connection([(8,)])
        when=datetime.now(timezone.utc)+timedelta(hours=1)
        with patch.object(ops,'get_db_connection',return_value=conn),patch.object(ops,'destinations',return_value=[-100]):
            sid=ops.create_schedule(42,'all',when,source_chat=42,source_msg=70,request_id='token')
        self.assertEqual(sid,8);self.assertEqual(cur.execute.call_args.args[1],(42,'all','',42,70,when,'token'))
    def test_leave_is_owner_only_and_failed_telegram_does_not_mark_inactive(self):
        bot=Mock();bot.leave_chat.return_value=False
        with patch.object(ops,'destinations',return_value=[-100]),patch.object(ops,'get_db_connection') as db:
            with self.assertRaises(ValueError):ops.leave_group(43,-100,bot)
            bot.leave_chat.assert_not_called()
            with self.assertRaises(ValueError):ops.leave_group(42,-100,bot)
        db.assert_not_called()
    def handlers(self):
        handlers={};bot=MagicMock()
        def decorator(*a,**kw):
            def bind(fn):handlers[fn.__name__]=fn;return fn
            return bind
        bot.message_handler.side_effect=decorator;bot.callback_query_handler.side_effect=decorator
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(owner.dashboard)
        replace=Mock()
        with patch('threading.Thread'):ops.register(app,bot,replace,Mock())
        return app,bot,handlers,replace
    def test_web_tools_requires_owner_login_and_csrf(self):
        app,_,_,_=self.handlers()
        with patch.object(owner,'_ready',return_value=True),app.test_client() as client:
            self.assertIn('/owner/login',client.get('/owner/tools/').location)
            with client.session_transaction() as s:s['owner']=True;s['csrf']='right'
            with patch.object(ops,'set_assistant') as grant:
                r=client.post('/owner/tools/',data={'action':'assistant','uid':'43','permission':'edit','csrf':'wrong'})
        self.assertEqual(r.status_code,403);grant.assert_not_called()
    def test_assistant_can_confirm_announcement_but_cannot_leave_group(self):
        _,bot,handlers,replace=self.handlers();store={43:{'phase':'now_confirm','target':'all','source_chat':43,'source_msg':7,'token':'t'}}
        def draft(uid,value=None):
            if value is not None:store[uid]=value
            return store.get(uid)
        q=NS(id='q',data='ops:confirmnow',from_user=NS(id=43),message=NS(message_id=8,chat=NS(id=43,type='private')))
        with patch.object(owner,'_load_panel_state',return_value=(43,8,None)),patch.object(ops,'can',side_effect=lambda uid,p:p=='announce'),patch.object(ops,'draft',side_effect=draft),patch.object(ops,'destinations',return_value=[-100]),patch.object(owner,'_queue_broadcast',return_value=10) as queue,patch('threading.Thread'),patch.object(ops,'leave_group') as leave:
            handlers['owner_tools_action'](q);queue.assert_called_once_with('[Telegram original]',[-100],43,7,'t')
            q.data='ops:leaveyes:-100';handlers['owner_tools_action'](q);leave.assert_not_called()
    def test_stale_tools_callback_cannot_leave(self):
        _,bot,handlers,_=self.handlers()
        q=NS(id='q',data='ops:leaveyes:-100',from_user=NS(id=42),message=NS(message_id=7,chat=NS(id=42,type='private')))
        with patch.object(owner,'_load_panel_state',return_value=(42,8,None)),patch.object(ops,'leave_group') as leave:
            handlers['owner_tools_action'](q)
        leave.assert_not_called();bot.answer_callback_query.assert_called_once()
