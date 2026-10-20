import json,time,unittest,html
from datetime import datetime,timezone
from unittest.mock import MagicMock,patch
from core import news_digest as engine,customization as custom
from data.news_sources import CATALOG
from features import news

NOW=datetime(2026,10,14,9,tzinfo=timezone.utc).timestamp()
DATE='Wed, 14 Oct 2026 08:00:00 GMT'
def xml(title='Myanmar update about a local hospital',date=DATE,url='https://example.com/story',extra=''):
    return f'<rss><channel><item><title>{html.escape(title)}</title><link>{html.escape(url)}</link><pubDate>{date}</pubDate>{extra}</item></channel></rss>'.encode()
def item(key='1',source='myanmar_now',title='မြန်မာနိုင်ငံ ကျောင်းတစ်ကျောင်းကို ပြုပြင်ဖွင့်လှစ်လိုက်ကြောင်း ထုတ်ပြန်'):
    source=CATALOG[source]
    return dict(key=key,source=source['id'],name=source['name'],family=source['family'],title=title,url='https://example.com/'+key,published=time.time()-60,revision='a',brief='',correction=False)

class FeedTests(unittest.TestCase):
    def test_rss_atom_dates_and_filtering(self):
        items,missing=engine.parse(xml(),CATALOG['bbc_asia'],NOW)
        self.assertEqual(len(items),1);self.assertEqual(missing,0)
        self.assertEqual(engine.parse(xml('Football in London'),CATALOG['bbc_asia'],NOW)[0],[])
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Myanmar local news update</title><link href="https://example.com/story"/><published>2026-10-14T08:00:00Z</published></entry></feed>'
        self.assertEqual(len(engine.parse(atom,CATALOG['bbc_asia'],NOW)[0]),1)

    def test_missing_future_and_old_dates_are_not_invented(self):
        self.assertEqual(engine.parse(xml(date=''),CATALOG['myanmar_now'],NOW),( [],1))
        for date in ('Wed, 14 Oct 2027 08:00:00 GMT','Wed, 14 Oct 2025 08:00:00 GMT'):
            self.assertFalse(engine.parse(xml(date=date),CATALOG['myanmar_now'],NOW)[0])

    def test_unsafe_xml_urls_and_unmatched_index_publisher(self):
        with self.assertRaises(ValueError):engine.parse(b'<!DOCTYPE rss><rss/>',CATALOG['myanmar_now'],NOW)
        self.assertFalse(engine.parse(xml(url='javascript:alert(1)'),CATALOG['myanmar_now'],NOW)[0])
        self.assertFalse(engine.parse(xml(extra='<source>Unknown Outlet</source>'),CATALOG['reuters'],NOW)[0])
        self.assertTrue(engine.parse(xml(extra='<source>Reuters</source>'),CATALOG['reuters'],NOW)[0])

    def test_source_count_does_not_double_language_editions_or_wire(self):
        a=item(source='bbc_asia');b=item('2',source='bbc_burmese');self.assertEqual(len(engine.families([a,b])),1)
        a=item(source='irrawaddy',title='Myanmar incident report (Reuters)');b=item('2',source='reuters',title=a['title'])
        self.assertEqual(len(engine.families([a,b])),1)

    def test_conservative_dedup_conflicting_numbers_separate(self):
        a=item(title='Myanmar hospital opens 5 new wards for patients');b=item('2',source='irrawaddy',title=a['title'])
        self.assertEqual(len(engine.clusters([a,b])),1)
        b['title']='Myanmar hospital opens 50 new wards for patients'
        self.assertEqual(len(engine.clusters([a,b])),2)
        b['title']=a['title'];b['published']=a['published']-48*3600
        self.assertEqual(len(engine.clusters([a,b])),2)

class DigestTests(unittest.TestCase):
    def test_markup_and_source_links_and_claim_labels(self):
        with patch.object(news,'cfg',side_effect=lambda key,cid=0:news.DEFAULTS[key]):
            body,items,count=news.render(-1,[[item(title='<script>not markup</script> Myanmar story')]],[])
        self.assertNotIn('<script>',body);self.assertIn('&lt;script&gt;',body)
        self.assertIn('https://example.com/',body);self.assertIn('fact-check',body);self.assertEqual(count,1)
        self.assertEqual(len(items),1)

    def test_differentiate_no_news_outage_and_cold_cache(self):
        self.assertEqual(news.render(-1,[],[])[0],news.text('warming'))
        self.assertEqual(news.render(-1,[],[('myanmar_now','ok',datetime.now(timezone.utc))])[0],news.text('empty'))
        self.assertEqual(news.render(-1,[],[('myanmar_now','HTTPError',datetime.now(timezone.utc))])[0],news.text('unavailable'))

    def test_render_count_supports_paging_without_skipping(self):
        groups=[[item(str(i),title=('သတင်းအကြောင်းအရာ '+str(i)+' ') *35)] for i in range(8)]
        with patch.object(news,'cfg',side_effect=lambda key,cid=0:8 if key=='items' else news.DEFAULTS[key]):
            body,items,count=news.render(-1,groups,[])
        self.assertLess(len(body),4096);self.assertGreater(count,0)
        button=news.keyboard(0,len(groups),count).keyboard[0][0]
        self.assertEqual(button.callback_data,'news:'+str(count))

    def test_owner_brief_and_known_source_validation(self):
        a=item();a['brief']='စစ်ပြီးရေးထားသော အကျဉ်းချုပ်';self.assertEqual(engine.headline(a),a['brief'])
        for ids in (['unknown'],['myanmar_now','myanmar_now']):
            with self.assertRaises(ValueError):custom.validate('cfg.features.news.source_ids',ids)
        custom.validate('cfg.features.news.source_ids',['myanmar_now','irrawaddy'])

    def test_one_source_failure_does_not_replace_old_cache(self):
        con=MagicMock();con.__enter__.return_value=con;cur=con.cursor.return_value.__enter__.return_value
        with patch.object(news,'get_db_connection',return_value=con),patch.object(engine,'fetch',side_effect=TimeoutError()):
            count,status=news.ingest(CATALOG['myanmar_now'],NOW)
        self.assertEqual(count,0);self.assertEqual(status,'TimeoutError')
        self.assertFalse(any('DELETE FROM news_items' in str(call) for call in cur.execute.call_args_list))

    def test_admin_control_refuses_member(self):
        bot=MagicMock();handlers=[];bot.message_handler.side_effect=lambda **kw:lambda fn:handlers.append((kw,fn)) or fn
        bot.callback_query_handler.side_effect=lambda **kw:lambda fn:fn
        with patch.object(news,'READY',False),patch.object(news,'initialize',side_effect=RuntimeError()):news.register(bot)
        control=next(fn for kw,fn in handlers if 'newson' in kw.get('commands',[]))
        m=MagicMock();m.chat.type='supergroup';m.chat.id=-1;m.text='/newson';m.from_user.id=42
        bot.get_chat_member.return_value.status='member'
        with patch('features.owner_operations.is_owner',return_value=False),patch.object(news,'get_db_connection') as db,patch.object(news,'track',side_effect=lambda m:m):control(m)
        db.assert_not_called();self.assertIn(news.text('admin'),bot.reply_to.call_args.args)

class CleanupTests(unittest.TestCase):
    def database(self):
        con=MagicMock();con.__enter__.return_value=con
        return con,con.cursor.return_value.__enter__.return_value

    def test_send_tracks_five_minute_deadline(self):
        con,cur=self.database();bot=MagicMock()
        bot.send_message.return_value.chat.id=-42;bot.send_message.return_value.message_id=9
        with patch.object(news,'get_db_connection',return_value=con):news.send(bot,-42,'news')
        sql,args=cur.execute.call_args.args
        self.assertIn("INTERVAL '5 minutes'",sql);self.assertEqual(args,(-42,9))

    def test_tap_resets_only_existing_card(self):
        con,cur=self.database();cur.fetchone.return_value=(9,)
        with patch.object(news,'get_db_connection',return_value=con):self.assertTrue(news.touch(-42,9))
        self.assertIn("SET expires_at=NOW()+INTERVAL '5 minutes'",cur.execute.call_args.args[0])
        cur.fetchone.return_value=None
        with patch.object(news,'get_db_connection',return_value=con):self.assertFalse(news.touch(-42,9))

    def test_expired_cleanup_and_retry(self):
        con,cur=self.database();cur.fetchall.return_value=[(-42,9),(-42,10)];bot=MagicMock()
        bot.delete_message.side_effect=[None,RuntimeError('temporary network error')]
        with patch.object(news,'get_db_connection',return_value=con):news.cleanup(bot)
        calls=cur.execute.call_args_list
        self.assertIn('expires_at<=NOW()',calls[0].args[0]);self.assertIn('FOR UPDATE SKIP LOCKED',calls[0].args[0])
        self.assertIn('DELETE FROM news_messages',calls[1].args[0]);self.assertEqual(calls[1].args[1],(-42,9))
        self.assertIn("INTERVAL '1 minute'",calls[2].args[0]);self.assertEqual(calls[2].args[1],(-42,10))

    def test_groups_hide_owner_ids(self):
        body,_,_=news.render(-42,[[item(key='secret-editor-id')]],[])
        self.assertNotIn('<code>secret-editor-id</code>',body)
        self.assertIn('🕒',body)

if __name__=='__main__':unittest.main()

class ReaderTests(unittest.TestCase):
    def test_extract_is_clean_bounded_and_not_title(self):
        self.assertEqual(engine.excerpt('Same headline','Same headline'),'')
        value=engine.excerpt('<script>evil()</script><p>'+('word '*500)+'</p>')
        self.assertNotIn('evil',value);self.assertLessEqual(len(value.split()),100)
        self.assertLessEqual(len(engine.excerpt('က'*5000)),1201)

    def test_feed_extract_and_legacy_fallback(self):
        data=engine.parse(xml(extra='<description>&lt;p&gt;A detailed report about Myanmar.&lt;/p&gt;</description>'),CATALOG['myanmar_now'],NOW)[0][0]
        self.assertEqual(data['excerpt'],'A detailed report about Myanmar.')
        body,kb=news.reader([[item()]],'1',0)
        self.assertIn(news.text('no_detail'),body)
        self.assertEqual(kb.keyboard[-1][0].callback_data,'news:0')

    def test_stable_id_navigation_and_html(self):
        a=item('a');a['excerpt']='Details & <unsafe>'
        b=item('b');groups=[[b],[a]]
        body,kb=news.reader(groups,'a',0)
        self.assertIn('Details &amp;',body);self.assertNotIn('<unsafe>',body)
        self.assertEqual(kb.keyboard[0][0].callback_data,'news:r:b:0')
        self.assertIsNone(news.reader(groups,'deleted',0))
        buttons=news.keyboard(0,2,2,groups).keyboard
        self.assertEqual(buttons[0][0].callback_data,'news:r:b:0')
        self.assertEqual(buttons[1][0].callback_data,'news:r:a:0')

    def test_owner_brief_has_priority_without_claiming_translation(self):
        a=item();a.update(brief='Owner text',excerpt='Source text')
        body,_=news.reader([[a]],'1',0)
        self.assertIn('Owner text',body);self.assertNotIn('Source text',body)
        self.assertLess(len(body),4096)

    def test_reader_callback_edits_same_card_and_renews_deadline(self):
        bot=MagicMock();callbacks=[]
        bot.message_handler.side_effect=lambda **kw:lambda fn:fn
        bot.callback_query_handler.side_effect=lambda **kw:lambda fn:callbacks.append(fn) or fn
        with patch.object(news,'initialize',side_effect=RuntimeError()),patch.object(news,'READY',False):news.register(bot)
        a=item();a['excerpt']='Cached article detail'
        c=MagicMock();c.id='tap';c.data='news:r:1:0';c.message.chat.id=-42;c.message.message_id=99
        with patch.object(news,'touch',return_value=True) as touch,patch.object(news,'load',return_value=([[a]],[])),patch('features.owner_operations.feature_allowed',return_value=True),patch.object(news,'setting_value',return_value=True):callbacks[0](c)
        touch.assert_called_once_with(-42,99)
        self.assertIn('Cached article detail',bot.edit_message_text.call_args.args[0])
        self.assertEqual(bot.edit_message_text.call_args.args[1:],(-42,99))
        bot.send_message.assert_not_called()
