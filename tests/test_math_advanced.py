"""Offline structural and answer-integrity tests for Math Battle procedural questions."""
import random
import unittest
from unittest.mock import patch

from core.math_battle_procedural import TEMPLATES, generate
from games import math_battle


class MathAdvancedTests(unittest.TestCase):
    def test_all_twenty_templates_every_level(self):
        self.assertEqual(sum(map(len, TEMPLATES.values())), 20)
        for level, kinds in TEMPLATES.items():
            for kind in kinds:
                for seed in range(12):
                    with self.subTest(level=level, kind=kind, seed=seed):
                        q = generate(level, rng=random.Random(seed), kind=kind)
                        self.assertEqual(q["level"], level)
                        self.assertEqual(type(q["answer"]), int)
                        self.assertLessEqual(len(q["question"]), 180)
                        self.assertIn("?", q["question"])
                        self.assertTrue(q["id"].startswith("ADV-"))
                        self.assertEqual(q["source"], "math_advanced:" + kind)

    def test_question_id_is_stable_for_identical_question(self):
        a = generate(4, rng=random.Random(101))
        b = generate(4, rng=random.Random(101))
        self.assertEqual(a, b)

    def test_fixed_question_fallback_and_answer_index(self):
        fixed = [{"id": "M1-test", "question": "8 + 9", "answer": 17}]
        with patch.object(math_battle, "_pool", return_value=[fixed] * 5), \
             patch.object(math_battle, "get_used_question_ids", return_value=set()), \
             patch.object(math_battle, "get_recent_question_ids", return_value=[]), \
             patch.object(math_battle, "mark_question_used", return_value=True), \
             patch.object(math_battle.random, "random", return_value=0.99):
            q = math_battle._next_question(-123, 0)
        self.assertEqual(q["options"][q["correct_index"]], 17)
        self.assertEqual(len(set(q["options"])), 4)

    def test_advanced_question_answer_index(self):
        fixed = [{"id": "M1-test", "question": "8 + 9", "answer": 17}]
        with patch.object(math_battle, "_pool", return_value=[fixed] * 5), \
             patch.object(math_battle, "get_used_question_ids", return_value=set()), \
             patch.object(math_battle, "get_recent_question_ids", return_value=[]), \
             patch.object(math_battle, "mark_question_used", return_value=True), \
             patch.object(math_battle.random, "random", return_value=0.1):
            q = math_battle._next_question(-123, 2)
        self.assertEqual(q["options"][q["correct_index"]], q["answer"])
        self.assertEqual(len(set(q["options"])), 4)
        self.assertTrue(q["id"].startswith("ADV-"))


if __name__ == "__main__":
    unittest.main()
