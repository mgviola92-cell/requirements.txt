"""Offline smoke checks for the audit report writer and validator."""
import json
import tempfile
import unittest
from pathlib import Path

from tests.question_audit import build_report,inspect_procedural,save_report
from core.procedural_questions import KINDS

class QuestionAuditTests(unittest.TestCase):
    def test_all_procedural_types(self):
        rows=inspect_procedural(2)
        self.assertEqual(len(rows),len(KINDS)*2)
        self.assertTrue(all(row["valid"] for row in rows),[x for x in rows if not x["valid"]][:5])

    def test_report_json_and_markdown(self):
        rows=[{"source":"test","type":"a","valid":True,"question":"What is 2 + 2?",
               "answer":"4","seconds":0.01,"error":None}]
        report=build_report(rows,False)
        with tempfile.TemporaryDirectory() as folder:
            save_report(report,folder)
            parsed=json.loads((Path(folder)/"question_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed["summary"]["test"]["valid"],1)
            self.assertIn("Question Engine Audit",(Path(folder)/"question_audit.md").read_text(encoding="utf-8"))

if __name__=="__main__":
    unittest.main()
