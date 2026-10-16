import io,json,random,time,unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock,MagicMock,patch
from flask import Flask
from core.batched_writes import BatchWriter
from core import traffic_meter as meter
from features import draw_guess as draw,owner_dashboard as owner
from games import draw_guess as game

class RoundThreeTests(unittest.TestCase):
    def connection(self):
        con=MagicMock();con.__enter__.return_value=con
        return con,con.cursor.return_value.__enter__.return_value
    def test_activity_batch_collapses_repeats_but_keeps_other_members(self):
        batch=BatchWriter('INSERT example VALUES(%s,%s)');batch.started=True
        batch.submit(('g',1),(1,'old'));batch.submit(('g',1),(1,'new'));batch.submit(('g',2),(2,'other'))
        con,cur=self.connection()
        with patch('core.batched_writes.get_db_connection',return_value=con):self.assertTrue(batch.flush())
        cur.executemany.assert_called_once_with(batch.sql,[(1,'new'),(2,'other')]);self.assertFalse(batch.snapshot())
    def test_failed_batch_retained_and_newer_metadata_wins(self):
        batch=BatchWriter('INSERT example VALUES(%s)');batch.started=True;batch.submit(1,('old',))
        con,cur=self.connection()
        def fail(*args):batch.submit(1,('new',));raise RuntimeError('offline')
        cur.executemany.side_effect=fail
        with patch('core.batched_writes.get_db_connection',return_value=con):self.assertFalse(batch.flush())
        self.assertEqual(batch.snapshot(),[('new',)])
        cur.executemany.side_effect=None
        with patch('core.batched_writes.get_db_connection',return_value=con):self.assertTrue(batch.flush())
    def test_draw_image_separate_and_events_not_replayed_from_state(self):
        s=game.create('g',-1,1,{},100);s.update(image='X'*300000,epoch=2,events=[dict(kind='round')])
        cur=MagicMock()
        with patch('features.group_studio.credit'):draw.persist(cur,s,110)
        image_call=next(c for c in cur.execute.call_args_list if c.args[0].startswith('INSERT INTO draw_guess_images'))
        self.assertEqual(image_call.args[1],('g',2,'X'*300000))
        state_call=next(c for c in cur.execute.call_args_list if c.args[0].startswith('INSERT INTO draw_guess_games'))
        stored=json.loads(state_call.args[1][2]);self.assertIsNone(stored['image']);self.assertEqual(stored['image_epoch'],2);self.assertEqual(stored['events'],[])
        self.assertLess(len(state_call.args[1][2]),2000)
    def test_draw_lazy_image_fetch_and_round_change_never_loads_old_image(self):
        cur=MagicMock();cur.fetchone.return_value=('saved-image',)
        s=dict(id='g',epoch=3,image_epoch=3,image=None)
        self.assertEqual(draw.drawing(cur,s),'saved-image');cur.execute.assert_called_once()
        cur.reset_mock();s['epoch']=4
        self.assertIsNone(draw.drawing(cur,s));cur.execute.assert_not_called()
    def test_game_next_round_clears_image_reference(self):
        s=game.create('g',-1,1,{},100);game.join(s,1,'A');game.join(s,2,'B');game.begin(s,101,random.Random(1));s['image_epoch']=s['epoch']
        game.next_round(s,102,random.Random(1))
        self.assertIsNone(s['image_epoch']);self.assertIsNone(s['image'])
    def test_unchanged_group_metadata_throttled_but_leaving_immediate(self):
        con,cur=self.connection();chat=NS(type='supergroup',id=-876,title='Group')
        with patch.object(owner,'get_db_connection',return_value=con),patch.object(owner,'_GROUP_SEEN',{}):
            owner.record_group(chat);owner.record_group(chat);owner.record_group(chat,False)
        self.assertEqual(cur.execute.call_count,2);self.assertFalse(cur.execute.call_args.args[1][2])
    def test_meter_counts_only_sizes_and_is_owner_protected(self):
        secret='DO_NOT_STORE_ME';meter.record('test','test_function',sent=meter.size(secret),received=10)
        report=meter.snapshot();self.assertNotIn(secret,json.dumps(report))
        row=next(r for r in report['rows'] if r['category']=='test');self.assertGreaterEqual(row['sent_bytes'],len(secret))
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(owner.dashboard)
        with app.test_client() as client,patch.object(owner,'_ready',return_value=True):
            self.assertEqual(client.get('/owner/bandwidth').status_code,302)
            with client.session_transaction() as session:session['owner']=True
            response=client.get('/owner/bandwidth?format=json');self.assertEqual(response.status_code,200);self.assertIn('rows',response.json)
    def test_telegram_meter_never_stores_token_or_message_content(self):
        import requests
        real=requests.Session.send
        try:
            with patch.object(requests.Session,'send',return_value=NS(content=b'ok')):
                meter.install_telegram()
                request=requests.Request('POST','https://api.telegram.org/botSUPER_SECRET_TOKEN/sendMessage',data=b'private text').prepare()
                requests.Session().send(request)
            report=json.dumps(meter.snapshot())
            self.assertNotIn('SUPER_SECRET_TOKEN',report);self.assertNotIn('private text',report)
            self.assertIn('sendMessage',report)
        finally:requests.Session.send=real
    def test_draw_round_transition_releases_previous_images(self):
        s=game.create('g',-1,1,{},100);s.update(epoch=2,events=[dict(kind='round')])
        cur=MagicMock();draw.persist(cur,s,110)
        self.assertTrue(any('DELETE FROM draw_guess_images' in c.args[0] and c.args[1]==('g',2) for c in cur.execute.call_args_list))
    def test_normal_pool_shutdown_flushes_activity_before_closing(self):
        from database import db
        order=[];pool=Mock();pool.close.side_effect=lambda:order.append('close')
        with patch('core.batched_writes.flush_all',side_effect=lambda:order.append('flush')):db._close_pool(pool)
        self.assertEqual(order,['flush','close'])
