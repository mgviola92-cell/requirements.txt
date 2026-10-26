"""Text-only transport, timer refreshes and speed-tap phase ordering."""
import ast,time,threading,random,html,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,Mock,patch
from ui import text_cards as cards
from core import customization as custom
from games import speed_tap as speed
from core.keyboards import speed_tap_keyboard

class TextCardTests(unittest.TestCase):
    def env(self,names):
        env=vars(cards).copy()
        env.update(vars(speed))
        env.update(bot=MagicMock(),time=time,random=random,threading=threading,html=html,
            _custom_text=custom.message_text,_custom_setting=custom.setting_value,
            speed_tap_keyboard=speed_tap_keyboard,speed_tap_visual_lock=threading.RLock(),speed_tap_visual_state={},
            schedule_task=Mock(),cancel_task=Mock(),delay_delete_message=Mock(),apply_custom_game_result=Mock(return_value=True))
        env.update(speed_pending_card=cards.speed_pending,speed_wait_card=cards.speed_wait,speed_go_card=cards.speed_go,speed_result_card=cards.speed_result,speed_timeout_card=cards.speed_timeout)
        nodes=[n for n in ast.parse(Path('bot.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
        for n in nodes:n.decorator_list=[]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'bot.py','exec'),env)
        return env

    def test_speed_phases_and_winner_use_only_text(self):
        cid=-90909
        env=self.env({'speed_tap_command','speed_tap_callback','get_speed_tap_visual_state','clear_speed_tap_visual_state'})
        try:
            self.assertTrue(env['speed_tap_command'](auto_chat_id=cid))
            env['schedule_task'].call_args.args[1]() # pending -> WAIT
            self.assertEqual(speed.get_speed_tap_game(cid)['state'],'waiting')
            bot=env['bot'];seen=[]
            bot.edit_message_text.side_effect=lambda *a,**kw:seen.append(speed.get_speed_tap_game(cid)['state'])
            env['schedule_task'].call_args.args[1]() # WAIT -> GO, then activation
            self.assertEqual(seen,['waiting'])
            self.assertEqual(speed.get_speed_tap_game(cid)['state'],'active')
            call=NS(id='q',data=f'speedtap:{cid}:tap',from_user=NS(id=42,first_name='A <B>',username=None),message=NS(chat=NS(id=cid),message_id=bot.send_message.return_value.message_id))
            env['speed_tap_callback'](call)
            env['apply_custom_game_result'].assert_called_once()
            self.assertIn('A <B>',bot.edit_message_text.call_args.args[0])
            self.assertIsNone(speed.get_speed_tap_game(cid))
            bot.send_photo.assert_not_called();bot.edit_message_media.assert_not_called()
        finally:speed.end_speed_tap_game(cid)

    def test_failed_go_edit_never_activates_round(self):
        cid=-90910;env=self.env({'speed_tap_command','get_speed_tap_visual_state','clear_speed_tap_visual_state'})
        try:
            env['speed_tap_command'](auto_chat_id=cid);env['schedule_task'].call_args.args[1]()
            env['bot'].edit_message_text.side_effect=RuntimeError('offline')
            env['schedule_task'].call_args.args[1]()
            self.assertIsNone(speed.get_speed_tap_game(cid))
        finally:speed.end_speed_tap_game(cid)

    def test_countdown_preserves_math_question_and_word(self):
        now=time.monotonic();g={'id':'g','round':0,'scores':{1:10},'names':{1:'မြန်မာ <name>'},'question':{'question':'7 + 8 = ?'},'deadline':now+30}
        env=self.env({'math_battle_tick','word_chain_tick'})
        env.update(math_battle_card_lock=threading.RLock(),get_math_battle=lambda cid:dict(g,message_id=9),math_round_card=cards.math_round,math_battle_keyboard=lambda g:None)
        env['math_battle_tick'](-1,'g',0,9)
        self.assertIn('7 + 8 = ?',env['bot'].edit_message_text.call_args.kwargs['text'])
        w=dict(g,word='apple',required='e',moves=1,mode='en',idle_deadline=now+25,message_id=9)
        env.update(word_chain_card_lock=threading.RLock(),get_word_chain_game=lambda cid:w,word_chain_status_card=cards.word_status,WORD_CHAIN_TICK_PREFIX='wc:')
        env['word_chain_tick'](-1,'g',1,9)
        self.assertIn('apple',env['bot'].edit_message_text.call_args.kwargs['text'])
        self.assertIn('e',env['bot'].edit_message_text.call_args.kwargs['text'])

    def test_profile_and_leaderboard_keep_stats_and_literal_names(self):
        value=cards.profile('မောင် <test>',200,3,5,1,1)
        self.assertIn('မောင် <test>',value);self.assertIn('LEGEND',value);self.assertIn('200',value)
        bot=MagicMock();cards.send_card(bot,-1,value,caption='old title')
        self.assertEqual(bot.send_message.call_args.args[1],value)
        self.assertIsNone(bot.send_message.call_args.kwargs['parse_mode'])
        board=cards.leaderboard([dict(name='လှ',points=20,wins=1,games=2)])
        self.assertIn('လှ',board);self.assertIn('20',board)

    def test_retired_games_absent_from_controls_and_command_catalog(self):
        from features import owner_operations as ops,command_help
        removed={'boss_raid','team_battle','pair_challenge'}
        self.assertFalse(removed.intersection(ops.GAME_LABELS))
        aliases={a for e in command_help.REFERENCE['entries'] for a in e['aliases']}
        self.assertFalse({'boss','bossraid','raid','teambattle','pair'}.intersection(aliases))
        self.assertFalse(any(any(x in k for x in removed) for k in custom.CATALOG))

