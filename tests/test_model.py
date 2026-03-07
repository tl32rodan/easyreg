"""Tests for easyreg.model — Data models.

Covers: Suite, Case, DiffRule, RunResult, Verdict, CaseResult
"""
import unittest

try:
    from easyreg.model import (
        Suite, Case, DiffRule, RunResult, Verdict, CaseResult,
    )
except ImportError:
    Suite = Case = DiffRule = RunResult = Verdict = CaseResult = None


def _skip_if_not_implemented(cls):
    """Skip test if model classes are not yet implemented."""
    if cls is None:
        raise unittest.SkipTest("model module not yet implemented")


class TestDiffRule(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented(DiffRule)

    def test_ignore_line_rule(self):
        rule = DiffRule(type="ignore_line", pattern="^#.*timestamp.*")
        self.assertEqual(rule.type, "ignore_line")
        self.assertEqual(rule.pattern, "^#.*timestamp.*")

    def test_ignore_regex_rule_with_replace(self):
        rule = DiffRule(type="ignore_regex", pattern=r"PID=\d+", replace="PID=XXX")
        self.assertEqual(rule.replace, "PID=XXX")

    def test_ignore_file_rule(self):
        rule = DiffRule(type="ignore_file", pattern="*.log")
        self.assertEqual(rule.type, "ignore_file")

    def test_ignore_folder_rule(self):
        rule = DiffRule(type="ignore_folder", pattern="tmp/")
        self.assertEqual(rule.type, "ignore_folder")

    def test_invalid_rule_type_raises(self):
        with self.assertRaises((ValueError, TypeError)):
            DiffRule(type="nonexistent_type", pattern="x")


class TestCase(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented(Case)

    def test_minimal_case(self):
        case = Case(name="basic", command="echo hello", input="/data/in")
        self.assertEqual(case.name, "basic")
        self.assertEqual(case.command, "echo hello")
        self.assertEqual(case.input, "/data/in")

    def test_case_with_timeout(self):
        case = Case(name="slow", command="long_run.sh", input="/data/in", timeout=7200)
        self.assertEqual(case.timeout, 7200)

    def test_case_with_per_case_diff_rules(self):
        rules = [DiffRule(type="ignore_line", pattern="^DEBUG:")]
        case = Case(
            name="custom_rules",
            command="cmd",
            input="/data/in",
            diff_rules=rules,
        )
        self.assertEqual(len(case.diff_rules), 1)
        self.assertEqual(case.diff_rules[0].type, "ignore_line")

    def test_case_diff_rules_mode_default_append(self):
        case = Case(name="default_mode", command="cmd", input="/data/in")
        self.assertEqual(case.diff_rules_mode, "append")

    def test_case_diff_rules_mode_override(self):
        case = Case(
            name="override_mode",
            command="cmd",
            input="/data/in",
            diff_rules_mode="override",
        )
        self.assertEqual(case.diff_rules_mode, "override")

    def test_case_default_timeout_is_none_or_sensible(self):
        case = Case(name="no_timeout", command="cmd", input="/data/in")
        # No timeout means None (no limit)
        self.assertIsNone(case.timeout)


class TestSuite(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented(Suite)

    def test_suite_creation(self):
        suite = Suite(
            name="my_flow",
            golden_dir="/golden/{case}",
            output_dir="/runs/{run_id}/{case}",
            cases=[
                Case(name="c1", command="echo 1", input="/in/c1"),
                Case(name="c2", command="echo 2", input="/in/c2"),
            ],
        )
        self.assertEqual(suite.name, "my_flow")
        self.assertEqual(len(suite.cases), 2)

    def test_suite_with_global_diff_rules(self):
        rules = [DiffRule(type="ignore_file", pattern="*.log")]
        suite = Suite(
            name="with_rules",
            golden_dir="/golden/{case}",
            output_dir="/runs/{run_id}/{case}",
            cases=[],
            diff_rules=rules,
        )
        self.assertEqual(len(suite.diff_rules), 1)

    def test_suite_with_versions(self):
        suite = Suite(
            name="versioned",
            golden_dir="/golden/{case}",
            output_dir="/runs/{run_id}/{case}",
            cases=[],
            versions={
                "baseline": {"TOOL_ROOT": "/v1"},
                "candidate": {"TOOL_ROOT": "/v2"},
            },
        )
        self.assertIn("baseline", suite.versions)
        self.assertIn("candidate", suite.versions)

    def test_suite_with_global_env(self):
        suite = Suite(
            name="env_suite",
            golden_dir="/golden/{case}",
            output_dir="/runs/{run_id}/{case}",
            cases=[],
            env={"TOOL_ROOT": "/tools/v1"},
        )
        self.assertEqual(suite.env["TOOL_ROOT"], "/tools/v1")


class TestVerdict(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented(Verdict)

    def test_pass_verdict(self):
        self.assertEqual(Verdict.PASS.value, "PASS")

    def test_fail_verdict(self):
        self.assertEqual(Verdict.FAIL.value, "FAIL")

    def test_new_verdict(self):
        """NEW = no golden reference exists yet."""
        self.assertEqual(Verdict.NEW.value, "NEW")

    def test_error_verdict(self):
        """ERROR = command execution failed."""
        self.assertEqual(Verdict.ERROR.value, "ERROR")


class TestRunResult(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented(RunResult)

    def test_successful_run(self):
        result = RunResult(returncode=0, stdout="ok", stderr="")
        self.assertEqual(result.returncode, 0)

    def test_failed_run(self):
        result = RunResult(returncode=1, stdout="", stderr="error msg")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "error msg")


class TestCaseResult(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented(CaseResult)

    def test_pass_result(self):
        result = CaseResult(
            case_name="c1",
            verdict=Verdict.PASS,
            diffs=[],
            errors=[],
        )
        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(len(result.diffs), 0)

    def test_fail_result_with_details(self):
        result = CaseResult(
            case_name="c2",
            verdict=Verdict.FAIL,
            diffs=["Content mismatch: output.txt"],
            errors=["Only in golden: extra.txt"],
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(len(result.diffs), 1)
        self.assertEqual(len(result.errors), 1)

    def test_new_result(self):
        result = CaseResult(
            case_name="c3",
            verdict=Verdict.NEW,
            diffs=[],
            errors=[],
        )
        self.assertEqual(result.verdict, Verdict.NEW)

    def test_error_result_with_run_result(self):
        run = RunResult(returncode=127, stdout="", stderr="command not found")
        result = CaseResult(
            case_name="c4",
            verdict=Verdict.ERROR,
            diffs=[],
            errors=[],
            run_result=run,
        )
        self.assertEqual(result.verdict, Verdict.ERROR)
        self.assertEqual(result.run_result.returncode, 127)


if __name__ == "__main__":
    unittest.main()
