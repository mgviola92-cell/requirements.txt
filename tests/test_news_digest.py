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
        with patch('features.owner_operations.is_owner',return_value=False),patch.object(news,'get_db_connection') as db:control(m)
        db.assert_not_called();self.assertIn(news.text('admin'),bot.reply_to.call_args.args)

if __name__=='__main__':unittest.main()
