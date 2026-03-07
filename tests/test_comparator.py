"""Tests for easyreg.comparator — Directory and content comparison.

Covers:
- Identical directories → PASS
- Missing/extra files → structural errors
- Content mismatch detection
- Nested directory comparison
- Diff rules integration (ignore_file, ignore_folder, ignore_line, ignore_regex)
- Empty directory handling
"""
import unittest
import tempfile
import shutil
from pathlib import Path

try:
    from easyreg.model import DiffRule
    from easyreg.comparator import compare_directories, ComparisonResult
except ImportError:
    DiffRule = None
    compare_directories = None
    ComparisonResult = None


def _skip_if_not_implemented():
    if any(x is None for x in [compare_directories, ComparisonResult, DiffRule]):
        raise unittest.SkipTest("comparator module not yet implemented")


class _ComparatorTestBase(unittest.TestCase):
    """Base class providing temp directory setup and file helpers."""

    def setUp(self):
        _skip_if_not_implemented()
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)
        self.golden = self.root / "golden"
        self.output = self.root / "output"
        self.golden.mkdir()
        self.output.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create(self, parent: Path, name: str, content: str):
        p = parent / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ─── Basic structural comparison ────────────────────────────────────────────

class TestDirectoryStructure(_ComparatorTestBase):

    def test_identical_flat_directories(self):
        self._create(self.golden, "f1.txt", "hello")
        self._create(self.output, "f1.txt", "hello")

        result = compare_directories(self.golden, self.output)
        self.assertTrue(result.match)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.diffs), 0)

    def test_missing_file_in_output(self):
        self._create(self.golden, "expected.txt", "data")

        result = compare_directories(self.golden, self.output)
        self.assertFalse(result.match)
        self.assertTrue(any("Only in golden" in e for e in result.errors))

    def test_extra_file_in_output(self):
        self._create(self.golden, "f1.txt", "data")
        self._create(self.output, "f1.txt", "data")
        self._create(self.output, "extra.txt", "extra")

        result = compare_directories(self.golden, self.output)
        self.assertFalse(result.match)
        self.assertTrue(any("Only in output" in e or "Only in candidate" in e
                            for e in result.errors))

    def test_both_empty_directories_match(self):
        result = compare_directories(self.golden, self.output)
        self.assertTrue(result.match)

    def test_nested_directory_structure(self):
        self._create(self.golden, "sub/deep/f.txt", "nested")
        self._create(self.output, "sub/deep/f.txt", "nested")

        result = compare_directories(self.golden, self.output)
        self.assertTrue(result.match)

    def test_nested_missing_subdirectory(self):
        self._create(self.golden, "sub/f.txt", "data")
        # output has no sub/ directory

        result = compare_directories(self.golden, self.output)
        self.assertFalse(result.match)


# ─── Content comparison ─────────────────────────────────────────────────────

class TestContentComparison(_ComparatorTestBase):

    def test_content_mismatch(self):
        self._create(self.golden, "f.txt", "expected output")
        self._create(self.output, "f.txt", "actual output")

        result = compare_directories(self.golden, self.output)
        self.assertFalse(result.match)
        self.assertTrue(any("f.txt" in d for d in result.diffs))

    def test_multiple_files_some_differ(self):
        self._create(self.golden, "a.txt", "same")
        self._create(self.golden, "b.txt", "original")
        self._create(self.output, "a.txt", "same")
        self._create(self.output, "b.txt", "changed")

        result = compare_directories(self.golden, self.output)
        self.assertFalse(result.match)
        self.assertTrue(any("b.txt" in d for d in result.diffs))
        # a.txt should not appear in diffs
        self.assertFalse(any("a.txt" in d for d in result.diffs))

    def test_identical_content_different_files(self):
        self._create(self.golden, "a.txt", "data")
        self._create(self.golden, "b.txt", "data")
        self._create(self.output, "a.txt", "data")
        self._create(self.output, "b.txt", "data")

        result = compare_directories(self.golden, self.output)
        self.assertTrue(result.match)


# ─── Comparison with diff rules ─────────────────────────────────────────────

class TestComparisonWithDiffRules(_ComparatorTestBase):

    def test_ignore_file_skips_log(self):
        rules = [DiffRule(type="ignore_file", pattern="*.log")]
        self._create(self.golden, "output.txt", "data")
        self._create(self.golden, "debug.log", "golden log")
        self._create(self.output, "output.txt", "data")
        self._create(self.output, "debug.log", "different log")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_ignore_file_only_in_one_side_still_matches(self):
        """Ignored file missing in output should not cause failure."""
        rules = [DiffRule(type="ignore_file", pattern="*.log")]
        self._create(self.golden, "output.txt", "data")
        self._create(self.golden, "run.log", "log stuff")
        self._create(self.output, "output.txt", "data")
        # output has no .log file

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_ignore_folder_skips_directory(self):
        rules = [DiffRule(type="ignore_folder", pattern="tmp/")]
        self._create(self.golden, "output.txt", "data")
        self._create(self.golden, "tmp/cache.dat", "golden cache")
        self._create(self.output, "output.txt", "data")
        self._create(self.output, "tmp/cache.dat", "different cache")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_ignore_folder_missing_in_output_still_matches(self):
        rules = [DiffRule(type="ignore_folder", pattern="tmp/")]
        self._create(self.golden, "output.txt", "data")
        self._create(self.golden, "tmp/stuff.dat", "stuff")
        self._create(self.output, "output.txt", "data")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_ignore_line_makes_content_match(self):
        rules = [DiffRule(type="ignore_line", pattern="^# Generated at")]
        self._create(self.golden, "f.txt",
                     "# Generated at 2024-01-01\nresult: 42\n")
        self._create(self.output, "f.txt",
                     "# Generated at 2025-03-07\nresult: 42\n")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_ignore_regex_normalizes_content(self):
        rules = [DiffRule(type="ignore_regex", pattern=r"PID=\d+", replace="PID=XXX")]
        self._create(self.golden, "f.txt", "started PID=111\n")
        self._create(self.output, "f.txt", "started PID=999\n")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_combined_rules(self):
        """Multiple rule types working together."""
        rules = [
            DiffRule(type="ignore_file", pattern="*.log"),
            DiffRule(type="ignore_line", pattern="^# timestamp"),
            DiffRule(type="ignore_regex", pattern=r"PID=\d+", replace="PID=X"),
        ]
        self._create(self.golden, "result.txt",
                     "# timestamp 111\nPID=100 ok\n")
        self._create(self.golden, "debug.log", "log content golden")
        self._create(self.output, "result.txt",
                     "# timestamp 222\nPID=200 ok\n")
        self._create(self.output, "debug.log", "log content output")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_no_rules_strict_comparison(self):
        """Without rules, even minor differences cause failure."""
        self._create(self.golden, "f.txt", "PID=100\n")
        self._create(self.output, "f.txt", "PID=200\n")

        result = compare_directories(self.golden, self.output)
        self.assertFalse(result.match)


class TestSortLinesComparison(_ComparatorTestBase):
    """Integration tests for sort_lines diff rule in directory comparison."""

    def setUp(self):
        try:
            from easyreg.comparator.diff_rules import apply_sort_lines
            if apply_sort_lines is None:
                raise ImportError
        except ImportError:
            raise unittest.SkipTest("sort_lines not yet implemented")
        super().setUp()

    def test_unordered_output_matches_with_sort_rule(self):
        rules = [DiffRule(type="sort_lines", pattern="")]
        self._create(self.golden, "f.txt", "apple\nbanana\ncherry\n")
        self._create(self.output, "f.txt", "cherry\napple\nbanana\n")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_different_content_fails_even_with_sort(self):
        rules = [DiffRule(type="sort_lines", pattern="")]
        self._create(self.golden, "f.txt", "apple\nbanana\n")
        self._create(self.output, "f.txt", "apple\norange\n")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertFalse(result.match)

    def test_sort_combined_with_ignore_line(self):
        rules = [
            DiffRule(type="ignore_line", pattern="^#"),
            DiffRule(type="sort_lines", pattern=""),
        ]
        self._create(self.golden, "f.txt", "# comment\nbanana\napple\n")
        self._create(self.output, "f.txt", "apple\nbanana\n# another comment\n")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)


class TestToleranceComparison(_ComparatorTestBase):
    """Integration tests for tolerance diff rule in directory comparison."""

    def setUp(self):
        try:
            from easyreg.comparator.diff_rules import lines_within_tolerance
            if lines_within_tolerance is None:
                raise ImportError
        except ImportError:
            raise unittest.SkipTest("tolerance not yet implemented")
        super().setUp()

    def test_numeric_values_within_tolerance_match(self):
        rules = [DiffRule(type="tolerance", pattern=r"\d+\.\d+", replace="0.01")]
        self._create(self.golden, "f.txt", "value: 1.000\nresult: 2.000\n")
        self._create(self.output, "f.txt", "value: 1.001\nresult: 2.001\n")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertTrue(result.match)

    def test_numeric_values_outside_tolerance_fail(self):
        rules = [DiffRule(type="tolerance", pattern=r"\d+\.\d+", replace="0.001")]
        self._create(self.golden, "f.txt", "value: 1.000\n")
        self._create(self.output, "f.txt", "value: 1.500\n")

        result = compare_directories(self.golden, self.output, diff_rules=rules)
        self.assertFalse(result.match)


if __name__ == "__main__":
    unittest.main()
