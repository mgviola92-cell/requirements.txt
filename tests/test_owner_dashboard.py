"""Owner flows run with isolated fake Telegram and database connections."""
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch
from flask import Flask
from features import owner_dashboard as owner


class OwnerStabilityTests(unittest.TestCase):
    def connection(self, rows):
        conn=MagicMock()
        conn.__enter__.return_value=conn
        cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect=rows
        return conn,cur

    def test_busy_worker_does_not_recover_live_sends(self):
        conn,cur=self.connection([(False,)])
        with patch.object(owner,'get_db_connection',return_value=conn), patch.object(owner,'_process_broadcast') as process:
            owner._send_broadcast(1)
        process.assert_not_called()
        self.assertEqual(cur.execute.call_count,1)

    def test_recovery_is_job_scoped_and_uses_lock_connection(self):
        conn,cur=self.connection([(True,),('running',),(1,)])
        with patch.object(owner,'get_db_connection',return_value=conn), patch.object(owner,'_process_broadcast') as process:
            owner._send_broadcast(7)
        process.assert_called_once_with(7,conn)
        sql,args=cur.execute.call_args.args
        self.assertIn("WHERE job_id=%s AND status='sending'",sql)
        self.assertEqual(args,(7,))

    def test_legacy_job_requires_review(self):
        conn,cur=self.connection([(True,),('running',),None])
        with patch.object(owner,'get_db_connection',return_value=conn), patch.object(owner,'_process_broadcast') as process:
            owner._send_broadcast(8)
        process.assert_not_called()
        self.assertIn("needs_review",cur.execute.call_args.args[0])

    def test_finished_job_cannot_be_replayed(self):
        conn,cur=self.connection([(True,),('completed',)])
        with patch.object(owner,'get_db_connection',return_value=conn), patch.object(owner,'_process_broadcast') as process:
            owner._send_broadcast(8)
        process.assert_not_called()

    def delivery(self, error=None, original=False, opted_out=False):
        conn,cur=self.connection([('hello',9 if original else None,10 if original else None),(-100,)]+([None] if opted_out else [(1,)]*(3 if error and getattr(error,'error_code',None)==429 else 1))+[None])
        bot=MagicMock()
        method=bot.copy_message if original else bot.send_message
        if error:method.side_effect=error
        with patch.object(owner,'get_db_connection',return_value=conn),patch.object(owner,'BOT',bot),patch.object(owner.time,'sleep') as sleep:
            owner._process_broadcast(5,conn)
        states=[c.args[1][0] for c in cur.execute.call_args_list if 'SET status=%s,last_error=%s' in c.args[0]]
        return bot,states,sleep,cur

    def test_opt_out_after_queue_prevents_delivery(self):
        bot,states,_,_=self.delivery(opted_out=True)
        bot.send_message.assert_not_called()
        self.assertEqual(states,['skipped'])

    def test_original_uses_copy_message(self):
        bot,states,_,_=self.delivery(original=True)
        bot.copy_message.assert_called_once_with(-100,9,10)
        bot.send_message.assert_not_called()
        self.assertEqual(states,['sent'])

    def test_web_text_is_plain(self):
        bot,states,_,_=self.delivery()
        bot.send_message.assert_called_once_with(-100,'hello',parse_mode=None)
        self.assertEqual(states,['sent'])

    def test_timeout_is_uncertain_and_never_retried(self):
        bot,states,_,_=self.delivery(TimeoutError('timed out'))
        self.assertEqual(bot.send_message.call_count,1)
        self.assertEqual(states,['uncertain'])

    def test_connection_failure_is_uncertain(self):
        bot,states,_,_=self.delivery(ConnectionError('connection closed'))
        self.assertEqual(bot.send_message.call_count,1)
        self.assertEqual(states,['uncertain'])

    def test_rate_limit_respects_full_retry_after(self):
        error=Exception('Too Many Requests: retry after 90')
        error.error_code=429
        error.result_json={'parameters':{'retry_after':90}}
        bot,states,sleep,_=self.delivery(error)
        self.assertEqual(bot.send_message.call_count,3)
        self.assertEqual(states,['failed'])
        self.assertEqual([c.args[0] for c in sleep.call_args_list if c.args[0]>=1],[90,90])

    def test_permission_error_is_not_retried(self):
        error=Exception('Forbidden: bot was kicked')
        error.error_code=403
        bot,states,_,cur=self.delivery(error)
        self.assertEqual(bot.send_message.call_count,1)
        self.assertEqual(states,['failed'])
        self.assertTrue(any('active=FALSE' in c.args[0] for c in cur.execute.call_args_list))

    def handlers(self):
        handlers={}
        bot=MagicMock()
        def message_handler(**kwargs):
            def register(fn):handlers[fn.__name__]=fn;return fn
            return register
        bot.message_handler.side_effect=message_handler
        bot.callback_query_handler.side_effect=message_handler
        bot.my_chat_member_handler.side_effect=message_handler
        with patch.object(owner,'_init_db'),patch.object(owner.threading,'Thread'):
            owner.register_owner_dashboard(Flask(__name__),bot)
        return bot,handlers

    def test_stale_callback_cannot_queue(self):
        bot,handlers=self.handlers()
        q=NS(id='q',data='own:send',from_user=NS(id=42),message=NS(message_id=3,chat=NS(type='private',id=42)))
        with patch.dict(os.environ,OWNER_TELEGRAM_ID='42'),patch.object(owner,'_load_panel_state',return_value=(42,4,None)),patch.object(owner,'_queue_broadcast') as queue:
            handlers['owner_actions'](q)
        queue.assert_not_called()
        bot.answer_callback_query.assert_called_once()

    def test_database_outage_fails_closed(self):
        bot,handlers=self.handlers()
        q=NS(id='q',data='own:send',from_user=NS(id=42),message=NS(message_id=3,chat=NS(type='private',id=42)))
        with patch.dict(os.environ,OWNER_TELEGRAM_ID='42'),patch.object(owner,'_load_panel_state',side_effect=RuntimeError()),patch.object(owner,'_queue_broadcast') as queue:
            handlers['owner_actions'](q)
        queue.assert_not_called()

    def test_forward_alone_does_not_save_or_open_cards(self):
        bot,handlers=self.handlers()
        handlers['capture_owner_message'](NS())
        bot.send_message.assert_not_called()
        bot.reply_to.assert_not_called()

    def test_welcome_preview_escapes_saved_text(self):
        app=Flask(__name__);app.secret_key='test'
        app.register_blueprint(owner.dashboard)
        conn,_=self.connection([('<script>alert(1)</script>\nWelcome',)])
        with app.test_client() as client,patch.object(owner,'_ready',return_value=True),patch.object(owner,'get_db_connection',return_value=conn):
            with client.session_transaction() as session:session['owner']=True
            response=client.get('/owner/welcome')
        self.assertEqual(response.status_code,200)
        self.assertNotIn(b'<script>alert(1)</script>',response.data)
        self.assertIn(b'&lt;script&gt;',response.data)

    def test_web_post_requires_csrf(self):
        app=Flask(__name__);app.secret_key='test'
        app.register_blueprint(owner.dashboard)
        with app.test_client() as client,patch.object(owner,'_ready',return_value=True),patch.object(owner,'_queue_broadcast') as queue:
            with client.session_transaction() as session:session['owner']=True;session['csrf']='correct'
            response=client.post('/owner/broadcast',data={'csrf':'wrong'})
        self.assertEqual(response.status_code,403)
        queue.assert_not_called()

    def test_testwelcome_is_owner_private_only(self):
        bot,handlers=self.handlers()
        msg=NS(chat=NS(type='group',id=-100),from_user=NS(id=42))
        with patch.dict(os.environ,OWNER_TELEGRAM_ID='42'):
            handlers['owner_test_welcome'](msg)
        bot.send_message.assert_not_called()

    def test_duplicate_request_cannot_create_targets(self):
        conn,cur=self.connection([(123,)])
        with patch.object(owner,'get_db_connection',return_value=conn):
            with self.assertRaisesRegex(ValueError,'already been submitted'):
                owner._queue_broadcast('hello',[-100],request_id='same')
        cur.executemany.assert_not_called()

    def test_draft_restores_after_restart(self):
        import time
        owner._owner_drafts.clear();owner._owner_card_ids.clear()
        bot,handlers=self.handlers()
        draft={'phase':'ready','expires':time.time()+600,'chat_id':42,'message_id':10,'request_id':'r'}
        q=NS(id='q',data='own:to:all',from_user=NS(id=42),message=NS(message_id=3,chat=NS(type='private',id=42)))
        bot.send_message.return_value=NS(message_id=4)
        with patch.dict(os.environ,OWNER_TELEGRAM_ID='42'),patch.object(owner,'_load_panel_state',return_value=(42,3,draft)),patch.object(owner,'_save_panel_state') as save:
            handlers['owner_actions'](q)
        self.assertEqual(owner._owner_drafts[42]['target'],'all')
        self.assertEqual(save.call_args.args[3]['request_id'],'r')
        bot.delete_message.assert_called_once_with(42,3)


if __name__=='__main__':unittest.main()
