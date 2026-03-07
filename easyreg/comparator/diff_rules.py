"""Diff rule engine: filtering and transformation for comparison."""
import fnmatch
import re
from typing import List

from ..model import DiffRule


def apply_line_rules(lines: List[str], rules: List[DiffRule]) -> List[str]:
    """Apply ignore_line, ignore_regex, and sort_lines rules to a list of lines.

    Rules are applied in order:
    1. ignore_line  — remove lines matching regex
    2. ignore_regex — replace patterns within remaining lines
    3. sort_lines   — sort lines alphabetically
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
        elif rule.type == "sort_lines":
            result = apply_sort_lines(result)

    return result


def apply_sort_lines(lines: List[str]) -> List[str]:
    """Return a sorted copy of lines (does not mutate input)."""
    return sorted(lines)


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
    return list(global_rules) + list(case_rules)


def lines_within_tolerance(
    golden_lines: List[str],
    output_lines: List[str],
    tolerance: float,
) -> bool:
    """Compare two lists of lines with numeric tolerance.

    Text tokens must match exactly. Numeric tokens are compared with
    abs(a - b) <= tolerance.

    Args:
        golden_lines: Expected lines.
        output_lines: Actual lines.
        tolerance: Maximum allowed absolute difference for numeric values.
    """
    if len(golden_lines) != len(output_lines):
        return False

    number_re = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")

    for g_line, o_line in zip(golden_lines, output_lines):
        if g_line == o_line:
            continue

        g_tokens = _tokenize(g_line, number_re)
        o_tokens = _tokenize(o_line, number_re)

        if len(g_tokens) != len(o_tokens):
            return False

        for g_tok, o_tok in zip(g_tokens, o_tokens):
            g_is_num, g_val = g_tok
            o_is_num, o_val = o_tok

            if g_is_num and o_is_num:
                if abs(float(g_val) - float(o_val)) > tolerance:
                    return False
            elif g_val != o_val:
                return False

    return True


def _tokenize(line: str, number_re: re.Pattern):
    """Split a line into (is_numeric, token_str) pairs."""
    tokens = []
    last = 0
    for m in number_re.finditer(line):
        if m.start() > last:
            text = line[last:m.start()]
            if text:
                tokens.append((False, text))
        tokens.append((True, m.group()))
        last = m.end()
    if last < len(line):
        text = line[last:]
        if text:
            tokens.append((False, text))
    return tokens
