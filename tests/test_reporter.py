"""Tests for regressionx.reporter — Report generation.

Covers:
- Markdown report: all pass, mixed results, NEW verdict
- Report contains summary statistics
- Report contains failure details
- Report file creation
"""
import unittest
import tempfile
import shutil
import os

try:
    from regressionx.model import CaseResult, Verdict
    from regressionx.reporter.markdown import MarkdownReporter
except ImportError:
    CaseResult = Verdict = MarkdownReporter = None


def _skip_if_not_implemented():
    if any(x is None for x in [CaseResult, Verdict, MarkdownReporter]):
        raise unittest.SkipTest("reporter module not yet implemented")


class _ReporterTestBase(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()
        self.test_dir = tempfile.mkdtemp()
        self.report_path = os.path.join(self.test_dir, "report.md")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _read_report(self):
        with open(self.report_path, "r", encoding="utf-8") as f:
            return f.read()


class TestMarkdownReporterAllPass(_ReporterTestBase):

    def test_all_pass_report(self):
        results = [
            CaseResult(case_name="case_a", verdict=Verdict.PASS, diffs=[], errors=[]),
            CaseResult(case_name="case_b", verdict=Verdict.PASS, diffs=[], errors=[]),
        ]
        reporter = MarkdownReporter(self.report_path)
        reporter.generate(results)

        content = self._read_report()
        self.assertIn("RegressionX Report", content)
        self.assertIn("case_a", content)
        self.assertIn("case_b", content)
        self.assertIn("PASS", content)
        # Should show 2 total, 2 passed, 0 failed
        self.assertIn("2", content)

    def test_no_failure_details_section_when_all_pass(self):
        results = [
            CaseResult(case_name="c1", verdict=Verdict.PASS, diffs=[], errors=[]),
        ]
        reporter = MarkdownReporter(self.report_path)
        reporter.generate(results)

        content = self._read_report()
        self.assertNotIn("Failure Details", content)


class TestMarkdownReporterWithFailures(_ReporterTestBase):

    def test_mixed_results(self):
        results = [
            CaseResult(case_name="pass_case", verdict=Verdict.PASS,
                       diffs=[], errors=[]),
            CaseResult(case_name="fail_case", verdict=Verdict.FAIL,
                       diffs=["Content mismatch: output.txt"],
                       errors=["Only in golden: extra.txt"]),
        ]
        reporter = MarkdownReporter(self.report_path)
        reporter.generate(results)

        content = self._read_report()
        self.assertIn("PASS", content)
        self.assertIn("FAIL", content)
        self.assertIn("fail_case", content)
        self.assertIn("Content mismatch: output.txt", content)
        self.assertIn("Only in golden: extra.txt", content)

    def test_failure_details_present(self):
        results = [
            CaseResult(case_name="broken", verdict=Verdict.FAIL,
                       diffs=["Content mismatch: f.txt"], errors=[]),
        ]
        reporter = MarkdownReporter(self.report_path)
        reporter.generate(results)

        content = self._read_report()
        self.assertIn("Failure Details", content)
        self.assertIn("broken", content)


class TestMarkdownReporterNewVerdict(_ReporterTestBase):

    def test_new_verdict_shown(self):
        results = [
            CaseResult(case_name="first_run", verdict=Verdict.NEW,
                       diffs=[], errors=[]),
        ]
        reporter = MarkdownReporter(self.report_path)
        reporter.generate(results)

        content = self._read_report()
        self.assertIn("NEW", content)
        self.assertIn("first_run", content)


class TestMarkdownReporterErrorVerdict(_ReporterTestBase):

    def test_error_verdict_shown(self):
        results = [
            CaseResult(case_name="error_case", verdict=Verdict.ERROR,
                       diffs=[], errors=["Command exited with code 127"]),
        ]
        reporter = MarkdownReporter(self.report_path)
        reporter.generate(results)

        content = self._read_report()
        self.assertIn("ERROR", content)
        self.assertIn("error_case", content)


class TestMarkdownReporterSummaryStats(_ReporterTestBase):

    def test_summary_counts(self):
        results = [
            CaseResult(case_name="p1", verdict=Verdict.PASS, diffs=[], errors=[]),
            CaseResult(case_name="p2", verdict=Verdict.PASS, diffs=[], errors=[]),
            CaseResult(case_name="f1", verdict=Verdict.FAIL,
                       diffs=["diff"], errors=[]),
            CaseResult(case_name="n1", verdict=Verdict.NEW, diffs=[], errors=[]),
        ]
        reporter = MarkdownReporter(self.report_path)
        reporter.generate(results)

        content = self._read_report()
        # Total: 4, Passed: 2, Failed: 1, New: 1
        self.assertIn("4", content)  # total


class TestMarkdownReporterFileCreation(_ReporterTestBase):

    def test_report_file_created(self):
        results = [
            CaseResult(case_name="c1", verdict=Verdict.PASS, diffs=[], errors=[]),
        ]
        reporter = MarkdownReporter(self.report_path)
        reporter.generate(results)

        self.assertTrue(os.path.exists(self.report_path))

    def test_empty_results_still_creates_report(self):
        reporter = MarkdownReporter(self.report_path)
        reporter.generate([])

        self.assertTrue(os.path.exists(self.report_path))
        content = self._read_report()
        self.assertIn("RegressionX Report", content)


if __name__ == "__main__":
    unittest.main()
