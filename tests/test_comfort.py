import copy
import random
import threading
import unittest
from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,patch
from core.comfort_content import encode_emojis,emoji_pair,choose_line,render_line,body_hash
from data.comfort_lines import LINES
from features import comfort as f


class ContentTests(unittest.TestCase):
    def test_authored_bank_unique_short_and_no_emoji(self):
        self.assertGreaterEqual(len(LINES),340)
        self.assertEqual(len(LINES),len(set(LINES)))
        self.assertTrue(all(len(x)<130 and '\n' not in x for x in LINES))
        self.assertTrue(all(not any(ord(c)>0xffff or 0x2600<=ord(c)<=0x27ff for c in x) for x in LINES))

    def test_bank_avoids_self_announcing_bot_language(self):
        self.assertFalse(any(x in line for line in LINES for x in ('ချော့စာ','ဌာန','ရောက်လာပါပြီ')))

    def test_editor_uses_numeric_line_order(self):
        from features.owner_controls import KEYS
        keys=[k for k in KEYS if k.startswith('msg.comfort.line.')]
        self.assertEqual(keys,['msg.comfort.line.'+str(i) for i in range(len(LINES))])

    def test_no_repeat_and_duplicate_customization(self):
        lines=[(str(i),s) for i,s in enumerate(LINES)]+[('duplicate',LINES[0])]
        used=set();rng=random.Random(881)
        first=[]
        for _ in LINES:
            choice=choose_line(lines,used,rng)
            self.assertIsNotNone(choice)
            _,line,digest=choice;self.assertNotIn(digest,used);used.add(digest);first.append(line)
        self.assertIsNone(choose_line(lines,used,rng))
        self.assertNotEqual(first[0],LINES[0])

    def test_utf16_custom_emoji_capture_preserves_two_ids(self):
        m=NS(text='💛 🥺 ❤️',entities=[NS(type='custom_emoji',offset=0,length=2,custom_emoji_id='123'),NS(type='custom_emoji',offset=3,length=2,custom_emoji_id='456')])
        self.assertEqual(encode_emojis(m),'ce:123:💛 ce:456:🥺 ❤️')
        self.assertEqual(emoji_pair('ce:123:💛'),('<tg-emoji emoji-id="123">💛</tg-emoji>','💛'))

    def test_escape_target_name_and_text(self):
        value=render_line(123,'<x>','{name} & <bad>',emoji_pair('<script>')[0])
        self.assertIn('tg://user?id=123',value)
        self.assertNotIn('<script>',value);self.assertNotIn('<bad>',value)

    def test_config_defaults_and_all_lines_editable(self):
        from core.customization import CATALOG,validate
        for i,line in enumerate(LINES):
            key='msg.comfort.line.'+str(i)
            self.assertEqual(CATALOG[key]['default'],line);validate(key,line)
        self.assertEqual(f.DEFAULTS['interval'],5)
        validate('cfg.features.comfort.interval',5)
        for k in f.DEFAULTS:validate('cfg.features.comfort.'+k,f.DEFAULTS[k])


class ControlsTests(unittest.TestCase):
    def setUp(self):
        self.bot=MagicMock();self.handlers={};self.cur=MagicMock()
        def register(**kw):
            def wrap(fn):self.handlers[fn.__name__]=fn;return fn
            return wrap
        self.bot.message_handler.side_effect=register
        self.bot.callback_query_handler.side_effect=register
        @contextmanager
        def transaction():yield self.cur
        self.tx=transaction
        with patch.object(f,'transaction',self.tx):f.register(self.bot)
        self.cur.reset_mock();self.bot.reset_mock()
        self.owner_patch=patch.object(f,'owner',side_effect=lambda uid:uid==1);self.owner_patch.start()
        self.text_patch=patch.object(f,'text',side_effect=lambda k,**kw:f.MESSAGES[k].format(**kw));self.text_patch.start()
        f.ACTIVE.clear()
        self.run={'id':'r1','chat':-10,'target':2,'name':'ကလေး','count':2,'interval':15,'expires':2000,'event':threading.Event(),'reply':None}
        f.ACTIVE[-10]=self.run

    def tearDown(self):
        self.owner_patch.stop();self.text_patch.stop();f.ACTIVE.clear()

    def message(self,uid,text='',mid=22):return NS(chat=NS(id=-10,type='supergroup'),from_user=NS(id=uid),text=text,message_id=mid)

    def test_others_including_admin_cannot_stop(self):
        self.cur.fetchone.return_value=('r1',2,'active')
        with patch.object(f,'transaction',self.tx):self.handlers['stop'](self.message(3))
        self.assertFalse(self.run['event'].is_set())
        self.assertFalse(any('UPDATE comfort_runs' in a.args[0] for a in self.cur.execute.call_args_list))

    def test_owner_can_stop_without_blocking_target(self):
        self.cur.fetchone.return_value=('r1',2,'active')
        with patch.object(f,'transaction',self.tx):self.handlers['stop'](self.message(1))
        self.assertTrue(self.run['event'].is_set());self.assertNotIn(-10,f.ACTIVE)
        self.assertFalse(any('blocked=TRUE' in a.args[0] for a in self.cur.execute.call_args_list))

    def test_target_stops_and_persistently_blocks(self):
        self.cur.fetchone.return_value=('r1',2,'active')
        with patch.object(f,'transaction',self.tx):self.handlers['stop'](self.message(2))
        self.assertTrue(self.run['event'].is_set())
        self.assertTrue(any('blocked=TRUE' in a.args[0] for a in self.cur.execute.call_args_list))
        self.assertIn('comfort:allow:2',str(self.bot.reply_to.call_args.kwargs['reply_markup'].to_dict()))

    def test_owner_cannot_unblock_target_but_target_can(self):
        q=NS(id='cb',data='comfort:allow:2',from_user=NS(id=1),message=NS(chat=NS(id=-10),message_id=22))
        with patch.object(f,'transaction',self.tx):self.handlers['allow'](q)
        self.cur.execute.assert_not_called()
        q.from_user.id=2
        with patch.object(f,'transaction',self.tx):self.handlers['allow'](q)
        self.assertIn('blocked=FALSE',self.cur.execute.call_args.args[0])

    def test_target_text_records_reply_and_other_text_does_not(self):
        self.handlers['activity'](self.message(3));self.assertIsNone(self.run['reply'])
        self.handlers['activity'](self.message(2,'hello'))
        self.assertEqual(self.run['reply'][0],22)

    def test_worker_continues_past_six_until_stop_and_uses_recent_reply(self):
        run=copy.copy(self.run);run['event']=MagicMock();run['event'].is_set.return_value=False;run['event'].wait.side_effect=[False]*7+[True];run['reply']=(99,1000)
        self.cur.fetchone.side_effect=[('active',),(False,)]*8
        with patch.object(f,'transaction',self.tx),patch.object(f,'next_line',return_value='ချစ်တယ်'),patch.object(f,'cfg',return_value=''),patch.object(f,'stop_run') as stop,patch.object(f.time,'time',return_value=1001):f.run_worker(self.bot,run)
        self.assertEqual(self.bot.send_message.call_count,8)
        self.assertEqual(run['event'].wait.call_count,8)
        self.assertEqual(self.bot.send_message.call_args_list[0].kwargs['reply_parameters'].message_id,99)
        self.assertNotIn('reply_parameters',self.bot.send_message.call_args_list[1].kwargs)
        stop.assert_called_once()

    def test_stopped_worker_does_not_send(self):
        self.run['event'].set()
        with patch.object(f,'stop_run'):f.run_worker(self.bot,self.run)
        self.bot.send_message.assert_not_called()

    def test_delivery_failure_does_not_retry(self):
        self.bot.send_message.side_effect=TimeoutError('ambiguous')
        self.cur.fetchone.side_effect=[('active',),(False,)]
        with patch.object(f,'transaction',self.tx),patch.object(f,'next_line',return_value='hi'),patch.object(f,'cfg',return_value=''),patch.object(f,'stop_run'),patch.object(f.time,'time',return_value=1001):f.run_worker(self.bot,self.run)
        self.assertEqual(self.bot.send_message.call_count,1)

    def test_start_owner_only(self):
        with patch.object(f,'transaction',self.tx):self.handlers['start'](self.message(3))
        self.cur.execute.assert_not_called()

    def test_blocked_target_cannot_be_restarted(self):
        self.cur.fetchone.return_value=(True,0)
        self.bot.get_chat_member.return_value=NS(status='member',user=NS(is_bot=False))
        values={**f.DEFAULTS,'target_id':2}
        with patch.object(f,'transaction',self.tx),patch.object(f,'cfg',side_effect=lambda k,cid:values[k]):self.handlers['start'](self.message(1))
        self.assertFalse(any('INSERT INTO comfort_runs' in a.args[0] for a in self.cur.execute.call_args_list))


if __name__=='__main__':unittest.main()
