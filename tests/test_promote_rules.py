"""Tests for golden promotion with rules and manifest metadata."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from easyreg.golden import GoldenManager
from easyreg.model import DiffRule


class _PromoteRulesTestBase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)
        self.golden_root = self.root / "golden"
        self.golden_root.mkdir()
        self.source = self.root / "output" / "case_a"
        self.source.mkdir(parents=True)
        self.mgr = GoldenManager(self.golden_root)

    def tearDown(self):
        shutil.rmtree(self.test_dir)


class TestPromoteIgnoreFile(_PromoteRulesTestBase):
    def test_ignored_files_excluded(self):
        (self.source / "data.txt").write_text("hello\n")
        (self.source / "debug.log").write_text("log data\n")

        rules = [DiffRule(type="ignore_file", pattern="*.log")]
        self.mgr.promote_with_rules("case_a", self.source, rules, {"promoted_at": "now"})

        golden = self.golden_root / "case_a"
        self.assertTrue((golden / "data.txt").exists())
        self.assertFalse((golden / "debug.log").exists())


class TestPromoteIgnoreFolder(_PromoteRulesTestBase):
    def test_ignored_folders_excluded(self):
        (self.source / "results").mkdir()
        (self.source / "results" / "out.txt").write_text("result\n")
        (self.source / "tmp").mkdir()
        (self.source / "tmp" / "scratch.txt").write_text("temp\n")

        rules = [DiffRule(type="ignore_folder", pattern="tmp")]
        self.mgr.promote_with_rules("case_a", self.source, rules, {"promoted_at": "now"})

        golden = self.golden_root / "case_a"
        self.assertTrue((golden / "results" / "out.txt").exists())
        self.assertFalse((golden / "tmp").exists())


class TestPromoteLineRules(_PromoteRulesTestBase):
    def test_ignore_line_transforms_content(self):
        (self.source / "output.txt").write_text(
            "# Generated at 2025-01-01\nresult: 42\n"
        )

        rules = [DiffRule(type="ignore_line", pattern="^# Generated")]
        self.mgr.promote_with_rules("case_a", self.source, rules, {"promoted_at": "now"})

        golden = self.golden_root / "case_a"
        content = (golden / "output.txt").read_text()
        self.assertNotIn("Generated", content)
        self.assertIn("result: 42", content)

    def test_ignore_regex_transforms_content(self):
        (self.source / "output.txt").write_text("PID=12345 status=ok\n")

        rules = [DiffRule(type="ignore_regex", pattern=r"PID=\d+", replace="PID=XXX")]
        self.mgr.promote_with_rules("case_a", self.source, rules, {"promoted_at": "now"})

        golden = self.golden_root / "case_a"
        content = (golden / "output.txt").read_text()
        self.assertIn("PID=XXX", content)
        self.assertNotIn("12345", content)

    def test_sort_lines_transforms_content(self):
        (self.source / "output.txt").write_text("cherry\napple\nbanana\n")

        rules = [DiffRule(type="sort_lines", pattern="*")]
        self.mgr.promote_with_rules("case_a", self.source, rules, {"promoted_at": "now"})

        golden = self.golden_root / "case_a"
        content = (golden / "output.txt").read_text()
        lines = content.strip().split("\n")
        self.assertEqual(lines, ["apple", "banana", "cherry"])


class TestPromoteBinaryFiles(_PromoteRulesTestBase):
    def test_binary_files_copied_as_is(self):
        binary_data = bytes(range(256))
        (self.source / "data.bin").write_bytes(binary_data)

        rules = [DiffRule(type="ignore_line", pattern="^#")]
        self.mgr.promote_with_rules("case_a", self.source, rules, {"promoted_at": "now"})

        golden = self.golden_root / "case_a"
        self.assertEqual((golden / "data.bin").read_bytes(), binary_data)


class TestManifest(_PromoteRulesTestBase):
    def test_manifest_created(self):
        (self.source / "data.txt").write_text("hello\n")

        metadata = {
            "promoted_at": "2026-03-10T00:00:00+00:00",
            "source_output_dir": str(self.source),
            "suite_config": {"suite": "test", "golden_dir": "g", "output_dir": "o"},
            "effective_rules": [],
        }
        self.mgr.promote_with_rules("case_a", self.source, [], metadata)

        manifest_path = self.golden_root / "golden_manifest.json"
        self.assertTrue(manifest_path.exists())

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("case_a", manifest["cases"])
        entry = manifest["cases"]["case_a"]
        self.assertEqual(entry["promoted_at"], "2026-03-10T00:00:00+00:00")
        self.assertEqual(entry["suite_config"]["suite"], "test")

    def test_manifest_incrementally_updated(self):
        (self.source / "data.txt").write_text("hello\n")

        meta_a = {"promoted_at": "t1", "source_output_dir": "a", "suite_config": {}, "effective_rules": []}
        self.mgr.promote_with_rules("case_a", self.source, [], meta_a)

        source_b = self.root / "output" / "case_b"
        source_b.mkdir(parents=True)
        (source_b / "data.txt").write_text("world\n")

        meta_b = {"promoted_at": "t2", "source_output_dir": "b", "suite_config": {}, "effective_rules": []}
        self.mgr.promote_with_rules("case_b", source_b, [], meta_b)

        manifest_path = self.golden_root / "golden_manifest.json"
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("case_a", manifest["cases"])
        self.assertIn("case_b", manifest["cases"])
        self.assertEqual(manifest["cases"]["case_a"]["promoted_at"], "t1")
        self.assertEqual(manifest["cases"]["case_b"]["promoted_at"], "t2")

    def test_manifest_with_rules_recorded(self):
        (self.source / "data.txt").write_text("hello\n")

        rules = [DiffRule(type="ignore_file", pattern="*.log")]
        metadata = {
            "promoted_at": "t1",
            "source_output_dir": str(self.source),
            "suite_config": {"suite": "test"},
            "effective_rules": [
                {"type": "ignore_file", "pattern": "*.log", "replace": None}
            ],
        }
        self.mgr.promote_with_rules("case_a", self.source, rules, metadata)

        manifest_path = self.golden_root / "golden_manifest.json"
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        entry = manifest["cases"]["case_a"]
        self.assertEqual(len(entry["effective_rules"]), 1)
        self.assertEqual(entry["effective_rules"][0]["type"], "ignore_file")
        self.assertEqual(entry["effective_rules"][0]["pattern"], "*.log")


class TestPromoteBackup(_PromoteRulesTestBase):
    def test_existing_golden_backed_up(self):
        # Create existing golden
        existing = self.golden_root / "case_a"
        existing.mkdir()
        (existing / "old.txt").write_text("old data\n")

        (self.source / "new.txt").write_text("new data\n")

        self.mgr.promote_with_rules("case_a", self.source, [], {"promoted_at": "t"})

        # Old golden should be backed up
        backup = self.golden_root / "case_a.bak"
        self.assertTrue(backup.exists())
        self.assertTrue((backup / "old.txt").exists())

        # New golden should have new content
        golden = self.golden_root / "case_a"
        self.assertTrue((golden / "new.txt").exists())
        self.assertFalse((golden / "old.txt").exists())


if __name__ == "__main__":
    unittest.main()
