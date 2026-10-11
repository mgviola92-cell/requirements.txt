import unittest
from data.this_or_that_questions import get_question
from ui.this_or_that_card import round_card

class ThisOrThatCardTests(unittest.TestCase):
    def test_no_unrelated_image_used(self):
        self.assertIsNone(round_card(get_question(0),1,manifest={}))
