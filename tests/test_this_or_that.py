import io,json,random,time,unittest
from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,patch
from PIL import Image
from data import this_or_that as data
from games import this_or_that as game
from features import this_or_that as feature
from core.sessions import can_start_session,start_session,end_session

class EngineTests(unittest.TestCase):
    def test_3160_distinct_pairs_and_photo_mapping(self):
        self.assertEqual(data.CAPACITY,3160)
        self.assertEqual(len(set(data.PAIRS)),3160)
        for i in range(data.CAPACITY):
            q=data.question(i);self.assertNotEqual(q['a']['id'],q['b']['id'])
        self.assertEqual([o['photo'] for o in data.OPTIONS[:24]],list(range(24)))

    def test_five_rounds_vote_once_deadline_and_cancel(self):
        s=game.new(-1,1,{})
        for r in range(5):
            game.open_round(s,r,100+r*100)
            game.vote(s,s['id'],s['round'],1,'a',s['deadline']-1)
            with self.assertRaises(ValueError):game.vote(s,s['id'],s['round'],1,'b',s['deadline']-1)
            with self.assertRaises(ValueError):game.vote(s,s['id'],s['round'],2,'a',s['deadline'])
            with self.assertRaises(ValueError):game.vote(s,'old',s['round'],2,'a',s['deadline']-1)
            game.close_round(s)
        self.assertEqual(s['phase'],'finished');self.assertEqual(len(s['results']),5)
        self.assertEqual(len(s['participants']),1)
        restored=json.loads(json.dumps(s));self.assertEqual(s,restored)
        game.cancel(s);self.assertEqual(s['phase'],'cancelled')

    def test_percentages_no_vote_and_ties(self):
        s=game.new(-1,1,{});self.assertEqual(game.counts(s),(0,0,0,0))
        s['votes']={'1':'a','2':'b'};self.assertEqual(game.counts(s),(1,1,50,50))


    def test_owner_option_text_and_auto_setting_validation(self):
        from core import customization as custom
        key='msg.data.this_or_that.option.0'
        with patch.object(custom,'refresh'),patch.dict(custom._values,{(0,key):'ကော်ဖီအသစ်'}):
            self.assertEqual(data.question(0)['a']['label'],'ကော်ဖီအသစ်')
        for key in ('cfg.tot_auto.threshold','cfg.tot_auto.quiet'):
            with self.assertRaises(ValueError):custom.validate(key,[100,200,300])

    def test_session_excludes_other_interactive_games(self):
        cid=-999312
        try:
            self.assertTrue(start_session(cid,'this_or_that')[0])
            self.assertFalse(can_start_session(cid,'math_battle')[0])
        finally:end_session(cid,'this_or_that')

class DeliveryTests(unittest.TestCase):
    def state(self):
        s=game.new(-1,1,{});game.open_round(s,0,time.time());s['card']=40;return s

    def test_text_card_sent_before_old_card_removed(self):
        bot=MagicMock();bot.send_photo.side_effect=RuntimeError('photo error');bot.send_message.return_value.message_id=41
        s=self.state();feature.publish(bot,s)
        bot.send_photo.assert_not_called()
        self.assertFalse(s['photo']);self.assertEqual(s['card'],41)
        bot.delete_message.assert_called_once_with(-1,40)
        self.assertIn('reply_markup',bot.send_message.call_args.kwargs)

    def test_total_send_failure_preserves_old_card(self):
        bot=MagicMock();bot.send_photo.side_effect=RuntimeError();bot.send_message.side_effect=RuntimeError()
        with self.assertRaises(RuntimeError):feature.publish(bot,self.state())
        bot.delete_message.assert_not_called()

    def test_keyboard_payloads_round_scoped_and_short(self):
        s=self.state()
        for confirm in (False,True):
            for row in feature.keyboard(s,confirm).keyboard:
                for button in row:self.assertLessEqual(len(button.callback_data.encode()),64)

    def test_old_round_callbacks_do_not_record_vote(self):
        bot=MagicMock();bot.message_handler.side_effect=lambda **kw:lambda fn:fn
        handlers=[];bot.callback_query_handler.side_effect=lambda **kw:lambda fn:handlers.append(fn) or fn
        with patch.object(feature,'get_db_connection',side_effect=RuntimeError('offline')):
            feature.register(bot)
        s=self.state();bot.get_chat_member.return_value=NS(status='member')
        @contextmanager
        def locked(cid):yield MagicMock(),s
        c=NS(id='x',data=f"tot:{s['id']}:0:a",message=NS(chat=NS(type='supergroup',id=-1),message_id=40),from_user=NS(id=1,is_bot=False))
        with patch.object(feature,'locked',locked):handlers[0](c)
        self.assertFalse(s['votes']);bot.answer_callback_query.assert_called_once()

    def test_participation_rewards_once_with_real_reason(self):
        class Cursor:
            def __init__(self):self.keys=set();self.rows=[];self.result=None
            def execute(self,sql,args):
                self.rows.append((sql,args))
                if sql.startswith('INSERT INTO this_that_rewards'):
                    fresh=args not in self.keys;self.keys.add(args);self.result=(args[1],) if fresh else None
            def fetchone(self):return self.result
        s=self.state();s['participants']={'1':True,'2':True};game.close_round(s)
        cur=Cursor();bot=MagicMock()
        with patch.object(feature,'end_session'):
            self.assertEqual(len(feature.finish(bot,cur,s)),2)
            self.assertEqual(feature.finish(bot,cur,s),[])
        updates=[x for x in cur.rows if x[0].startswith('INSERT INTO player_stats')]
        reasons=[x[1][-1] for x in cur.rows if x[0].startswith('INSERT INTO reward_transactions')]
        self.assertEqual(len(updates),2);self.assertTrue(all(x.startswith('this_or_that_participation:') for x in reasons))

if __name__=='__main__':unittest.main()
