import unittest,time
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,patch
from features import news,news_owner
from database import news_preferences
from core import customization

class SourcePickerTests(unittest.TestCase):
    def setUp(self):
        news_owner.DRAFTS.clear();self.bot=MagicMock();self.callbacks=[];self.commands=[]
        self.bot.message_handler.side_effect=lambda **kw:lambda fn:self.commands.append(fn) or fn
        self.bot.callback_query_handler.side_effect=lambda **kw:lambda fn:self.callbacks.append(fn) or fn
        self.replace=MagicMock();news_owner.register(self.bot,self.replace,MagicMock())
        self.auth=patch('features.owner_operations.is_owner',side_effect=lambda uid:uid==1);self.auth.start()
        self.panel=patch('features.owner_dashboard._load_panel_state',return_value=(None,10,None));self.panel.start()
        self.refresh=patch.object(news_owner,'refresh');self.refresh.start()
        self.sources=patch.object(news,'sources_for',return_value=['dvb']);self.sources.start()
    def tearDown(self):
        self.auth.stop();self.panel.stop();self.refresh.stop();self.sources.stop();news_owner.DRAFTS.clear()
    def q(self,uid=1,data='nws:open',kind='private',mid=10):return NS(id='q',data=data,from_user=NS(id=uid),message=NS(chat=NS(type=kind,id=uid),message_id=mid))
    def tap(self,q):self.callbacks[0](q)
    def test_owner_news_control_submenu(self):
        self.tap(self.q(data='nws:home'))
        self.replace.assert_called_once()
        self.assertIn('သတင်းထိန်းချုပ်မှု',self.replace.call_args.args[2])
        buttons=self.replace.call_args.args[3].keyboard
        self.assertTrue(any(b.callback_data=='nws:open' for row in buttons for b in row))

    def test_unauthorized_or_group_never_opens(self):
        self.tap(self.q(uid=2));self.tap(self.q(kind='group'));self.replace.assert_not_called()
    def test_toggle_is_draft_until_save_and_empty_is_valid(self):
        self.tap(self.q());d=news_owner.DRAFTS[1];token=d['token']
        with patch.object(news_owner,'save') as save:
            self.tap(self.q(data=f'nws:{token}:none'));save.assert_not_called()
            self.tap(self.q(data=f'nws:{token}:save'));save.assert_called_once_with(0,'cfg.features.news.source_ids',[],1)
        customization.validate('cfg.features.news.source_ids',[])
    def test_stale_menu_cannot_change_source(self):
        self.tap(self.q());d=news_owner.DRAFTS[1]
        self.tap(self.q(data=f"nws:{d['token']}:none",mid=9));self.assertEqual(d['selected'],{'dvb'})
    def test_external_change_refuses_overwrite(self):
        self.tap(self.q());d=news_owner.DRAFTS[1]
        with patch.object(news,'sources_for',return_value=['shan']),patch.object(news_owner,'save') as save:
            self.tap(self.q(data=f"nws:{d['token']}:save"));save.assert_not_called()
    def test_nonempty_other_lists_still_required(self):
        with self.assertRaises(ValueError):customization.validate('cfg.features.draw_guess.words',[])
    def test_activation_only_moves_when_reenabled(self):
        cur=MagicMock();news_preferences.sync_sources(cur,['dvb'])
        query=next(c.args[0] for c in cur.execute.call_args_list if 'ON CONFLICT(source_id)' in c.args[0])
        self.assertIn('EXCLUDED.enabled AND NOT news_source_activation.enabled',query)
        self.assertIn('IS DISTINCT FROM',query)

class AutomaticNewsTests(unittest.TestCase):
    def run_auto(self,published,activated,cursor,explicit=True,gate=True,already_sent=False,discovered=None):
        now=datetime.now(timezone.utc);con=MagicMock();con.__enter__.return_value=con
        cur=con.cursor.return_value.__enter__.return_value;last=['']
        cur.execute.side_effect=lambda q,*args:last.__setitem__(0,q)
        def all_rows():
            q=last[0]
            if 'owner_groups g' in q:return [(-1,explicit,None,None)]
            if 'news_source_activation' in q:return [('dvb',now-timedelta(seconds=activated))]
            if 'FROM news_sent' in q:return [('a','r')] if already_sent else []
            return []
        def one_row():
            if 'RETURNING chat_id' in last[0]:return (-1,)
            if 'SELECT cursor_at' in last[0]:return (now-timedelta(seconds=cursor),)
            return None
        cur.fetchall.side_effect=all_rows;cur.fetchone.side_effect=one_row
        a=dict(key='a',source='dvb',name='DVB',family='dvb',title='သတင်းအသစ် ခေါင်းစဉ်',published=now.timestamp()-published,url='https://example.org/a',brief='',correction=False,revision='r')
        if discovered is not None:a['discovered']=now.timestamp()-discovered
        bot=MagicMock()
        with patch.object(news,'get_db_connection',return_value=con),patch.object(news,'load',return_value=([[a]],[])),patch.object(news,'cfg',side_effect=lambda key,cid=0:news.DEFAULTS[key]),patch.object(news,'setting_value',return_value=True),patch('features.owner_operations.feature_allowed',return_value=True),patch('core.startup_safety.AUTO_POSTS.allow',return_value=gate),patch.object(news,'send') as send:
            news.auto(bot)
        return send,cur
    def test_single_source_new_story_is_delivered(self):
        send,cur=self.run_auto(60,500,300);send.assert_called_once()
        self.assertIn('<b>▌ 1။',send.call_args.args[2])
        calls=[c.args[0] for c in cur.execute.call_args_list]
        self.assertGreater(next(i for i,q in enumerate(calls) if 'INSERT INTO news_auto_state' in q),next(i for i,q in enumerate(calls) if 'SELECT cursor_at' in q))
    def test_newly_discovered_story_not_lost_behind_cursor(self):
        self.run_auto(400,1000,300,discovered=60)[0].assert_called_once()
    def test_preselection_history_is_not_delivered(self):self.run_auto(600,300,900)[0].assert_not_called()
    def test_repeat_or_disabled_group_is_not_delivered(self):
        self.run_auto(60,500,300,already_sent=True)[0].assert_not_called()
        self.run_auto(60,500,300,explicit=False)[0].assert_not_called()
    def test_old_outage_backlog_is_not_delivered(self):self.run_auto(7200,10000,10000)[0].assert_not_called()
    def test_startup_gate_does_not_advance_cursor(self):
        send,cur=self.run_auto(60,500,300,gate=False);send.assert_not_called()
        self.assertFalse(any('INSERT INTO news_auto_state' in c.args[0] for c in cur.execute.call_args_list))
    def test_news_status_uses_active_refresh_interval(self):
        import inspect
        source=inspect.getsource(news.register)
        self.assertIn("minutes=cfg('refresh_minutes',0)",source)

    def test_digest_never_exceeds_five_stories(self):
        import inspect
        source=inspect.getsource(news.auto)
        self.assertIn('render(cid,eligible[:5],health)',source)

    def test_source_choice_is_global(self):
        with patch.object(news,'cfg',return_value=['dvb']) as cfg:self.assertEqual(news.sources_for(-123),['dvb'])
        cfg.assert_called_once_with('source_ids',0)
