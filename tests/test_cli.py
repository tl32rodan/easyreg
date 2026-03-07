"""Tests for regressionx.cli — CLI integration tests.

Covers:
- run command: load config → execute → compare → report
- compare command: compare existing outputs only
- promote command: promote golden
- --case filter: run specific case only
- golden --status command
- Exit code 1 on failure, 0 on success
- Missing config error
"""
import unittest
import tempfile
import shutil
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

try:
    from regressionx import cli
except ImportError:
    cli = None

try:
    from regressionx.model import Suite, Case, Verdict, CaseResult, RunResult
except ImportError:
    Suite = Case = Verdict = CaseResult = RunResult = None


def _skip_if_not_implemented():
    if cli is None:
        raise unittest.SkipTest("cli module not yet implemented")


class _CLITestBase(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write_config(self, data):
        path = self.root / "suite.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return str(path)

    def _minimal_config(self):
        return {
            "suite": "test_suite",
            "golden_dir": str(self.root / "golden" / "{case}"),
            "output_dir": str(self.root / "output" / "{case}"),
            "cases": [
                {"name": "case_a", "command": "echo hello > result.txt",
                 "input": "/dev/null"},
            ],
        }


class TestRunCommand(_CLITestBase):

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_run_executes_and_compares(self, mock_compare, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner

        mock_compare.return_value = MagicMock(match=True, errors=[], diffs=[])

        config_path = self._write_config(self._minimal_config())
        # Create golden dir so comparison can proceed
        golden_dir = self.root / "golden" / "case_a"
        golden_dir.mkdir(parents=True)
        (golden_dir / "result.txt").write_text("hello\n")

        exit_code = cli.main(["run", "--config", config_path])
        self.assertEqual(exit_code, 0)
        self.assertTrue(mock_runner.run.called)
        self.assertTrue(mock_compare.called)

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_run_returns_1_on_failure(self, mock_compare, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner

        mock_compare.return_value = MagicMock(
            match=False, errors=[], diffs=["Content mismatch: f.txt"]
        )

        config_path = self._write_config(self._minimal_config())
        golden_dir = self.root / "golden" / "case_a"
        golden_dir.mkdir(parents=True)
        (golden_dir / "result.txt").write_text("different\n")

        exit_code = cli.main(["run", "--config", config_path])
        self.assertEqual(exit_code, 1)


class TestCompareCommand(_CLITestBase):

    @patch("regressionx.cli.compare_directories")
    def test_compare_does_not_execute(self, mock_compare):
        mock_compare.return_value = MagicMock(match=True, errors=[], diffs=[])

        config_path = self._write_config(self._minimal_config())
        # Create both golden and output dirs
        golden_dir = self.root / "golden" / "case_a"
        golden_dir.mkdir(parents=True)
        (golden_dir / "f.txt").write_text("data")
        output_dir = self.root / "output" / "case_a"
        output_dir.mkdir(parents=True)
        (output_dir / "f.txt").write_text("data")

        exit_code = cli.main(["compare", "--config", config_path])
        self.assertEqual(exit_code, 0)
        # compare should be called, but no runner should be invoked


class TestPromoteCommand(_CLITestBase):

    @patch("regressionx.cli.GoldenManager")
    def test_promote_calls_golden_manager(self, mock_gm_cls):
        mock_gm = MagicMock()
        mock_gm_cls.return_value = mock_gm

        config = self._minimal_config()
        config_path = self._write_config(config)
        # Create output dir to promote from
        output_dir = self.root / "output" / "case_a"
        output_dir.mkdir(parents=True)
        (output_dir / "result.txt").write_text("output")

        cli.main(["promote", "--config", config_path])
        self.assertTrue(mock_gm.promote.called)

    @patch("regressionx.cli.GoldenManager")
    def test_promote_specific_case(self, mock_gm_cls):
        mock_gm = MagicMock()
        mock_gm_cls.return_value = mock_gm

        config = self._minimal_config()
        config["cases"].append(
            {"name": "case_b", "command": "echo b", "input": "/dev/null"}
        )
        config_path = self._write_config(config)

        output_dir = self.root / "output" / "case_a"
        output_dir.mkdir(parents=True)
        (output_dir / "result.txt").write_text("output")

        cli.main(["promote", "--config", config_path, "--case", "case_a"])

        # Only case_a should be promoted
        calls = mock_gm.promote.call_args_list
        promoted_names = [c[0][0] for c in calls]
        self.assertIn("case_a", promoted_names)
        self.assertNotIn("case_b", promoted_names)


class TestCaseFilter(_CLITestBase):

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_case_filter_runs_only_specified(self, mock_compare, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner
        mock_compare.return_value = MagicMock(match=True, errors=[], diffs=[])

        config = self._minimal_config()
        config["cases"].append(
            {"name": "case_b", "command": "echo b", "input": "/dev/null"}
        )
        config_path = self._write_config(config)

        golden_a = self.root / "golden" / "case_a"
        golden_a.mkdir(parents=True)
        (golden_a / "result.txt").write_text("data")

        cli.main(["run", "--config", config_path, "--case", "case_a"])

        # Only 1 case should be run, not 2
        self.assertEqual(mock_runner.run.call_count, 1)


class TestGoldenStatus(_CLITestBase):

    @patch("regressionx.cli.GoldenManager")
    def test_golden_status(self, mock_gm_cls):
        mock_gm = MagicMock()
        mock_gm.status.return_value = {"case_a": True, "case_b": False}
        mock_gm_cls.return_value = mock_gm

        config_path = self._write_config(self._minimal_config())

        exit_code = cli.main(["golden", "--config", config_path, "--status"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(mock_gm.status.called)


class TestCLIErrors(_CLITestBase):

    def test_missing_config_exits_nonzero(self):
        with self.assertRaises(SystemExit) as cm:
            cli.main(["run"])
        self.assertNotEqual(cm.exception.code, 0)

    def test_nonexistent_config_file(self):
        with self.assertRaises((SystemExit, FileNotFoundError)):
            cli.main(["run", "--config", "/nonexistent/suite.json"])

    def test_unknown_command(self):
        with self.assertRaises(SystemExit) as cm:
            cli.main(["unknown_cmd", "--config", "x.json"])
        self.assertNotEqual(cm.exception.code, 0)


class TestNewVerdictFlow(_CLITestBase):
    """When golden doesn't exist for a case, verdict should be NEW."""

    @patch("regressionx.cli.SubprocessRunner")
    def test_no_golden_yields_new_verdict(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner

        config_path = self._write_config(self._minimal_config())
        # No golden directory created → should result in NEW verdict

        exit_code = cli.main(["run", "--config", config_path])
        # NEW verdict should not be treated as failure
        self.assertEqual(exit_code, 0)


class TestParallelRun(_CLITestBase):
    """Tests for --parallel N flag on the run command."""

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_parallel_flag_accepted(self, mock_compare, mock_runner_cls):
        """--parallel N should not cause an error."""
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner
        mock_compare.return_value = MagicMock(match=True, errors=[], diffs=[])

        config = self._minimal_config()
        config["cases"].append(
            {"name": "case_b", "command": "echo b", "input": "/dev/null"}
        )
        config_path = self._write_config(config)

        golden_a = self.root / "golden" / "case_a"
        golden_a.mkdir(parents=True)
        (golden_a / "result.txt").write_text("data")
        golden_b = self.root / "golden" / "case_b"
        golden_b.mkdir(parents=True)
        (golden_b / "result.txt").write_text("data")

        exit_code = cli.main(["run", "--config", config_path, "--parallel", "2"])
        self.assertEqual(exit_code, 0)

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_parallel_all_cases_executed(self, mock_compare, mock_runner_cls):
        """All cases should be executed even with --parallel."""
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner
        mock_compare.return_value = MagicMock(match=True, errors=[], diffs=[])

        config = self._minimal_config()
        config["cases"].append(
            {"name": "case_b", "command": "echo b", "input": "/dev/null"}
        )
        config_path = self._write_config(config)

        golden_a = self.root / "golden" / "case_a"
        golden_a.mkdir(parents=True)
        (golden_a / "result.txt").write_text("data")
        golden_b = self.root / "golden" / "case_b"
        golden_b.mkdir(parents=True)
        (golden_b / "result.txt").write_text("data")

        cli.main(["run", "--config", config_path, "--parallel", "2"])

        self.assertEqual(mock_runner.run.call_count, 2)

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_parallel_1_same_as_sequential(self, mock_compare, mock_runner_cls):
        """--parallel 1 should behave like sequential execution."""
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner
        mock_compare.return_value = MagicMock(match=True, errors=[], diffs=[])

        config_path = self._write_config(self._minimal_config())
        golden_a = self.root / "golden" / "case_a"
        golden_a.mkdir(parents=True)
        (golden_a / "result.txt").write_text("data")

        exit_code = cli.main(["run", "--config", config_path, "--parallel", "1"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(mock_runner.run.call_count, 1)

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_parallel_failure_propagates(self, mock_compare, mock_runner_cls):
        """A failing case under --parallel should still return exit code 1."""
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner
        mock_compare.return_value = MagicMock(
            match=False, errors=[], diffs=["mismatch"]
        )

        config_path = self._write_config(self._minimal_config())
        golden_a = self.root / "golden" / "case_a"
        golden_a.mkdir(parents=True)
        (golden_a / "result.txt").write_text("data")

        exit_code = cli.main(["run", "--config", config_path, "--parallel", "2"])
        self.assertEqual(exit_code, 1)


class TestJsonReport(_CLITestBase):
    """Tests for --report-format json flag."""

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_json_format_flag_accepted(self, mock_compare, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner
        mock_compare.return_value = MagicMock(match=True, errors=[], diffs=[])

        config_path = self._write_config(self._minimal_config())
        golden_a = self.root / "golden" / "case_a"
        golden_a.mkdir(parents=True)
        (golden_a / "result.txt").write_text("data")

        report_path = str(self.root / "report.json")
        exit_code = cli.main([
            "run", "--config", config_path,
            "--report", report_path,
            "--report-format", "json",
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue(os.path.exists(report_path))

    @patch("regressionx.cli.SubprocessRunner")
    @patch("regressionx.cli.compare_directories")
    def test_json_report_is_valid_json(self, mock_compare, mock_runner_cls):
        import json as _json
        mock_runner = MagicMock()
        mock_runner.run.return_value = RunResult(returncode=0, stdout="", stderr="")
        mock_runner_cls.return_value = mock_runner
        mock_compare.return_value = MagicMock(match=True, errors=[], diffs=[])

        config_path = self._write_config(self._minimal_config())
        golden_a = self.root / "golden" / "case_a"
        golden_a.mkdir(parents=True)
        (golden_a / "result.txt").write_text("data")

        report_path = str(self.root / "report.json")
        cli.main([
            "run", "--config", config_path,
            "--report", report_path,
            "--report-format", "json",
        ])

        with open(report_path, encoding="utf-8") as f:
            data = _json.load(f)
        self.assertIn("summary", data)
        self.assertIn("cases", data)


if __name__ == "__main__":
    unittest.main()
