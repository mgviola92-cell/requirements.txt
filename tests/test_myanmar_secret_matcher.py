import unittest
from core.myanmar_secret_matcher import normalize_secret,matches_secret
from data.imposter_words import WORDS

class MyanmarSecretTests(unittest.TestCase):
    def test_exact_and_unicode_order(self):
        self.assertTrue(matches_secret("မုန့်ဟင်းခါး","မုန့်ဟင်းခါး"))
        self.assertTrue(matches_secret("မုန့်ဟင်းခါး","မုန့်ဟင်းခါး"))
        self.assertTrue(matches_secret("  မုန့်ဟင်းခါး  ","မုန့်ဟင်းခါး"))
        self.assertTrue(matches_secret("မုန့်\u200bဟင်းခါး","မုန့်ဟင်းခါး"))
    def test_different_words_rejected(self):
        self.assertFalse(matches_secret("စင်","ဆင်"))
        self.assertFalse(matches_secret("ကျောင်းအိတ်","ကျောင်းလွယ်အိတ်"))
        self.assertFalse(matches_secret("မုန့်ဟင်းခါ","မုန့်ဟင်းခါး"))
        self.assertFalse(matches_secret("","ဆင်"))
    def test_expanded_word_bank(self):
        self.assertGreaterEqual(len(WORDS),900)
        self.assertEqual(len(WORDS),len(set(WORDS)))
        self.assertTrue(all(w.strip() for w in WORDS))
