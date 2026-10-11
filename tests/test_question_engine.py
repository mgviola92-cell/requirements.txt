"""Offline question engine checks: python -m unittest tests.test_question_engine"""
import unittest
from unittest.mock import patch

from core.procedural_questions import KINDS, generate
from core.question_quality import make_mcq, validate_question


class QuestionEngineTests(unittest.TestCase):
    def test_fifty_distinct_procedural_templates(self):
        self.assertGreaterEqual(len(KINDS), 50)
        self.assertEqual(len(KINDS), len(set(KINDS)))

    def test_every_procedural_template_produces_valid_two_choice_question(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                with patch("core.procedural_questions.random.choice", side_effect=lambda values: kind if values is KINDS else values[0]):
                    item = generate(level=3, mode="versus")
                self.assertTrue(item["question"])
                self.assertIn("?", item["question"])
                self.assertEqual(len(item["options"]), 2)
                self.assertNotEqual(item["options"][0], item["options"][1])
                self.assertIn(item["answer"], ("a", "b"))

    def test_all_difficulty_levels(self):
        for level in range(1, 7):
            for _ in range(20):
                item = generate(level=level)
                self.assertEqual(item["difficulty"], level)

    def test_invalid_mcq_is_rejected(self):
        self.assertIsNone(validate_question({"question":"Which one is correct?",
                                               "answers":["A","A","B","C"],"correct_index":0}))
        self.assertIsNone(make_mcq("Choose the answer", "yes", ["yes","no"], "test"))

    def test_mcq_correct_index_matches_correct_answer(self):
        item = make_mcq("Which number is prime?", "7", ["4","6","8","9"], "test")
        self.assertIsNotNone(item)
        self.assertEqual(item["answers"][item["correct_index"]], "7")


if __name__ == "__main__":
    unittest.main()
