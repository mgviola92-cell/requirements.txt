import unittest
from data.this_or_that_questions import get_question
from ui.this_or_that_card import round_card, illustrated_card, result_card

class ThisOrThatCardTests(unittest.TestCase):
    def test_no_unrelated_image_used(self):
        self.assertIsNone(round_card(get_question(0),1,manifest={}))

    def test_fallback_card_is_a_real_image(self):
        card=illustrated_card(get_question(0),1)
        self.assertIsNotNone(card)
        self.assertEqual(card.read(2),b"\xff\xd8")

    def test_result_image(self):
        card=result_card(3)
        self.assertEqual(card.read(2),b"\xff\xd8")
