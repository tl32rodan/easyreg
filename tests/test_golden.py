"""Tests for regressionx.golden — Golden reference management.

Covers:
- Read golden directory (exists vs not exists)
- Promote: copy run output → golden
- Promote: backup existing golden before overwrite
- Promote specific case only
- Golden status check
"""
import unittest
import tempfile
import shutil
from pathlib import Path

try:
    from regressionx.golden import GoldenManager
except ImportError:
    GoldenManager = None


def _skip_if_not_implemented():
    if GoldenManager is None:
        raise unittest.SkipTest("golden module not yet implemented")


class _GoldenTestBase(unittest.TestCase):
    def setUp(self):
        _skip_if_not_implemented()
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)
        self.golden_root = self.root / "golden"
        self.output_root = self.root / "output"
        self.golden_root.mkdir()
        self.output_root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create(self, parent: Path, name: str, content: str):
        p = parent / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


class TestGoldenExists(_GoldenTestBase):

    def test_golden_exists_returns_true(self):
        golden_dir = self.golden_root / "case_a"
        golden_dir.mkdir()
        self._create(golden_dir, "output.txt", "golden data")

        mgr = GoldenManager(self.golden_root)
        self.assertTrue(mgr.exists("case_a"))

    def test_golden_not_exists_returns_false(self):
        mgr = GoldenManager(self.golden_root)
        self.assertFalse(mgr.exists("case_nonexistent"))

    def test_golden_path(self):
        mgr = GoldenManager(self.golden_root)
        path = mgr.get_path("case_a")
        self.assertEqual(path, self.golden_root / "case_a")


class TestGoldenPromote(_GoldenTestBase):

    def test_promote_creates_golden_from_output(self):
        """First-time promotion: output → golden."""
        output_dir = self.output_root / "case_a"
        self._create(output_dir, "result.txt", "new output")
        self._create(output_dir, "sub/data.txt", "nested")

        mgr = GoldenManager(self.golden_root)
        mgr.promote("case_a", output_dir)

        golden_dir = self.golden_root / "case_a"
        self.assertTrue(golden_dir.exists())
        self.assertEqual(
            (golden_dir / "result.txt").read_text(encoding="utf-8"),
            "new output",
        )
        self.assertEqual(
            (golden_dir / "sub/data.txt").read_text(encoding="utf-8"),
            "nested",
        )

    def test_promote_overwrites_existing_golden(self):
        """Re-promotion: old golden is replaced with new output."""
        golden_dir = self.golden_root / "case_a"
        self._create(golden_dir, "result.txt", "old golden")

        output_dir = self.output_root / "case_a"
        self._create(output_dir, "result.txt", "updated output")

        mgr = GoldenManager(self.golden_root)
        mgr.promote("case_a", output_dir)

        self.assertEqual(
            (golden_dir / "result.txt").read_text(encoding="utf-8"),
            "updated output",
        )

    def test_promote_creates_backup_of_existing_golden(self):
        """When overwriting, a backup of the old golden should be created."""
        golden_dir = self.golden_root / "case_a"
        self._create(golden_dir, "result.txt", "old golden")

        output_dir = self.output_root / "case_a"
        self._create(output_dir, "result.txt", "new output")

        mgr = GoldenManager(self.golden_root)
        mgr.promote("case_a", output_dir)

        # Backup directory should exist (e.g., case_a.bak or case_a.prev)
        backup_candidates = list(self.golden_root.glob("case_a.bak*")) + \
                           list(self.golden_root.glob("case_a.prev*"))
        self.assertGreater(len(backup_candidates), 0,
                          "Expected backup directory after promotion")

    def test_promote_nonexistent_output_raises(self):
        mgr = GoldenManager(self.golden_root)
        with self.assertRaises((FileNotFoundError, ValueError)):
            mgr.promote("case_a", self.output_root / "nonexistent")


class TestGoldenStatus(_GoldenTestBase):

    def test_status_reports_existing_cases(self):
        self._create(self.golden_root / "case_a", "f.txt", "a")
        self._create(self.golden_root / "case_b", "f.txt", "b")

        mgr = GoldenManager(self.golden_root)
        status = mgr.status()

        self.assertIn("case_a", status)
        self.assertIn("case_b", status)

    def test_status_empty_golden(self):
        mgr = GoldenManager(self.golden_root)
        status = mgr.status()
        self.assertEqual(len(status), 0)


if __name__ == "__main__":
    unittest.main()
