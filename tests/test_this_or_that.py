"""This or That static pool and asset-readiness tests."""
import unittest
from data.this_or_that_questions import CATEGORIES, TOTAL_QUESTIONS, get_question, validate_bank
from core.this_or_that_visuals import get_visuals, visual_coverage

class ThisOrThatBankTests(unittest.TestCase):
    def test_question_count_and_unique_ids(self):
        self.assertEqual(len(CATEGORIES),12)
        self.assertEqual(TOTAL_QUESTIONS,3312)
        self.assertEqual(validate_bank(),TOTAL_QUESTIONS)

    def test_options_are_category_matched(self):
        for i in range(TOTAL_QUESTIONS):
            q=get_question(i)
            self.assertIn(q["options"][0],CATEGORIES[q["category"]])
            self.assertIn(q["options"][1],CATEGORIES[q["category"]])
            self.assertNotEqual(*q["options"])
            self.assertEqual(len(q["visual_tags"]),2)
            self.assertTrue(q["visual_tags"][0].startswith(q["category"]+"/"))

    def test_no_unrelated_image_fallback(self):
        q=get_question(0)
        self.assertIsNone(get_visuals(q, {}))
        coverage=visual_coverage({})
        self.assertEqual(coverage, {"ready":0,"total":288,"missing":288})

    def test_invalid_indices(self):
        with self.assertRaises(ValueError):get_question(-1)
        with self.assertRaises(ValueError):get_question(TOTAL_QUESTIONS)
