import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from games import this_or_that as game
from data.this_or_that_questions import TOTAL_QUESTIONS

class ThisOrThatEngineTests(unittest.TestCase):
    def test_round_count(self):
        self.assertEqual(game.ROUNDS, 5)
        self.assertEqual(game.VOTE_SECONDS, (45, 90))
        self.assertEqual(TOTAL_QUESTIONS, 3312)

    def test_invalid_choices(self):
        self.assertFalse(game.vote(1, "not-a-match", 1, 1, -1))
        self.assertFalse(game.vote(1, "not-a-match", 1, 1, 2))

    def test_first_valid_vote_and_duplicate_protection(self):
        mid="test-match"
        future=datetime.now(timezone.utc)+timedelta(minutes=1)
        cursor=MagicMock()
        cursor.fetchone.side_effect=[(mid,1,future,"active"),(123,)]
        connection=MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value=cursor
        with patch.object(game,"get_db_connection",return_value=connection):
            self.assertTrue(game.vote(100,mid,1,123,0))
        self.assertEqual(cursor.execute.call_count,2)

    def test_closed_round_rejects_new_votes(self):
        past=datetime.now(timezone.utc)-timedelta(seconds=1)
        cursor=MagicMock()
        cursor.fetchone.return_value=("match",1,past,"active")
        connection=MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value=cursor
        with patch.object(game,"get_db_connection",return_value=connection):
            self.assertFalse(game.vote(100,"match",1,123,0))
        self.assertEqual(cursor.execute.call_count,1)
