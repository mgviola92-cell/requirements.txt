"""Offline tests for Would You Rather's scenario bank and vote rendering."""
import unittest
from unittest.mock import patch, MagicMock
from features.would_you_rather import PAIRS, CAPACITY, generate_by_index, generate
from data.wyr_expansion import TOTAL, OPTIONS, choices_at


class WouldYouRatherTests(unittest.TestCase):
    def test_distinct_myanmar_question_pairs(self):
        self.assertGreaterEqual(CAPACITY, 20000)
        self.assertEqual(TOTAL, 25560)
        self.assertEqual(CAPACITY, 84 + TOTAL)
        self.assertGreaterEqual(len(PAIRS), 75)

    def test_all_combinations_unique_and_valid(self):
        choices = set()
        for ix in range(CAPACITY):
            item = generate_by_index(ix)
            self.assertEqual(len(item["options"]),2)
            self.assertLessEqual(len(item["question"]),300)
            self.assertTrue(all(len(option)<=100 for option in item["options"]))
            self.assertTrue(any(0x1000 <= ord(c) <= 0x109F for c in item["question"]))
            self.assertNotEqual(*item["options"])
            self.assertNotIn(item["options"][0],item["question"])
            self.assertNotIn(item["options"][1],item["question"])
            self.assertTrue(item["question"].startswith("🎲 Would You Rather?"))
            self.assertEqual(item["id"], ("WYR-MM-"+str(ix)) if ix < 84 else ("WYR-CAT-"+str(ix-84)))
            self.assertNotIn(item["options"], choices)
            choices.add(item["options"])
        self.assertEqual(len(choices), CAPACITY)

    def test_all_categories_have_72_meaningful_choices(self):
        self.assertEqual(len(OPTIONS), 10)
        for options in OPTIONS:
            self.assertEqual(len(options), 72)
            self.assertEqual(len(set(options)),72)
            self.assertTrue(all(len(opt) <= 100 for opt in options))

    def test_invalid_indices(self):
        with self.assertRaises(ValueError): generate_by_index(-1)
        with self.assertRaises(ValueError): generate_by_index(CAPACITY)

    def test_generator_outputs_valid_result(self):
        for _ in range(300):
            q=generate()
            self.assertEqual(len(q["options"]),2)
            self.assertIn("?",q["question"])


if __name__ == "__main__":
    unittest.main()
