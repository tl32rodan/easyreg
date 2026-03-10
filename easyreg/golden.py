"""Golden reference management: read, promote, backup, status."""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .comparator.diff_rules import apply_line_rules, should_ignore_file, should_ignore_folder
from .model import DiffRule


class GoldenManager:
    """Manages golden reference directories."""

    def __init__(self, golden_root: Path):
        self._root = Path(golden_root)

    def exists(self, case_name: str) -> bool:
        return (self._root / case_name).is_dir()

    def get_path(self, case_name: str) -> Path:
        return self._root / case_name

    def promote(self, case_name: str, source_dir: Path) -> None:
        """Copy source_dir contents to golden, backing up any existing golden."""
        source_dir = Path(source_dir)
        if not source_dir.is_dir():
            raise FileNotFoundError(
                f"Source directory does not exist: {source_dir}"
            )

        golden_dir = self._root / case_name

        # Backup existing golden if present
        if golden_dir.exists():
            backup_dir = self._root / f"{case_name}.bak"
            # Remove old backup if exists
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            golden_dir.rename(backup_dir)

        # Copy source to golden
        shutil.copytree(source_dir, golden_dir)

    def promote_with_rules(
        self,
        case_name: str,
        source_dir: Path,
        rules: List[DiffRule],
        metadata_entry: dict,
    ) -> None:
        """Promote source_dir to golden, applying rules to filter/transform contents.

        - ignore_file rules: skip matching files
        - ignore_folder rules: skip matching directories
        - ignore_line / ignore_regex / sort_lines: transform text file contents
        - Updates golden_manifest.json at golden_root level
        """
        source_dir = Path(source_dir)
        if not source_dir.is_dir():
            raise FileNotFoundError(
                f"Source directory does not exist: {source_dir}"
            )

        golden_dir = self._root / case_name

        # Backup existing golden if present
        if golden_dir.exists():
            backup_dir = self._root / f"{case_name}.bak"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            golden_dir.rename(backup_dir)

        # Walk source and copy with rules applied
        text_rule_types = {"ignore_line", "ignore_regex", "sort_lines"}
        text_rules = [r for r in rules if r.type in text_rule_types]

        self._copy_with_rules(source_dir, golden_dir, rules, text_rules)

        # Update manifest
        self._update_manifest(case_name, metadata_entry)

    def _copy_with_rules(
        self,
        source: Path,
        dest: Path,
        rules: List[DiffRule],
        text_rules: List[DiffRule],
    ) -> None:
        """Recursively copy source to dest, applying rules."""
        dest.mkdir(parents=True, exist_ok=True)

        for entry in sorted(source.iterdir()):
            if entry.is_dir():
                if should_ignore_folder(entry.name, rules):
                    continue
                self._copy_with_rules(entry, dest / entry.name, rules, text_rules)
            else:
                if should_ignore_file(entry.name, rules):
                    continue
                if text_rules:
                    try:
                        content = entry.read_text(encoding="utf-8")
                        lines = content.splitlines()
                        transformed = apply_line_rules(lines, text_rules)
                        (dest / entry.name).write_text(
                            "\n".join(transformed) + ("\n" if content.endswith("\n") else ""),
                            encoding="utf-8",
                        )
                        continue
                    except UnicodeDecodeError:
                        pass
                # Binary file or no text rules — copy as-is
                shutil.copy2(entry, dest / entry.name)

    def _load_manifest(self) -> dict:
        """Load the golden manifest, or return empty structure."""
        manifest_path = self._root / "golden_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"cases": {}}

    def _save_manifest(self, manifest: dict) -> None:
        """Save the golden manifest."""
        self._root.mkdir(parents=True, exist_ok=True)
        manifest_path = self._root / "golden_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def _update_manifest(self, case_name: str, metadata_entry: dict) -> None:
        """Update the manifest with a new case entry."""
        manifest = self._load_manifest()
        manifest["cases"][case_name] = metadata_entry
        self._save_manifest(manifest)

    def status(self) -> Dict[str, bool]:
        """Return a dict of case_name → exists for all subdirectories."""
        if not self._root.exists():
            return {}
        return {
            d.name: True
            for d in sorted(self._root.iterdir())
            if d.is_dir() and not d.name.endswith(".bak")
        }
