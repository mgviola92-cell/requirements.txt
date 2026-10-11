import ast
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
from features.activity_spawn import ActivitySpawner


class MinimumRng:
    def randint(self,a,b):return a
    def random(self):return 0


class ActivitySpawnTests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.spawn=Mock(return_value=True)
        self.allowed=Mock(return_value=True)
        self.engine=ActivitySpawner(self.spawn,threshold=(3,3),chance=.75,quiet=(10,10),
            can_spawn=self.allowed,clock=lambda:self.now,rng=MinimumRng())

    def message(self,cid=1,uid=None):
        self.now+=3
        return self.engine.record(cid,uid if uid is not None else int(self.now)%2)

    def test_threshold_triggers_once(self):
        for _ in range(3):self.message()
        self.spawn.assert_called_once_with(1)

    def test_groups_do_not_share_activity(self):
        self.message(1);self.message(1);self.message(2)
        self.spawn.assert_not_called()
        self.message(1)
        self.spawn.assert_called_once_with(1)

    def test_one_user_flood_does_not_trigger(self):
        for _ in range(20):self.message(uid=5)
        self.spawn.assert_not_called()

    def test_repeated_messages_in_three_seconds_do_not_count(self):
        for _ in range(20):self.engine.record(1,5)
        self.assertEqual(len(self.engine.groups[1]['events']),1)

    def test_blocked_game_keeps_activity_and_retries(self):
        self.allowed.return_value=False
        for _ in range(3):self.message()
        self.spawn.assert_not_called()
        self.allowed.return_value=True
        for _ in range(3):self.message()
        self.spawn.assert_called_once_with(1)

    def test_failed_spawn_is_not_recorded_as_success(self):
        self.spawn.return_value=False
        for _ in range(6):self.message()
        self.assertEqual(self.spawn.call_count,2)
        self.assertEqual(self.engine.groups[1]['quiet_until'],0)

    def test_random_miss_retries_after_few_messages(self):
        self.engine.rng.random=lambda:1
        for _ in range(3):self.message()
        self.spawn.assert_not_called()
        self.engine.rng.random=lambda:0
        for _ in range(3):self.message()
        self.spawn.assert_called_once()

    def test_quiet_requires_fresh_activity(self):
        for _ in range(3):self.message()
        for _ in range(3):self.message()
        self.assertEqual(self.spawn.call_count,1)
        for _ in range(3):self.message()
        self.assertEqual(self.spawn.call_count,2)

    def test_expired_blocked_activity_does_not_raise_threshold_forever(self):
        self.allowed.return_value=False
        for _ in range(30):self.message()
        self.now+=601
        self.allowed.return_value=True
        for _ in range(3):self.message()
        self.spawn.assert_called_once()

    def test_inflight_check_cannot_start_second_spawn(self):
        def spawn(cid):
            self.engine.record(cid,99)
            return True
        self.spawn.side_effect=spawn
        for _ in range(3):self.message()
        self.spawn.assert_called_once()

    def test_auto_boss_reuses_live_card_and_timer_without_deleting_chat_message(self):
        tree=ast.parse(Path('bot.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='spawn_boss_raid')
        raid={'id':'r','boss':{'name':'Boss'}}
        env={name:Mock() for name in ['can_start_session','start_boss_raid','start_session',
            'get_boss_artwork','get_boss_visual_stage','generate_boss_live_card','boss_raid_text',
            'boss_attack_keyboard','set_boss_raid_message_id','safe_pin_message','delay_delete_message',
            'schedule_task','finish_boss_raid','end_session']}
        env.update(BOSS_RAID_DURATION=180,boss_raid_visual_state={},boss_raid_timeout=Mock(),bot=Mock())
        env['can_start_session'].return_value=(True,None)
        env['start_boss_raid'].return_value=(True,raid)
        env['start_session'].return_value=(True,None)
        env['generate_boss_live_card'].return_value=('image','variant','composition')
        env['bot'].send_photo.return_value=NS(message_id=12)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'bot.py','exec'),env)
        self.assertTrue(env['spawn_boss_raid'](-100))
        env['bot'].send_photo.assert_called_once()
        env['delay_delete_message'].assert_not_called()
        self.assertEqual(env['schedule_task'].call_args.kwargs['task_id'],'boss_timeout:-100')

    def test_raid_tracker_is_before_consuming_game_handlers(self):
        text=Path('bot.py').read_text()
        self.assertLess(text.index('def boss_activity_middleware'),text.index('def ban_word_filter'))
        self.assertLess(text.index('def boss_activity_middleware'),text.index('def boss_raid_command'))


if __name__=='__main__':unittest.main()
