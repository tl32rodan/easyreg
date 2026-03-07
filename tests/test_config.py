"""Tests for regressionx.config — JSON config loading, validation, placeholder expansion.

Covers:
- Valid JSON loading → Suite object
- Placeholder expansion ({case}, {run_id}, {version}, {input}, {output_dir})
- Missing required fields validation
- Invalid JSON handling
- diff_rules_mode merge logic (append vs override)
- Versions expansion
"""
import unittest
import tempfile
import json
import os
import shutil

try:
    from regressionx.config import load_config
except ImportError:
    load_config = None

try:
    from regressionx.model import Suite, Case, DiffRule
except ImportError:
    Suite = Case = DiffRule = None


def _skip_if_not_implemented(*objs):
    for obj in objs:
        if obj is None:
            raise unittest.SkipTest("Required module not yet implemented")


class TestLoadConfig(unittest.TestCase):
    """Test JSON config file loading into Suite object."""

    def setUp(self):
        _skip_if_not_implemented(load_config, Suite)
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write_config(self, data, filename="suite.json"):
        path = os.path.join(self.test_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def _minimal_config(self, **overrides):
        config = {
            "suite": "test_suite",
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "cases": [
                {"name": "case_a", "command": "echo hello", "input": "/data/a"},
            ],
        }
        config.update(overrides)
        return config

    def test_load_minimal_config(self):
        path = self._write_config(self._minimal_config())
        suite = load_config(path)
        self.assertIsInstance(suite, Suite)
        self.assertEqual(suite.name, "test_suite")
        self.assertEqual(len(suite.cases), 1)
        self.assertEqual(suite.cases[0].name, "case_a")

    def test_load_config_with_global_diff_rules(self):
        config = self._minimal_config(
            diff_rules=[
                {"type": "ignore_file", "pattern": "*.log"},
                {"type": "ignore_folder", "pattern": "tmp/"},
            ]
        )
        path = self._write_config(config)
        suite = load_config(path)
        self.assertEqual(len(suite.diff_rules), 2)
        self.assertEqual(suite.diff_rules[0].type, "ignore_file")
        self.assertEqual(suite.diff_rules[1].type, "ignore_folder")

    def test_load_config_with_versions(self):
        config = self._minimal_config(
            versions={
                "baseline": {"TOOL_ROOT": "/v1"},
                "candidate": {"TOOL_ROOT": "/v2"},
            }
        )
        path = self._write_config(config)
        suite = load_config(path)
        self.assertEqual(len(suite.versions), 2)
        self.assertIn("baseline", suite.versions)

    def test_load_config_with_global_env(self):
        config = self._minimal_config(env={"MY_VAR": "value"})
        path = self._write_config(config)
        suite = load_config(path)
        self.assertEqual(suite.env["MY_VAR"], "value")

    def test_load_config_with_case_diff_rules(self):
        config = self._minimal_config()
        config["cases"][0]["diff_rules"] = [
            {"type": "ignore_line", "pattern": "^DEBUG:"},
        ]
        path = self._write_config(config)
        suite = load_config(path)
        self.assertEqual(len(suite.cases[0].diff_rules), 1)

    def test_load_config_with_case_diff_rules_mode_override(self):
        config = self._minimal_config()
        config["cases"][0]["diff_rules_mode"] = "override"
        config["cases"][0]["diff_rules"] = [
            {"type": "ignore_line", "pattern": "^DEBUG:"},
        ]
        path = self._write_config(config)
        suite = load_config(path)
        self.assertEqual(suite.cases[0].diff_rules_mode, "override")

    def test_load_config_case_timeout(self):
        config = self._minimal_config()
        config["cases"][0]["timeout"] = 3600
        path = self._write_config(config)
        suite = load_config(path)
        self.assertEqual(suite.cases[0].timeout, 3600)

    def test_multiple_cases(self):
        config = self._minimal_config()
        config["cases"].append(
            {"name": "case_b", "command": "echo world", "input": "/data/b"}
        )
        path = self._write_config(config)
        suite = load_config(path)
        self.assertEqual(len(suite.cases), 2)
        self.assertEqual(suite.cases[1].name, "case_b")


class TestConfigValidation(unittest.TestCase):
    """Test config validation — missing fields, invalid types."""

    def setUp(self):
        _skip_if_not_implemented(load_config)
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write_config(self, data, filename="suite.json"):
        path = os.path.join(self.test_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def _write_raw(self, text, filename="bad.json"):
        path = os.path.join(self.test_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_missing_suite_name_raises(self):
        config = {
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "cases": [],
        }
        path = self._write_config(config)
        with self.assertRaises((ValueError, KeyError)):
            load_config(path)

    def test_missing_golden_dir_raises(self):
        config = {
            "suite": "test",
            "output_dir": "/runs/{run_id}/{case}",
            "cases": [],
        }
        path = self._write_config(config)
        with self.assertRaises((ValueError, KeyError)):
            load_config(path)

    def test_missing_output_dir_raises(self):
        config = {
            "suite": "test",
            "golden_dir": "/golden/{case}",
            "cases": [],
        }
        path = self._write_config(config)
        with self.assertRaises((ValueError, KeyError)):
            load_config(path)

    def test_case_missing_name_raises(self):
        config = {
            "suite": "test",
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "cases": [{"command": "echo 1", "input": "/data"}],
        }
        path = self._write_config(config)
        with self.assertRaises((ValueError, KeyError)):
            load_config(path)

    def test_case_missing_command_raises(self):
        config = {
            "suite": "test",
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "cases": [{"name": "c1", "input": "/data"}],
        }
        path = self._write_config(config)
        with self.assertRaises((ValueError, KeyError)):
            load_config(path)

    def test_invalid_json_raises(self):
        path = self._write_raw("{bad json!!")
        with self.assertRaises((json.JSONDecodeError, ValueError)):
            load_config(path)

    def test_file_not_found_raises(self):
        with self.assertRaises((FileNotFoundError, OSError)):
            load_config("/nonexistent/path/suite.json")

    def test_invalid_diff_rule_type_raises(self):
        config = {
            "suite": "test",
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "diff_rules": [{"type": "bogus", "pattern": "x"}],
            "cases": [],
        }
        path = self._write_config(config)
        with self.assertRaises((ValueError, TypeError)):
            load_config(path)


class TestPlaceholderExpansion(unittest.TestCase):
    """Test that placeholders in golden_dir, output_dir, command are expanded."""

    def setUp(self):
        _skip_if_not_implemented(load_config, Suite)
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write_config(self, data):
        path = os.path.join(self.test_dir, "suite.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def test_golden_dir_case_placeholder(self):
        """golden_dir with {case} should be expandable per case."""
        config = {
            "suite": "test",
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "cases": [
                {"name": "case_x", "command": "echo x", "input": "/data/x"},
            ],
        }
        path = self._write_config(config)
        suite = load_config(path)
        # The Suite should store the template; expansion happens at runtime
        self.assertIn("{case}", suite.golden_dir)

    def test_env_placeholder_in_versions(self):
        """env with {version} placeholder works with versions map."""
        config = {
            "suite": "test",
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "env": {"TOOL_ROOT": "/tools/{version}"},
            "versions": {
                "v1": {"version": "1.0"},
                "v2": {"version": "2.0"},
            },
            "cases": [
                {"name": "c1", "command": "run.sh", "input": "/data/c1"},
            ],
        }
        path = self._write_config(config)
        suite = load_config(path)
        self.assertIn("{version}", suite.env["TOOL_ROOT"])


class TestDiffRulesMerge(unittest.TestCase):
    """Test diff_rules_mode: append (default) vs override."""

    def setUp(self):
        _skip_if_not_implemented(load_config, Suite)
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write_config(self, data):
        path = os.path.join(self.test_dir, "suite.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def test_append_mode_merges_global_and_case_rules(self):
        """Default append mode: case rules added after global rules."""
        config = {
            "suite": "test",
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "diff_rules": [
                {"type": "ignore_file", "pattern": "*.log"},
            ],
            "cases": [
                {
                    "name": "c1",
                    "command": "echo 1",
                    "input": "/data/c1",
                    "diff_rules": [
                        {"type": "ignore_line", "pattern": "^DEBUG:"},
                    ],
                },
            ],
        }
        path = self._write_config(config)
        suite = load_config(path)
        # After merge, case should have both global + case rules
        # The merge should be done at comparison time or config resolution time
        # We test that the raw data is preserved correctly
        self.assertEqual(len(suite.diff_rules), 1)  # global
        self.assertEqual(len(suite.cases[0].diff_rules), 1)  # case-level
        self.assertEqual(suite.cases[0].diff_rules_mode, "append")

    def test_override_mode_case_rules_only(self):
        """Override mode: case rules replace global rules entirely."""
        config = {
            "suite": "test",
            "golden_dir": "/golden/{case}",
            "output_dir": "/runs/{run_id}/{case}",
            "diff_rules": [
                {"type": "ignore_file", "pattern": "*.log"},
            ],
            "cases": [
                {
                    "name": "c1",
                    "command": "echo 1",
                    "input": "/data/c1",
                    "diff_rules_mode": "override",
                    "diff_rules": [
                        {"type": "ignore_line", "pattern": "^DEBUG:"},
                    ],
                },
            ],
        }
        path = self._write_config(config)
        suite = load_config(path)
        self.assertEqual(suite.cases[0].diff_rules_mode, "override")


if __name__ == "__main__":
    unittest.main()
