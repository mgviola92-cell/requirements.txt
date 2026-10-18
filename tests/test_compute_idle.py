"""Idle workers must avoid frequent database wakeups without delaying active games."""
import unittest
from unittest.mock import MagicMock,patch
from features import imposter

class ComputeIdleTests(unittest.TestCase):
    def check_wait(self,active,expected):
        con=MagicMock();con.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value=[]
        wake=MagicMock();wake.wait.side_effect=SystemExit
        with patch.object(imposter,'get_db_connection',return_value=con),patch.object(imposter,'WATCH_WAKE',wake),patch.object(imposter,'ACTIVE_CHATS',active):
            with self.assertRaises(SystemExit):imposter._watch(MagicMock())
        wake.wait.assert_called_once_with(expected)
    def test_idle_recovers_without_three_second_poll(self):self.check_wait(set(),600)
    def test_active_game_keeps_fast_tick(self):self.check_wait({-100},3)
    def test_successful_save_wakes_worker(self):
        with patch.object(imposter,'get_db_connection',return_value=MagicMock()),patch.object(imposter,'WATCH_WAKE') as wake:
            imposter._save(-100,{'phase':'join'})
        wake.set.assert_called_once()
    def test_failed_save_does_not_wake_worker(self):
        with patch.object(imposter,'get_db_connection',side_effect=RuntimeError),patch.object(imposter,'WATCH_WAKE') as wake:
            with self.assertRaises(RuntimeError):imposter._save(-100,{'phase':'join'})
        wake.set.assert_not_called()
