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

    def test_large_sample_has_valid_answers_and_distinct_questions(self):
        """2,000 deterministic independent generations across five levels."""
        for level, kinds in TEMPLATES.items():
            level_seen = set()
            for kind in kinds:
                kind_seen = set()
                for seed in range(100):
                    q = generate(level, rng=random.Random(seed + 10000 * level), kind=kind)
                    self.assertEqual(type(q["answer"]), int)
                    self.assertIn("?", q["question"])
                    self.assertEqual(q["id"], "ADV-" + __import__("hashlib").sha256(
                        q["question"].encode("utf-8")).hexdigest()[:24])
                    kind_seen.add(q["id"])
                    level_seen.add(q["id"])
                # Some sequences repeat occasionally; enough distinct questions
                # must be available to avoid a small and repetitive pool.
                self.assertGreaterEqual(len(kind_seen), 40, (level, kind))
            self.assertGreaterEqual(len(level_seen), 160, level)

    def test_selected_answers_against_independent_calculation(self):
        """Cross-check algebra, fractions, geometry and probability."""
        import re
        for seed in range(100):
            rng = random.Random(seed)
            q = generate(3, rng=rng, kind="fraction_equation")
            m = re.fullmatch(r"Solve: x/(\\d+) \\+ (\\d+) = (-?\\d+); x = \\?", q["question"])
            self.assertIsNotNone(m)
            d, a, result = map(int, m.groups())
            self.assertEqual(q["answer"] // d + a, result)
            self.assertEqual(q["answer"] % d, 0)

            q = generate(4, rng=random.Random(seed), kind="simultaneous")
            m = re.fullmatch(r"If 2x \\+ y = (-?\\d+) and x - y = (-?\\d+), find x = \\?", q["question"])
            self.assertIsNotNone(m)
            total, diff = map(int, m.groups())
            self.assertEqual(3*q["answer"], total + diff)

            q = generate(4, rng=random.Random(seed), kind="probability")
            m = re.fullmatch(r"A bag has (\\d+) red and (\\d+) blue balls\\. With replacement, red then blue: numerator of probability over denominator (\\d+) = \\?", q["question"])
            self.assertIsNotNone(m)
            red, blue, denominator = map(int, m.groups())
            self.assertEqual(denominator, (red + blue)**2)
            self.assertEqual(q["answer"], red*blue)

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
