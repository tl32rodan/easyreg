"""Golden reference management: read, promote, backup, status."""
import shutil
from pathlib import Path
from typing import Dict, List


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

    def status(self) -> Dict[str, bool]:
        """Return a dict of case_name → exists for all subdirectories."""
        if not self._root.exists():
            return {}
        return {
            d.name: True
            for d in sorted(self._root.iterdir())
            if d.is_dir() and not d.name.endswith(".bak")
        }
