"""Tests for regressionx.comparator.diff_rules — Diff rule engine.

Covers:
- ignore_line: skip lines matching regex
- ignore_regex: replace matching patterns within lines before comparison
- ignore_file: skip files matching glob
- ignore_folder: skip directories matching glob
- sort_lines: sort lines before comparison (unstable output order)
- tolerance: numeric tolerance comparison
- Rule chaining (multiple rules applied in order)
- Effective rules resolution (append vs override mode)
"""
import unittest

try:
    from regressionx.model import DiffRule
    from regressionx.comparator.diff_rules import (
        apply_line_rules,
        should_ignore_file,
        should_ignore_folder,
        resolve_effective_rules,
        apply_sort_lines,
        lines_within_tolerance,
    )
except ImportError:
    DiffRule = None
    apply_line_rules = None
    should_ignore_file = None
    apply_sort_lines = None
    lines_within_tolerance = None
    should_ignore_folder = None
    resolve_effective_rules = None


def _skip_if_not_implemented():
    if any(x is None for x in [
        DiffRule, apply_line_rules, should_ignore_file,
        should_ignore_folder, resolve_effective_rules,
    ]):
        raise unittest.SkipTest("diff_rules module not yet implemented")


# ─── ignore_line ─────────────────────────────────────────────────────────────

class TestIgnoreLine(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()

    def test_matching_line_is_removed(self):
        rules = [DiffRule(type="ignore_line", pattern="^# Generated at")]
        lines = [
            "# Generated at 2025-01-01",
            "data line 1",
            "data line 2",
        ]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["data line 1", "data line 2"])

    def test_non_matching_lines_preserved(self):
        rules = [DiffRule(type="ignore_line", pattern="^DEBUG:")]
        lines = ["INFO: ok", "WARNING: hmm"]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["INFO: ok", "WARNING: hmm"])

    def test_regex_pattern(self):
        rules = [DiffRule(type="ignore_line", pattern=r"^#.*timestamp.*")]
        lines = [
            "# timestamp: 12345",
            "# This has timestamp in it",
            "actual data",
        ]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["actual data"])

    def test_all_lines_removed(self):
        rules = [DiffRule(type="ignore_line", pattern=".*")]
        lines = ["a", "b", "c"]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, [])

    def test_empty_input(self):
        rules = [DiffRule(type="ignore_line", pattern="^#")]
        result = apply_line_rules([], rules)
        self.assertEqual(result, [])


# ─── ignore_regex ────────────────────────────────────────────────────────────

class TestIgnoreRegex(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()

    def test_replace_pid(self):
        rules = [DiffRule(type="ignore_regex", pattern=r"PID=\d+", replace="PID=XXX")]
        lines = ["Process started PID=12345 running"]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["Process started PID=XXX running"])

    def test_replace_timestamp(self):
        rules = [DiffRule(
            type="ignore_regex",
            pattern=r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            replace="YYYY-MM-DD HH:MM:SS",
        )]
        lines = ["Log entry 2025-03-07 14:30:00 info"]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["Log entry YYYY-MM-DD HH:MM:SS info"])

    def test_multiple_occurrences_in_one_line(self):
        rules = [DiffRule(type="ignore_regex", pattern=r"\d+", replace="N")]
        lines = ["count=42 total=100"]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["count=N total=N"])

    def test_no_match_leaves_line_unchanged(self):
        rules = [DiffRule(type="ignore_regex", pattern=r"PID=\d+", replace="PID=XXX")]
        lines = ["no pid here"]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["no pid here"])


# ─── ignore_file ─────────────────────────────────────────────────────────────

class TestIgnoreFile(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()

    def test_glob_match_log(self):
        rules = [DiffRule(type="ignore_file", pattern="*.log")]
        self.assertTrue(should_ignore_file("debug.log", rules))
        self.assertFalse(should_ignore_file("output.txt", rules))

    def test_glob_match_multiple_patterns(self):
        rules = [
            DiffRule(type="ignore_file", pattern="*.log"),
            DiffRule(type="ignore_file", pattern="*.tmp"),
        ]
        self.assertTrue(should_ignore_file("run.log", rules))
        self.assertTrue(should_ignore_file("cache.tmp", rules))
        self.assertFalse(should_ignore_file("result.txt", rules))

    def test_exact_filename_match(self):
        rules = [DiffRule(type="ignore_file", pattern="Thumbs.db")]
        self.assertTrue(should_ignore_file("Thumbs.db", rules))
        self.assertFalse(should_ignore_file("thumbs.db", rules))  # case sensitive

    def test_no_rules_means_no_ignore(self):
        self.assertFalse(should_ignore_file("anything.txt", []))

    def test_only_file_rules_considered(self):
        """Non-ignore_file rules should not affect file matching."""
        rules = [DiffRule(type="ignore_line", pattern="*.log")]
        self.assertFalse(should_ignore_file("debug.log", rules))


# ─── ignore_folder ───────────────────────────────────────────────────────────

class TestIgnoreFolder(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()

    def test_glob_match_folder(self):
        rules = [DiffRule(type="ignore_folder", pattern="tmp/")]
        self.assertTrue(should_ignore_folder("tmp", rules))

    def test_glob_match_pycache(self):
        rules = [DiffRule(type="ignore_folder", pattern="__pycache__/")]
        self.assertTrue(should_ignore_folder("__pycache__", rules))

    def test_no_match(self):
        rules = [DiffRule(type="ignore_folder", pattern="tmp/")]
        self.assertFalse(should_ignore_folder("output", rules))

    def test_multiple_folder_patterns(self):
        rules = [
            DiffRule(type="ignore_folder", pattern="tmp/"),
            DiffRule(type="ignore_folder", pattern="logs/"),
        ]
        self.assertTrue(should_ignore_folder("tmp", rules))
        self.assertTrue(should_ignore_folder("logs", rules))
        self.assertFalse(should_ignore_folder("data", rules))

    def test_no_rules_means_no_ignore(self):
        self.assertFalse(should_ignore_folder("anything", []))

    def test_only_folder_rules_considered(self):
        """Non-ignore_folder rules should not affect folder matching."""
        rules = [DiffRule(type="ignore_file", pattern="tmp/")]
        self.assertFalse(should_ignore_folder("tmp", rules))


# ─── Rule chaining ───────────────────────────────────────────────────────────

class TestRuleChaining(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()

    def test_ignore_line_then_ignore_regex(self):
        """Rules apply in order: first remove lines, then regex-replace."""
        rules = [
            DiffRule(type="ignore_line", pattern="^#"),
            DiffRule(type="ignore_regex", pattern=r"PID=\d+", replace="PID=XXX"),
        ]
        lines = [
            "# comment line",
            "Process PID=999 started",
            "done",
        ]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["Process PID=XXX started", "done"])

    def test_multiple_ignore_regex_rules(self):
        rules = [
            DiffRule(type="ignore_regex", pattern=r"PID=\d+", replace="PID=X"),
            DiffRule(type="ignore_regex", pattern=r"TIME=\S+", replace="TIME=X"),
        ]
        lines = ["PID=123 TIME=14:30:00"]
        result = apply_line_rules(lines, rules)
        self.assertEqual(result, ["PID=X TIME=X"])


# ─── resolve_effective_rules ─────────────────────────────────────────────────

class TestResolveEffectiveRules(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()

    def test_no_case_rules_returns_global(self):
        global_rules = [DiffRule(type="ignore_file", pattern="*.log")]
        result = resolve_effective_rules(global_rules, [], "append")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].pattern, "*.log")

    def test_append_mode_concatenates(self):
        global_rules = [DiffRule(type="ignore_file", pattern="*.log")]
        case_rules = [DiffRule(type="ignore_line", pattern="^DEBUG:")]
        result = resolve_effective_rules(global_rules, case_rules, "append")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].pattern, "*.log")  # global first
        self.assertEqual(result[1].pattern, "^DEBUG:")  # case after

    def test_override_mode_uses_case_only(self):
        global_rules = [DiffRule(type="ignore_file", pattern="*.log")]
        case_rules = [DiffRule(type="ignore_line", pattern="^DEBUG:")]
        result = resolve_effective_rules(global_rules, case_rules, "override")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].pattern, "^DEBUG:")

    def test_override_with_empty_case_rules_returns_empty(self):
        global_rules = [DiffRule(type="ignore_file", pattern="*.log")]
        result = resolve_effective_rules(global_rules, [], "override")
        self.assertEqual(len(result), 0)

    def test_append_with_empty_global_returns_case_only(self):
        case_rules = [DiffRule(type="ignore_line", pattern="^DEBUG:")]
        result = resolve_effective_rules([], case_rules, "append")
        self.assertEqual(len(result), 1)


# ─── sort_lines ──────────────────────────────────────────────────────────────

def _skip_sort():
    if apply_sort_lines is None:
        raise unittest.SkipTest("sort_lines not yet implemented")


class TestSortLines(unittest.TestCase):
    def setUp(self):
        _skip_sort()

    def test_sorts_lines_alphabetically(self):
        lines = ["banana", "apple", "cherry"]
        result = apply_sort_lines(lines)
        self.assertEqual(result, ["apple", "banana", "cherry"])

    def test_already_sorted_unchanged(self):
        lines = ["a", "b", "c"]
        result = apply_sort_lines(lines)
        self.assertEqual(result, ["a", "b", "c"])

    def test_empty_input(self):
        self.assertEqual(apply_sort_lines([]), [])

    def test_single_line(self):
        self.assertEqual(apply_sort_lines(["only"]), ["only"])

    def test_does_not_mutate_input(self):
        lines = ["b", "a"]
        apply_sort_lines(lines)
        self.assertEqual(lines, ["b", "a"])  # original unchanged

    def test_sort_rule_applied_via_apply_line_rules(self):
        """sort_lines rule should work through apply_line_rules pipeline."""
        if DiffRule is None:
            raise unittest.SkipTest("model not implemented")
        rule = DiffRule(type="sort_lines", pattern="")
        lines = ["z_line", "a_line", "m_line"]
        result = apply_line_rules(lines, [rule])
        self.assertEqual(result, ["a_line", "m_line", "z_line"])


# ─── tolerance ───────────────────────────────────────────────────────────────

def _skip_tol():
    if lines_within_tolerance is None:
        raise unittest.SkipTest("tolerance not yet implemented")


class TestTolerance(unittest.TestCase):
    def setUp(self):
        _skip_tol()

    def test_exact_match(self):
        self.assertTrue(lines_within_tolerance(["1.0", "2.0"], ["1.0", "2.0"], 0.0))

    def test_within_absolute_tolerance(self):
        self.assertTrue(lines_within_tolerance(["1.000", "2.000"],
                                               ["1.001", "2.001"], 0.01))

    def test_outside_absolute_tolerance(self):
        self.assertFalse(lines_within_tolerance(["1.0", "2.0"],
                                                ["1.5", "2.5"], 0.1))

    def test_mixed_numeric_and_text(self):
        """Text lines must match exactly; numeric lines use tolerance."""
        self.assertTrue(lines_within_tolerance(
            ["label: 1.000", "other"],
            ["label: 1.001", "other"],
            0.01,
        ))

    def test_text_mismatch_fails(self):
        self.assertFalse(lines_within_tolerance(
            ["hello", "1.0"],
            ["world", "1.0"],
            0.01,
        ))

    def test_different_line_counts_fails(self):
        self.assertFalse(lines_within_tolerance(["1.0"], ["1.0", "2.0"], 0.0))

    def test_tolerance_rule_via_apply_line_rules(self):
        """tolerance rule should be accessible for future integration."""
        if DiffRule is None:
            raise unittest.SkipTest("model not implemented")
        # tolerance is applied at file-compare level, not line-filter level,
        # so DiffRule type should be registered as valid
        rule = DiffRule(type="tolerance", pattern=r"\d+\.\d+", replace="0.01")
        self.assertEqual(rule.type, "tolerance")


if __name__ == "__main__":
    unittest.main()
