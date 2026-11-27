import unittest

from benchmark import baseline, evaluate, read_data


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.manual, self.cases = read_data()
        self.sections = {section["id"] for section in self.manual}

    def test_gold_labels_match_manual_and_pass(self):
        for case in self.cases:
            if case["answer"] is not None:
                values = {fact["value"] for section in self.manual
                          if section["id"] in case["citations"] for fact in section["facts"]}
                self.assertIn(case["answer"], values)
        rows = [{key: case[key] for key in ("id", "answer", "citations")} for case in self.cases]
        result = evaluate(self.cases, rows, self.sections)["metrics"]
        self.assertEqual(result["strict_pass"], {"passed": 40, "total": 40})
        self.assertEqual(result["abstention"]["total"], 8)

    def test_alias_and_wrong_citation_are_scored_independently(self):
        case = self.cases[0]
        rows = [{"id": case["id"], "answer": " 1 minute. ", "citations": ["mounting"]}]
        detail = evaluate([case], rows, self.sections)["details"][0]
        self.assertTrue(detail["answer_correct"])
        self.assertFalse(detail["citations_match"])

    def test_incomplete_submission_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing predictions"):
            evaluate(self.cases, [], self.sections)

    def test_enhanced_baseline_abstains_on_some_unsupported_questions(self):
        rows = baseline(self.manual, self.cases, enhanced=True)
        result = evaluate(self.cases, rows, self.sections)["metrics"]
        self.assertGreater(result["abstention"]["passed"], 0)
