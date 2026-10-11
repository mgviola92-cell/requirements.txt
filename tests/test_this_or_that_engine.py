import unittest
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
