"""Tests for provider-specific metadata questions without network access."""
import unittest
from unittest.mock import patch
from core.metadata_quiz import field_quiz,OPENALEX_FIELDS,OPENLIBRARY_FIELDS,NASA_FIELDS
from core.fact_question_engine import openalex_question
from core.extra_question_sources import open_library_question,nasa_images_question

class MetadataQuestionTests(unittest.TestCase):
    def test_metadata_template_catalogue(self):
        self.assertGreaterEqual(len(OPENALEX_FIELDS),15)
        self.assertGreaterEqual(len(OPENLIBRARY_FIELDS),8)
        self.assertGreaterEqual(len(NASA_FIELDS),7)

    def test_nested_metadata_and_distractors(self):
        rows=[{"title":"Research study number "+str(i),
               "primary_topic":{"field":{"display_name":"Field "+str(i)}}}
              for i in range(9)]
        item=field_quiz(rows,[("primary_topic.field.display_name","Which field is '{title}'?")],
                        "title","test")
        self.assertIsNotNone(item)
        self.assertEqual(len(set(item["answers"])),4)

    def test_no_fabricated_missing_fields(self):
        rows=[{"title":"Research study number "+str(i)} for i in range(9)]
        self.assertIsNone(field_quiz(rows,[("missing","What is {title}?")],"title","test"))

    def test_openalex_with_mocked_batch(self):
        rows=[{"title":"Research article "+str(i)+" about a new topic",
               "publication_year":2020+i,"publication_date":str(2020+i)+"-01-01",
               "cited_by_count":300+i*10,"type":"article",
               "primary_topic":{"field":{"display_name":"Field "+str(i)}}}
              for i in range(12)]
        with patch("core.fact_question_engine._read",return_value={"results":rows}),patch("core.fact_question_engine.random.random",return_value=0):
            item=openalex_question()
        self.assertIsNotNone(item)
        self.assertEqual(len(item["answers"]),4)

    def test_openlibrary_with_mocked_batch(self):
        rows=[{"title":"Book of Knowledge "+str(i),
               "author_name":["Writer "+str(i)],
               "first_publish_year":1980+i,"edition_count":i+1}
              for i in range(12)]
        with patch("core.extra_question_sources._get",return_value={"docs":rows}),patch("core.extra_question_sources.random.random",return_value=0):
            item=open_library_question()
        self.assertIsNotNone(item)

    def test_nasa_with_mocked_batch(self):
        rows=[{"data":[{"title":"NASA image of planet "+str(i),
                        "date_created":str(2000+i)+"-01-01",
                        "center":"NASA Center "+str(i),
                        "nasa_id":"NASA-"+str(i)}]} for i in range(12)]
        with patch("core.extra_question_sources._get",return_value={"collection":{"items":rows}}),patch("core.extra_question_sources.random.random",return_value=0):
            item=nasa_images_question()
        self.assertIsNotNone(item)

if __name__=="__main__":
    unittest.main()
