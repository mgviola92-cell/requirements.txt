"""Regressions for repeated state uploads, pool reuse, and unreachable daily chats."""
import ast,copy,random,unittest,threading,time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock,patch
from database import db,daily_challenge as daily
from features import draw_guess as draw,nan_yate as nan
from games import draw_guess as game

class BandwidthTests(unittest.TestCase):
    def connection(self):
        con=MagicMock();con.__enter__.return_value=con
        return con,con.cursor.return_value.__enter__.return_value
    def test_pool_reused_and_transaction_context_returned(self):
        pool=MagicMock();pool.connection.return_value=MagicMock()
        with patch.object(db,'DATABASE_URL','postgresql://test'),patch.object(db,'_pool',None),patch.object(db,'ConnectionPool',return_value=pool) as factory,patch.object(db.atexit,'register'):
            first=db.get_db_connection();second=db.get_db_connection()
            factory.assert_called_once();pool.open.assert_called_once()
            self.assertIs(first,second);self.assertEqual(pool.connection.call_count,2)
            self.assertEqual(factory.call_args.kwargs['max_size'],12)
    def test_failed_daily_chats_disabled_without_erasing_progress(self):
        con,cur=self.connection()
        for code,reason,enabled in [(403,'Forbidden: the group chat was deleted',False),(400,'Bad Request: chat not found',False),(403,'Forbidden: bot was kicked from the supergroup chat',False),(429,'Too Many Requests',True),(500,'temporary failure',True)]:
            error=RuntimeError(reason);error.error_code=code
            with patch.object(daily,'get_db_connection',return_value=con):daily.delivery_failed(-42,error)
            sql,args=cur.execute.call_args.args
            self.assertTrue(sql.startswith('UPDATE daily_groups'))
            self.assertIn("INTERVAL '30 minutes'",sql);self.assertEqual(args,(enabled,-42))
    def test_active_daily_groups_exclude_disabled_and_backoff(self):
        con,cur=self.connection();cur.fetchall.return_value=[(-1,)]
        with patch.object(daily,'get_db_connection',return_value=con):self.assertEqual(daily.active_groups(),[-1])
        sql=cur.execute.call_args.args[0];self.assertIn('WHERE enabled',sql);self.assertIn('retry_after<=NOW()',sql)
    def test_noop_draw_tick_does_not_resend_image_or_words(self):
        s=game.create('g',-42,1,{},100);s.update(phase='guess',deadline=300,updated=195,image='X'*300000,words=[('ကြောင်',[])])
        con,cur=self.connection();cur.fetchall.return_value=[(-42,)]
        @contextmanager
        def tx(**kw):yield cur,s,-42
        with patch.object(draw,'get_db_connection',return_value=con),patch.object(draw,'tx',tx),patch.object(draw,'start_session'),patch.object(draw,'persist') as persist,patch.object(draw,'drain'),patch.object(draw.time,'time',return_value=200):draw.tick(MagicMock())
        persist.assert_not_called()
        sql,args=cur.execute.call_args.args;self.assertIn("jsonb_set(state,'{updated}'",sql)
        self.assertLess(len(str(args)),100)
        self.assertEqual(s['image'],'X'*300000)
    def test_draw_deadline_still_persists_real_transition(self):
        s=game.create('g',-42,1,{},100);s.update(deadline=200,updated=195)
        con,cur=self.connection();cur.fetchall.return_value=[(-42,)]
        @contextmanager
        def tx(**kw):yield cur,s,-42
        with patch.object(draw,'get_db_connection',return_value=con),patch.object(draw,'tx',tx),patch.object(draw,'start_session'),patch.object(draw,'persist') as persist,patch.object(draw,'drain'),patch.object(draw.time,'time',return_value=201):draw.tick(MagicMock())
        persist.assert_called_once();self.assertEqual(s['phase'],'cancelled')
    def test_noop_nan_tick_only_updates_heartbeat(self):
        from games import nan_yate as g
        s=g.create('n',-42,1,{},100);s.update(phase='night',deadline=300,updated=195)
        con,cur=self.connection();cur.fetchall.return_value=[(-42,)]
        @contextmanager
        def tx(**kw):yield cur,s,-42
        with patch.object(nan,'get_db_connection',return_value=con),patch.object(nan,'transaction',tx),patch.object(nan,'start_session'),patch.object(nan,'persist') as persist,patch.object(nan,'drain'),patch.object(nan,'invalidate_rewards'),patch.object(nan.time,'time',return_value=200):nan.tick(MagicMock())
        persist.assert_not_called();self.assertIn("jsonb_set(state,'{updated}'",cur.execute.call_args.args[0])
    def publish_handler(self,bot,cur):
        source=ast.parse(Path('features/daily_challenge.py').read_text());fn=next(n for n in ast.walk(source) if isinstance(n,ast.FunctionDef) and n.name=='publish')
        env=dict(_ready=True,today=lambda:'day',time=time,_lock=threading.RLock(),_last_refresh={},delivery_ready=lambda cid:True,get_card_id=lambda *a:9,overview=lambda *a,**k:{},card=lambda s:MagicMock(),bot=bot,delivery_failed=MagicMock(),_custom_text=lambda k,d,f:d)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'daily','exec'),env);return env
    def test_edit_permission_failure_does_not_upload_replacement(self):
        bot=MagicMock();bot.edit_message_media.side_effect=RuntimeError('Forbidden: bot was kicked')
        env=self.publish_handler(bot,None)
        self.assertFalse(env['publish'](-42));bot.send_photo.assert_not_called();env['delivery_failed'].assert_called_once()
    def test_backoff_skips_any_image_upload(self):
        bot=MagicMock();env=self.publish_handler(bot,None);env['delivery_ready']=lambda cid:False
        self.assertFalse(env['publish'](-42));bot.send_photo.assert_not_called();bot.edit_message_media.assert_not_called()

if __name__=='__main__':unittest.main()
