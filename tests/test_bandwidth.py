"""Regressions for repeated state uploads, pool reuse, and unreachable daily chats."""
import ast,copy,random,unittest,threading,time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock,patch
from database import db
from features import draw_guess as draw,nan_yate as nan
from games import draw_guess as game

class BandwidthTests(unittest.TestCase):
    def connection(self):
        con=MagicMock();con.__enter__.return_value=con
        return con,con.cursor.return_value.__enter__.return_value
    def test_pool_reused_and_transaction_context_returned(self):
        pool=MagicMock();pool.connection.return_value=MagicMock()
        with patch.object(db,'DATABASE_URL','postgresql://test'),patch.object(db,'_pool',None),patch.object(db,'ConnectionPool',return_value=pool) as factory,patch.object(db.atexit,'register'):
            with db.get_db_connection() as first:pass
            with db.get_db_connection() as second:pass
            factory.assert_called_once();pool.open.assert_called_once()
            self.assertIs(first,second);self.assertEqual(pool.connection.call_count,2)
            self.assertEqual(factory.call_args.kwargs['max_size'],12)
    def test_noop_draw_tick_does_not_resend_image_or_words(self):
        s=game.create('g',-42,1,{},100);s.update(phase='guess',deadline=300,updated=185,image='X'*300000,words=[('ကြောင်',[])])
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
        s=g.create('n',-42,1,{},100);s.update(phase='night',deadline=300,updated=185)
        con,cur=self.connection();cur.fetchall.return_value=[(-42,)]
        @contextmanager
        def tx(**kw):yield cur,s,-42
        with patch.object(nan,'get_db_connection',return_value=con),patch.object(nan,'transaction',tx),patch.object(nan,'start_session'),patch.object(nan,'persist') as persist,patch.object(nan,'drain'),patch.object(nan,'invalidate_rewards'),patch.object(nan.time,'time',return_value=200):nan.tick(MagicMock())
        persist.assert_not_called();self.assertIn("jsonb_set(state,'{updated}'",cur.execute.call_args.args[0])
if __name__=='__main__':unittest.main()
