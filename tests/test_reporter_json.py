"""Tests for easyreg.reporter.json_reporter — JSON report generation.

Covers:
- Valid JSON output
- Summary statistics
- Per-case details (verdict, diffs, errors)
- Machine-readable format for CI integration
"""
import json
import os
import shutil
import tempfile
import unittest

try:
    from easyreg.model import CaseResult, RunResult, Verdict
    from easyreg.reporter.json_reporter import JsonReporter
except ImportError:
    CaseResult = RunResult = Verdict = JsonReporter = None


def _skip():
    if any(x is None for x in [CaseResult, Verdict, JsonReporter]):
        raise unittest.SkipTest("json_reporter not yet implemented")


class _Base(unittest.TestCase):
    def setUp(self):
        _skip()
        self.test_dir = tempfile.mkdtemp()
        self.report_path = os.path.join(self.test_dir, "report.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _load(self):
        with open(self.report_path, encoding="utf-8") as f:
            return json.load(f)


class TestJsonReporterStructure(_Base):

    def test_output_is_valid_json(self):
        reporter = JsonReporter(self.report_path)
        reporter.generate([])
        data = self._load()
        self.assertIsInstance(data, dict)

    def test_top_level_keys(self):
        reporter = JsonReporter(self.report_path)
        reporter.generate([])
        data = self._load()
        self.assertIn("summary", data)
        self.assertIn("cases", data)

    def test_summary_counts_all_pass(self):
        results = [
            CaseResult(case_name="c1", verdict=Verdict.PASS, diffs=[], errors=[]),
            CaseResult(case_name="c2", verdict=Verdict.PASS, diffs=[], errors=[]),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        data = self._load()
        summary = data["summary"]
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["new"], 0)
        self.assertEqual(summary["errors"], 0)

    def test_summary_counts_mixed(self):
        results = [
            CaseResult(case_name="p", verdict=Verdict.PASS, diffs=[], errors=[]),
            CaseResult(case_name="f", verdict=Verdict.FAIL,
                       diffs=["mismatch"], errors=[]),
            CaseResult(case_name="n", verdict=Verdict.NEW, diffs=[], errors=[]),
            CaseResult(case_name="e", verdict=Verdict.ERROR, diffs=[], errors=[]),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        summary = self._load()["summary"]
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["new"], 1)
        self.assertEqual(summary["errors"], 1)


class TestJsonReporterCases(_Base):

    def test_case_entry_has_required_fields(self):
        results = [
            CaseResult(case_name="c1", verdict=Verdict.PASS, diffs=[], errors=[]),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        case = self._load()["cases"][0]
        self.assertIn("name", case)
        self.assertIn("verdict", case)
        self.assertIn("diffs", case)
        self.assertIn("errors", case)

    def test_pass_case_entry(self):
        results = [
            CaseResult(case_name="ok", verdict=Verdict.PASS, diffs=[], errors=[]),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        case = self._load()["cases"][0]
        self.assertEqual(case["name"], "ok")
        self.assertEqual(case["verdict"], "PASS")
        self.assertEqual(case["diffs"], [])
        self.assertEqual(case["errors"], [])

    def test_fail_case_includes_details(self):
        results = [
            CaseResult(
                case_name="broken",
                verdict=Verdict.FAIL,
                diffs=["Content mismatch: output.txt"],
                errors=["Only in golden: extra.txt"],
            ),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        case = self._load()["cases"][0]
        self.assertEqual(case["verdict"], "FAIL")
        self.assertIn("Content mismatch: output.txt", case["diffs"])
        self.assertIn("Only in golden: extra.txt", case["errors"])

    def test_new_verdict_in_json(self):
        results = [
            CaseResult(case_name="fresh", verdict=Verdict.NEW, diffs=[], errors=[]),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        case = self._load()["cases"][0]
        self.assertEqual(case["verdict"], "NEW")

    def test_error_verdict_includes_returncode(self):
        run = RunResult(returncode=127, stdout="", stderr="not found")
        results = [
            CaseResult(
                case_name="bad",
                verdict=Verdict.ERROR,
                diffs=[],
                errors=[],
                run_result=run,
            ),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        case = self._load()["cases"][0]
        self.assertEqual(case["verdict"], "ERROR")
        self.assertEqual(case.get("returncode"), 127)

    def test_empty_results(self):
        reporter = JsonReporter(self.report_path)
        reporter.generate([])
        data = self._load()
        self.assertEqual(data["cases"], [])
        self.assertEqual(data["summary"]["total"], 0)


class TestJsonReporterCIIntegration(_Base):

    def test_overall_pass_field_true_when_all_pass(self):
        results = [
            CaseResult(case_name="c1", verdict=Verdict.PASS, diffs=[], errors=[]),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        data = self._load()
        self.assertTrue(data["summary"].get("passed_overall"))

    def test_overall_pass_field_false_when_any_fail(self):
        results = [
            CaseResult(case_name="c1", verdict=Verdict.PASS, diffs=[], errors=[]),
            CaseResult(case_name="c2", verdict=Verdict.FAIL,
                       diffs=["diff"], errors=[]),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        data = self._load()
        self.assertFalse(data["summary"].get("passed_overall"))

    def test_new_does_not_count_as_failure(self):
        results = [
            CaseResult(case_name="c1", verdict=Verdict.NEW, diffs=[], errors=[]),
        ]
        reporter = JsonReporter(self.report_path)
        reporter.generate(results)
        data = self._load()
        self.assertTrue(data["summary"].get("passed_overall"))


if __name__ == "__main__":
    unittest.main()
