import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from core import db_work
from database import db

class StopLoop(BaseException):pass

class CommitWakeTests(unittest.TestCase):
    def setUp(self):
        self.event=db_work.signal('test_work_queue')
        self.con=MagicMock();self.pool=MagicMock()
        self.pool.connection.return_value.__enter__.return_value=self.con
    def context(self):return patch.object(db,'_pool',self.pool)
    def test_notify_after_successful_commit_only(self):
        with self.context(),patch.object(db,'DATABASE_URL','postgresql://test'):
            with db.get_db_connection() as con:
                db_work.wrote(con,'INSERT INTO test_work_queue VALUES(1)')
                self.assertFalse(self.event.is_set())
            self.assertTrue(self.event.is_set())
        self.assertNotIn(id(self.con),db_work._PENDING)
    def test_pool_reborrow_does_not_lose_next_transactions_tracking(self):
        def reborrow(*args):
            self.assertFalse(self.event.is_set())
            db_work.begin(self.con)
            db_work.wrote(self.con,'INSERT INTO test_work_queue VALUES(2)')
            return False
        self.pool.connection.return_value.__exit__.side_effect=reborrow
        with self.context(),patch.object(db,'DATABASE_URL','postgresql://test'):
            with db.get_db_connection() as con:db_work.wrote(con,'INSERT INTO test_work_queue VALUES(1)')
        self.assertTrue(self.event.is_set())
        self.assertEqual(db_work.take(self.con),{'test_work_queue'})

    def test_rollback_does_not_wake(self):
        with self.context(),patch.object(db,'DATABASE_URL','postgresql://test'):
            with self.assertRaises(ValueError):
                with db.get_db_connection() as con:
                    db_work.wrote(con,'UPDATE test_work_queue SET id=2')
                    raise ValueError('rollback')
        self.assertFalse(self.event.is_set())
        self.assertNotIn(id(self.con),db_work._PENDING)
    def test_commit_failure_does_not_wake(self):
        self.pool.connection.return_value.__exit__.side_effect=RuntimeError('commit failed')
        with self.context(),patch.object(db,'DATABASE_URL','postgresql://test'):
            with self.assertRaises(RuntimeError):
                with db.get_db_connection() as con:db_work.wrote(con,'DELETE FROM test_work_queue')
        self.assertFalse(self.event.is_set())
    def test_reads_and_other_tables_do_not_wake(self):
        db_work.begin(self.con)
        for query in ['SELECT * FROM test_work_queue','INSERT INTO other_table VALUES(1)','CREATE TABLE test_work_queue(id INT)']:
            db_work.wrote(self.con,query)
        db_work.finish(self.con,True)
        self.assertFalse(self.event.is_set())
    def test_connections_do_not_mix_notifications(self):
        other=object();db_work.begin(self.con);db_work.begin(other)
        db_work.wrote(self.con,'UPDATE test_work_queue SET id=1')
        db_work.finish(other,True);self.assertFalse(self.event.is_set())
        db_work.finish(self.con,True);self.assertTrue(self.event.is_set())
    def test_read_only_transaction_does_not_wake(self):
        with self.context(),patch.object(db,'DATABASE_URL','postgresql://test'):
            with db.get_db_connection():pass
        self.assertFalse(self.event.is_set())

class DeadlineTests(unittest.TestCase):
    def test_shared_recovery_boundary(self):
        self.assertEqual(db_work.delay(now=301),599)
        self.assertEqual(db_work.delay(now=899),1)
    def test_earlier_deadline_and_overdue_bound(self):
        self.assertEqual(db_work.delay(400,now=301),99)
        self.assertEqual(db_work.delay(300,now=301),0.1)
    def test_later_deadline_still_recovers_external_work(self):
        self.assertEqual(db_work.delay(10000,now=301),599)
    def test_due_lookup(self):
        from datetime import datetime,timezone
        con=MagicMock();con.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value=(datetime.fromtimestamp(900,timezone.utc),)
        with patch.object(db,'get_db_connection',return_value=con):self.assertEqual(db_work.next_due('SELECT MIN(due_at) FROM jobs'),900)


def nested_function(file,name,index=0):
    tree=ast.parse(Path(file).read_text())
    nodes=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name==name]
    node=nodes[index]
    return compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),file,'exec')

class WorkerSleepTests(unittest.TestCase):
    def run_loop(self,file,name,namespace,index=0):
        exec(nested_function(file,name,index),namespace)
        with self.assertRaises(StopLoop):namespace[name]()
    def event(self):
        wake=MagicMock();wake.wait.side_effect=StopLoop
        return wake
    def test_empty_studio_waits_for_recovery(self):
        wake=self.event();work=MagicMock();work.next_due.return_value=None;work.delay.return_value=900
        run=MagicMock()
        self.run_loop('features/group_studio.py','loop',dict(WORK_WAKE=wake,db_work=work,run_jobs=run,bot=object(),LOG=MagicMock()))
        run.assert_called_once();wake.wait.assert_called_once_with(900)
    def test_future_studio_job_sleeps_until_due(self):
        wake=self.event();work=MagicMock();work.next_due.return_value=12345;work.delay.return_value=123
        self.run_loop('features/group_studio.py','loop',dict(WORK_WAKE=wake,db_work=work,run_jobs=MagicMock(),bot=object(),LOG=MagicMock()))
        work.delay.assert_called_once_with(12345);wake.wait.assert_called_once_with(123)
    def test_empty_news_cleanup_does_not_poll_ten_seconds(self):
        wake=self.event();work=MagicMock();work.next_due.return_value=None;work.delay.return_value=900
        self.run_loop('features/news.py','cleanup_loop',dict(CLEANUP_WAKE=wake,db_work=work,cleanup=MagicMock(),bot=object(),LOG=MagicMock()))
        wake.wait.assert_called_once_with(900)
    def test_news_cleanup_uses_inactivity_deadline(self):
        wake=self.event();work=MagicMock();work.next_due.return_value=12345;work.delay.return_value=300
        self.run_loop('features/news.py','cleanup_loop',dict(CLEANUP_WAKE=wake,db_work=work,cleanup=MagicMock(),bot=object(),LOG=MagicMock()))
        work.delay.assert_called_once_with(12345);wake.wait.assert_called_once_with(300)
    def test_news_fetch_uses_deadlines(self):
        wake=self.event();work=MagicMock();work.next_due.return_value=12345;work.delay.return_value=600
        refresh=MagicMock();auto=MagicMock(return_value=None)
        self.run_loop('features/news.py','loop',dict(NEWS_WAKE=wake,db_work=work,refresh=refresh,auto=auto,bot=object(),LOG=MagicMock()))
        refresh.assert_called_once();auto.assert_called_once();wake.wait.assert_called_once_with(600)
    def test_empty_broadcast_recovery_sleeps(self):
        wake=self.event();con=MagicMock();con.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value=[]
        work=MagicMock();work.delay.return_value=900
        self.run_loop('features/owner_dashboard.py','_resume_broadcasts',dict(BROADCAST_WAKE=wake,db_work=work,get_db_connection=lambda:con,_send_broadcast=MagicMock()))
        wake.wait.assert_called_once_with(900)
    def test_game_idle_sleep_and_fast_active_tick_remain(self):
        for file in ['features/draw_guess.py','features/nan_yate.py']:
            for active,expected in [(False,900),(True,3)]:
                with self.subTest(file=file,active=active):
                    wake=self.event();work=MagicMock();work.delay.return_value=900
                    self.run_loop(file,'loop',dict(WAKE=wake,db_work=work,tick=lambda bot:active,bot=object(),LOG=MagicMock()))
                    wake.wait.assert_called_once_with(expected)

class DailyAndScheduleTests(unittest.TestCase):
    run_loop=WorkerSleepTests.run_loop
    event=WorkerSleepTests.event
    # These tests execute the actual nested scheduler with simulated clock/DB.
    def daily_namespace(self,now,wake):
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        work=MagicMock();work.delay.return_value=900
        clock=MagicMock();clock.now.return_value=now
        return dict(DAILY_WAKE=wake,datetime=clock,MMT=ZoneInfo('Asia/Yangon'),timedelta=timedelta,
                    active_groups=MagicMock(return_value=[-1]),random_post_minute=lambda cid,day:0,
                    get_card_id=MagicMock(return_value=42),publish=MagicMock(),time=MagicMock(),db_work=work)
    def test_daily_posted_group_not_queried_on_each_recovery(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        wake=MagicMock();wake.wait.side_effect=[False,StopLoop]
        env=self.daily_namespace(datetime(2026,10,19,1,tzinfo=ZoneInfo('Asia/Yangon')),wake)
        self.run_loop('features/daily_challenge.py','daily_auto_loop',env)
        env['get_card_id'].assert_called_once_with(-1,env['datetime'].now.return_value.date())
        env['publish'].assert_not_called()
        self.assertEqual(wake.wait.call_args_list[0].args,(900,))
    def test_daily_future_minute_does_not_query_card_early(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        wake=self.event();env=self.daily_namespace(datetime(2026,10,19,1,tzinfo=ZoneInfo('Asia/Yangon')),wake)
        env['random_post_minute']=lambda cid,day:180
        self.run_loop('features/daily_challenge.py','daily_auto_loop',env)
        env['get_card_id'].assert_not_called();env['publish'].assert_not_called()
        due=env['db_work'].delay.call_args.args[0]
        self.assertEqual(due,datetime(2026,10,19,3,tzinfo=ZoneInfo('Asia/Yangon')).timestamp())
    def test_daily_cache_resets_next_day(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        wake=MagicMock();wake.wait.side_effect=[False,StopLoop]
        env=self.daily_namespace(None,wake)
        env['datetime'].now.side_effect=[datetime(2026,10,19,23,tzinfo=ZoneInfo('Asia/Yangon')),datetime(2026,10,20,1,tzinfo=ZoneInfo('Asia/Yangon'))]
        self.run_loop('features/daily_challenge.py','daily_auto_loop',env)
        self.assertEqual(env['get_card_id'].call_count,2)
    def schedule(self,due,queued=False):
        wake=self.event();con=MagicMock()
        con.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.side_effect=[(due,),(queued,)]
        clock=MagicMock();clock.time.return_value=1000;clock.monotonic.return_value=4000
        work=MagicMock();work.timestamp.side_effect=db_work.timestamp;work.delay.return_value=900
        self.run_loop('features/owner_operations.py','supervisor',dict(SCHEDULE_WAKE=wake,time=clock,db_work=work,due_schedules=MagicMock(),get_db_connection=lambda:con))
        return wake
    def test_empty_owner_scheduler_sleeps(self):self.schedule(None).wait.assert_called_once_with(900)
    def test_blocked_overdue_schedule_backs_off_instead_of_spinning(self):
        from datetime import datetime,timezone
        self.schedule(datetime.fromtimestamp(999,timezone.utc)).wait.assert_called_once_with(60)
    def test_queued_schedule_remains_responsive(self):self.schedule(None,True).wait.assert_called_once_with(60)
