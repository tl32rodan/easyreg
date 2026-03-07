"""Diff rule engine: filtering and transformation for comparison."""
import fnmatch
import re
from typing import List

from ..model import DiffRule


def apply_line_rules(lines: List[str], rules: List[DiffRule]) -> List[str]:
    """Apply ignore_line and ignore_regex rules to a list of lines.

    Rules are applied in order:
    1. ignore_line rules remove matching lines entirely.
    2. ignore_regex rules replace matching patterns within remaining lines.
    """
    result = list(lines)

    for rule in rules:
        if rule.type == "ignore_line":
            pattern = re.compile(rule.pattern)
            result = [line for line in result if not pattern.search(line)]
        elif rule.type == "ignore_regex":
            pattern = re.compile(rule.pattern)
            replacement = rule.replace if rule.replace is not None else ""
            result = [pattern.sub(replacement, line) for line in result]

    return result


def should_ignore_file(filename: str, rules: List[DiffRule]) -> bool:
    """Check if a file should be ignored based on ignore_file rules."""
    for rule in rules:
        if rule.type == "ignore_file" and fnmatch.fnmatch(filename, rule.pattern):
            return True
    return False


def should_ignore_folder(foldername: str, rules: List[DiffRule]) -> bool:
    """Check if a folder should be ignored based on ignore_folder rules."""
    for rule in rules:
        if rule.type == "ignore_folder":
            # Pattern may end with /, match against both forms
            pat = rule.pattern.rstrip("/")
            if fnmatch.fnmatch(foldername, pat):
                return True
    return False


def resolve_effective_rules(
    global_rules: List[DiffRule],
    case_rules: List[DiffRule],
    mode: str,
) -> List[DiffRule]:
    """Resolve effective diff rules based on merge mode.

    Args:
        global_rules: Suite-level diff rules.
        case_rules: Case-level diff rules.
        mode: "append" (global + case) or "override" (case only).
    """
    if mode == "override":
        return list(case_rules)
    # Default: append
    return list(global_rules) + list(case_rules)
