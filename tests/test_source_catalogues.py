"""Offline provider catalogue checks. Run: python -m unittest discover -s tests."""
import unittest
from unittest.mock import patch

from core.world_bank_indicators import METRICS
from core.wikidata_more_topics import MORE_TOPICS
from core.fact_question_engine import TOPICS
from core.wikipedia_questions import CATEGORIES, wikipedia_question
from core.extra_question_sources import world_bank_question


class SourceCatalogueTests(unittest.TestCase):
    def test_wikidata_fifty_distinct_rules(self):
        rules=TOPICS+MORE_TOPICS
        self.assertGreaterEqual(len(rules),50)
        self.assertEqual(len({name for name,*_ in rules}),len(rules))

    def test_world_bank_fifty_distinct_indicators(self):
        self.assertGreaterEqual(len(METRICS),50)
        for code,(name,unit) in METRICS.items():
            self.assertTrue(code and name and unit)

    def test_wikipedia_topic_pools(self):
        self.assertGreaterEqual(len(CATEGORIES),50)
        self.assertEqual(len(set(CATEGORIES)),len(CATEGORIES))

    def test_wikipedia_question_from_mocked_memberships(self):
        def members(category):
            return [category+" example"]
        with patch("core.wikipedia_questions._members",side_effect=members):
            result=wikipedia_question()
        self.assertIsNotNone(result)
        self.assertEqual(len(result["answers"]),4)
        self.assertEqual(len(set(result["answers"])),4)

    def test_world_bank_question_from_mocked_api(self):
        rows=[
            {"country":{"id":"C"+str(i),"value":"Country "+str(i)},"countryiso3code":"AAA",
             "value":1000000+i*100000}
            for i in range(8)]
        countries=[{"id":"C"+str(i),"region":{"id":"EAS"}} for i in range(8)]
        def response(url):
            return [{},countries] if "/v2/country?" in url else [{},rows]
        with patch("core.extra_question_sources._get",side_effect=response):
            result=world_bank_question()
        self.assertIsNotNone(result)
        self.assertEqual(len(set(result["answers"])),4)


if __name__=="__main__":
    unittest.main()
