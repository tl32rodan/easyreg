"""Tests for easyreg.runner — Subprocess execution engine.

Covers:
- Execute command in sandbox directory
- Command creates output files
- Command failure (non-zero exit code)
- Timeout handling
- Environment variable injection
- RunnerBase interface compliance
"""
import unittest
import tempfile
import shutil
import os
from pathlib import Path

try:
    from easyreg.model import Case, RunResult
    from easyreg.runner.subprocess_runner import SubprocessRunner
except ImportError:
    Case = RunResult = SubprocessRunner = None


def _skip_if_not_implemented():
    if any(x is None for x in [Case, RunResult, SubprocessRunner]):
        raise unittest.SkipTest("runner module not yet implemented")


class _RunnerTestBase(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)
        self.output_dir = self.root / "output"
        self.output_dir.mkdir()
        self.runner = SubprocessRunner()

    def tearDown(self):
        shutil.rmtree(self.test_dir)


class TestSubprocessRunner(_RunnerTestBase):

    def test_execute_simple_command(self):
        case = Case(name="simple", command="echo hello", input="/dev/null")
        result = self.runner.run(case, self.output_dir)

        self.assertIsInstance(result, RunResult)
        self.assertEqual(result.returncode, 0)

    def test_command_creates_output_file(self):
        case = Case(
            name="creates_file",
            command="echo result > output.txt",
            input="/dev/null",
        )
        result = self.runner.run(case, self.output_dir)

        self.assertEqual(result.returncode, 0)
        output_file = self.output_dir / "output.txt"
        self.assertTrue(output_file.exists())
        self.assertEqual(output_file.read_text().strip(), "result")

    def test_command_runs_in_output_directory(self):
        """Working directory of command should be the output directory."""
        case = Case(
            name="cwd_check",
            command="pwd > cwd.txt",
            input="/dev/null",
        )
        result = self.runner.run(case, self.output_dir)

        self.assertEqual(result.returncode, 0)
        cwd_file = self.output_dir / "cwd.txt"
        recorded_cwd = cwd_file.read_text().strip()
        self.assertEqual(recorded_cwd, str(self.output_dir))

    def test_command_failure_nonzero_exit(self):
        case = Case(
            name="failing",
            command="exit 42",
            input="/dev/null",
        )
        result = self.runner.run(case, self.output_dir)

        self.assertEqual(result.returncode, 42)

    def test_command_stderr_captured(self):
        case = Case(
            name="stderr",
            command="echo error_msg >&2",
            input="/dev/null",
        )
        result = self.runner.run(case, self.output_dir)

        self.assertIn("error_msg", result.stderr)

    def test_command_stdout_captured(self):
        case = Case(
            name="stdout",
            command="echo hello_world",
            input="/dev/null",
        )
        result = self.runner.run(case, self.output_dir)

        self.assertIn("hello_world", result.stdout)


class TestRunnerWithEnv(_RunnerTestBase):

    def test_env_vars_injected(self):
        case = Case(
            name="env_test",
            command='echo $MY_VAR > env_out.txt',
            input="/dev/null",
        )
        env = {"MY_VAR": "injected_value"}
        result = self.runner.run(case, self.output_dir, env=env)

        self.assertEqual(result.returncode, 0)
        content = (self.output_dir / "env_out.txt").read_text().strip()
        self.assertEqual(content, "injected_value")

    def test_env_vars_merged_with_system(self):
        """Injected env vars should be merged with system env, not replace it."""
        case = Case(
            name="env_merge",
            command='echo $HOME > home.txt',
            input="/dev/null",
        )
        env = {"MY_CUSTOM": "val"}
        result = self.runner.run(case, self.output_dir, env=env)

        self.assertEqual(result.returncode, 0)
        # HOME should still be available
        home = (self.output_dir / "home.txt").read_text().strip()
        self.assertNotEqual(home, "")


class TestRunnerTimeout(_RunnerTestBase):

    def test_timeout_kills_long_running_command(self):
        case = Case(
            name="slow",
            command="sleep 60",
            input="/dev/null",
            timeout=1,  # 1 second timeout
        )
        result = self.runner.run(case, self.output_dir)

        # Should either have non-zero return code or a timeout indicator
        self.assertNotEqual(result.returncode, 0)


class TestRunnerCreatesOutputDir(_RunnerTestBase):

    def test_creates_output_dir_if_not_exists(self):
        new_output = self.root / "new_output" / "deep"
        case = Case(
            name="auto_mkdir",
            command="echo ok > result.txt",
            input="/dev/null",
        )
        result = self.runner.run(case, new_output)

        self.assertEqual(result.returncode, 0)
        self.assertTrue(new_output.exists())
        self.assertTrue((new_output / "result.txt").exists())


if __name__ == "__main__":
    unittest.main()
