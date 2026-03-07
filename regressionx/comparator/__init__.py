"""Comparator package: directory and content comparison with diff rules."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..model import DiffRule
from .diff_rules import apply_line_rules, should_ignore_file, should_ignore_folder


@dataclass
class ComparisonResult:
    """Result of comparing two directories."""
    match: bool
    errors: List[str] = field(default_factory=list)
    diffs: List[str] = field(default_factory=list)


def compare_directories(
    golden: Path,
    output: Path,
    diff_rules: Optional[List[DiffRule]] = None,
    _prefix: str = "",
) -> ComparisonResult:
    """Recursively compare two directories, applying diff rules.

    Args:
        golden: Path to the golden (expected) directory.
        output: Path to the output (actual) directory.
        diff_rules: Optional list of DiffRule to apply.
        _prefix: Internal, for tracking relative paths in recursion.
    """
    golden = Path(golden)
    output = Path(output)
    rules = diff_rules or []
    errors = []
    diffs = []

    # Collect entries from both sides
    golden_entries = {e.name: e for e in sorted(golden.iterdir())} if golden.exists() else {}
    output_entries = {e.name: e for e in sorted(output.iterdir())} if output.exists() else {}

    all_names = sorted(set(golden_entries) | set(output_entries))

    for name in all_names:
        rel_path = f"{_prefix}{name}" if not _prefix else f"{_prefix}/{name}"
        if not _prefix:
            rel_path = name

        g_entry = golden_entries.get(name)
        o_entry = output_entries.get(name)

        # Check if this is a directory on either side
        g_is_dir = g_entry is not None and g_entry.is_dir()
        o_is_dir = o_entry is not None and o_entry.is_dir()

        if g_is_dir or o_is_dir:
            if should_ignore_folder(name, rules):
                continue
            # Recurse into subdirectories
            sub_golden = golden / name
            sub_output = output / name
            if g_entry is None:
                errors.append(f"Only in output: {rel_path}")
                continue
            if o_entry is None:
                errors.append(f"Only in golden: {rel_path}")
                continue
            sub_result = compare_directories(
                sub_golden, sub_output, diff_rules=rules,
                _prefix=f"{rel_path}/",
            )
            errors.extend(sub_result.errors)
            diffs.extend(sub_result.diffs)
            continue

        # File handling
        if should_ignore_file(name, rules):
            continue

        if g_entry is None:
            errors.append(f"Only in output: {rel_path}")
            continue
        if o_entry is None:
            errors.append(f"Only in golden: {rel_path}")
            continue

        # Compare file content
        if not _compare_file_content(g_entry, o_entry, rules):
            diffs.append(f"Content mismatch: {rel_path}")

    has_issues = bool(errors) or bool(diffs)
    return ComparisonResult(match=not has_issues, errors=errors, diffs=diffs)


def _compare_file_content(
    golden_file: Path, output_file: Path, rules: List[DiffRule]
) -> bool:
    """Compare two files, applying line-level diff rules."""
    # Check if we have any line-level rules
    line_rules = [r for r in rules if r.type in ("ignore_line", "ignore_regex")]

    if not line_rules:
        # Fast path: binary comparison
        return golden_file.read_bytes() == output_file.read_bytes()

    # Text comparison with rules
    try:
        golden_lines = golden_file.read_text(encoding="utf-8").splitlines()
        output_lines = output_file.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        # Binary file, fall back to byte comparison
        return golden_file.read_bytes() == output_file.read_bytes()

    golden_filtered = apply_line_rules(golden_lines, line_rules)
    output_filtered = apply_line_rules(output_lines, line_rules)

    return golden_filtered == output_filtered
