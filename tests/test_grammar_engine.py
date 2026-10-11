import unittest
from core.grammar_engine import analyze, explain

class GrammarEngineTests(unittest.TestCase):
    def test_past_auxiliary(self):
        x=analyze("I didn't went to school.")
        self.assertEqual(x[0]["corrected"],"I didn't go to school.")
    def test_third_person_negative(self):
        x=analyze("She don't like sports.")
        self.assertEqual(x[0]["corrected"],"She doesn't like sports.")
    def test_does_base(self):
        x=analyze("He doesn't likes pizza.")
        self.assertEqual(x[0]["corrected"],"He doesn't like pizza.")
    def test_subject_verb(self):
        self.assertEqual(analyze("I is happy.")[0]["corrected"],"I am happy.")
        self.assertEqual(analyze("They is late.")[0]["corrected"],"They are late.")
    def test_informal_is_not_automatically_wrong(self):
        for text in ("I'm gonna go.", "idk lol", "Wanna play?", "That game is awesome!"):
            self.assertEqual(analyze(text),[])
    def test_punctuation_and_case(self):
        self.assertEqual(analyze("I didn't WENT!")[0]["corrected"],"I didn't GO!")
    def test_skip_url_and_commands(self):
        self.assertEqual(analyze("/grammar I is"),[])
        self.assertEqual(analyze("https://example.com I is"),[])
    def test_burmese_explanation(self):
        result=explain("I didn't went.")
        self.assertIn("Base Form",result)
        self.assertIn("didn't go",result)
    def test_no_false_certainty(self):
        self.assertIn("100%",explain("I'm doing well."))

    def test_past_question_uses_base_form(self):
        self.assertEqual(analyze("Did she went home?")[0]["corrected"],"Did she go home?")
    def test_modal_uses_base_form(self):
        self.assertEqual(analyze("I can went home.")[0]["corrected"],"I can go home.")
        self.assertEqual(analyze("She will ate rice.")[0]["corrected"],"She will eat rice.")
    def test_does_question_uses_base_form(self):
        self.assertEqual(analyze("Does he likes pizza?")[0]["corrected"],"Does he like pizza?")
    def test_multiple_independent_rules(self):
        result=explain("She don't likes pizza. I didn't went.")
        self.assertIn("She doesn't like pizza.",result)
        self.assertIn("I didn't go.",result)
    def test_valid_formal_and_informal(self):
        for sentence in ("Could she have gone?", "He doesn't like it.", "I can go.", "Wanna hang out?", "I wish I were there."):
            self.assertEqual(analyze(sentence),[])
