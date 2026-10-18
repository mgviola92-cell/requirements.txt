import ast,io,time,unittest,urllib.error
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,Mock,patch
from contextlib import contextmanager
from core import news_digest as news,telegram_media as media
from features import draw_guess as draw,nan_yate as nan
from games import draw_guess as game

class BandwidthRoundTwoTests(unittest.TestCase):
    def setUp(self):media._CACHE.clear()
    def test_conditional_news_request_304_never_reads_or_parses_body(self):
        validators={'etag':'"v1"','modified':'Wed, 14 Oct 2026 10:00:00 GMT'}
        error=urllib.error.HTTPError('https://example.org/rss',304,'Not Modified',{},None)
        with patch.object(news.urllib.request,'urlopen',side_effect=error) as get,patch.object(news,'parse') as parse:
            self.assertEqual(news.fetch({'url':'https://example.org/rss'},time.time(),validators),(None,0))
            headers={k.lower():v for k,v in get.call_args.args[0].header_items()}
            self.assertEqual(headers['if-none-match'],'"v1"');self.assertIn('if-modified-since',headers);parse.assert_not_called()
        self.assertEqual(validators['etag'],'"v1"')
    def test_news_validators_only_replaced_after_successful_parse(self):
        response=MagicMock();response.__enter__.return_value=response;response.status=200;response.headers={'ETag':'"v2"'};response.read.return_value=b'feed'
        old={'etag':'"v1"','modified':'yesterday'}
        with patch.object(news.urllib.request,'urlopen',return_value=response),patch.object(news,'parse',side_effect=ValueError('bad xml')):
            with self.assertRaises(ValueError):news.fetch({'url':'https://example.org/rss'},0,old)
        self.assertEqual(old['etag'],'"v1"')
        with patch.object(news.urllib.request,'urlopen',return_value=response),patch.object(news,'parse',return_value=([],0)):
            news.fetch({'url':'https://example.org/rss'},0,old)
        self.assertEqual(old,{'etag':'"v2"','modified':None})
    def test_photo_reuse_durable_and_scoped_to_bot_and_content(self):
        bot=NS(token='123:test',send_photo=Mock(return_value=NS(photo=[NS(file_id='cached-photo')])));image=io.BytesIO(b'image')
        con=MagicMock();con.__enter__.return_value=con;cur=con.cursor.return_value.__enter__.return_value;cur.fetchone.return_value=None
        with patch.object(media,'get_db_connection',return_value=con):
            media.send_photo(bot,-1,image,caption='first')
            media.send_photo(bot,-2,io.BytesIO(b'image'),caption='second')
        self.assertIs(bot.send_photo.call_args_list[0].args[1],image)
        self.assertEqual(bot.send_photo.call_args_list[1].args[1],'cached-photo')
        self.assertEqual(bot.send_photo.call_args.kwargs['caption'],'second')
        self.assertNotEqual(media.key(bot,image),media.key(NS(token='other:bot'),image))
        self.assertNotEqual(media.key(bot,image),media.key(bot,io.BytesIO(b'new drawing')))
        self.assertTrue(any('INSERT INTO telegram_photo_cache' in str(c) for c in cur.execute.call_args_list))
    def test_stored_photo_id_used_for_edit_and_invalid_id_upload_retried_once(self):
        bot=NS(token='123:test',edit_message_media=Mock());image=io.BytesIO(b'image');identity=media.key(bot,image);media.remember(identity,'old-id',persist=False)
        error=RuntimeError('Bad Request: wrong file identifier');error.error_code=400
        bot.edit_message_media.side_effect=[error,NS(photo=[NS(file_id='new-id')])]
        with patch.object(media,'get_db_connection'):
            media.edit_photo(bot,-1,9,image,caption='new caption')
        self.assertEqual(bot.edit_message_media.call_count,2)
        self.assertEqual(bot.edit_message_media.call_args_list[0].args[0].media,'old-id')
        self.assertEqual(media.lookup(identity),'new-id')
    def test_photo_permission_error_does_not_trigger_upload(self):
        bot=NS(token='123:test',send_photo=Mock());image=io.BytesIO(b'image');media.remember(media.key(bot,image),'stored',persist=False)
        error=RuntimeError('Forbidden');error.error_code=403;bot.send_photo.side_effect=error
        with self.assertRaises(RuntimeError):media.send_photo(bot,-1,image)
        bot.send_photo.assert_called_once();self.assertEqual(bot.send_photo.call_args.args[1],'stored')
    def test_recent_draw_heartbeat_does_not_write_state_again(self):
        s=game.create('g',-42,1,{},100);s.update(phase='guess',deadline=300,updated=195,image='X'*300000,words=[('ကြောင်',[])])
        con=MagicMock();con.__enter__.return_value=con;cur=con.cursor.return_value.__enter__.return_value;cur.fetchall.return_value=[(-42,)]
        txcur=MagicMock()
        @contextmanager
        def tx(**kw):yield txcur,s,-42
        with patch.object(draw,'get_db_connection',return_value=con),patch.object(draw,'tx',tx),patch.object(draw,'start_session'),patch.object(draw,'persist') as persist,patch.object(draw,'drain'),patch.object(draw.time,'time',return_value=200):
            self.assertTrue(draw.tick(MagicMock()))
        persist.assert_not_called();txcur.execute.assert_not_called()
    def test_idle_game_workers_wait_longer_but_active_games_keep_fast_ticks(self):
        for file,delay in [('draw_guess',3),('nan_yate',3)]:
            node=next(n for n in ast.walk(ast.parse(Path('features/'+file+'.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='loop')
            for active in (False,True):
                wake=Mock();wake.wait.side_effect=StopIteration;con=MagicMock();con.__enter__.return_value=con;con.cursor.return_value.__enter__.return_value.fetchall.return_value=[(-1,)] if active else []
                env=dict(WAKE=wake,tick=Mock(return_value=active),bot=Mock(),LOG=Mock(),get_db_connection=lambda:con)
                exec(compile(ast.Module(body=[node],type_ignores=[]),'worker','exec'),env)
                with self.assertRaises(StopIteration):env['loop']()
                wake.wait.assert_called_once_with(delay if active else 30)
    def test_unchanged_news_item_not_serialized_and_uploaded_again(self):
        from features import news as feature
        item=dict(key='k',title='headline',published=1000,brief='',revision='v1')
        con=MagicMock();con.__enter__.return_value=con;cur=con.cursor.return_value.__enter__.return_value;cur.fetchone.side_effect=[None,(dict(item),)]
        with patch.object(feature,'get_db_connection',return_value=con),patch.object(feature.engine,'fetch',return_value=([dict(item)],0)):
            self.assertEqual(feature.ingest({'id':'source'},2000),(1,'ok'))
        sql=[c.args[0] for c in cur.execute.call_args_list]
        self.assertFalse(any('INSERT INTO news_items' in q for q in sql))
        self.assertTrue(any('INSERT INTO news_health' in q for q in sql))
    def test_news_not_modified_keeps_health_success_and_previous_count(self):
        from features import news as feature
        con=MagicMock();con.__enter__.return_value=con;cur=con.cursor.return_value.__enter__.return_value;cur.fetchone.return_value=({'etag':'v1'},)
        with patch.object(feature,'get_db_connection',return_value=con),patch.object(feature.engine,'fetch',return_value=(None,0)):
            self.assertEqual(feature.ingest({'id':'source'},2000),(0,'not-modified'))
        sql,args=cur.execute.call_args.args
        self.assertIn('THEN news_health.items',sql);self.assertIsNotNone(args[1]);self.assertEqual(args[2],'not-modified')
    def test_pending_cleanup_keeps_worker_fast_after_game_ends(self):
        for module in (draw,nan):
            con=MagicMock();con.__enter__.return_value=con;cur=con.cursor.return_value.__enter__.return_value;cur.fetchall.return_value=[]
            for pending in (True,False):
                cur.fetchone.return_value=(pending,)
                with patch.object(module,'get_db_connection',return_value=con),patch.object(module,'drain'):
                    self.assertEqual(module.tick(Mock()),pending)
