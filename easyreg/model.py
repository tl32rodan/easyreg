"""Data models for RegressionX.

Suite, Case, DiffRule, RunResult, Verdict, CaseResult
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


VALID_DIFF_RULE_TYPES = frozenset([
    "ignore_line", "ignore_regex", "ignore_file", "ignore_folder",
    "sort_lines", "tolerance",
])


@dataclass
class DiffRule:
    """A single diff/comparison rule."""
    type: str
    pattern: str
    replace: Optional[str] = None

    def __post_init__(self):
        if self.type not in VALID_DIFF_RULE_TYPES:
            raise ValueError(
                f"Invalid diff rule type: {self.type!r}. "
                f"Valid types: {sorted(VALID_DIFF_RULE_TYPES)}"
            )


@dataclass
class Case:
    """A single regression test case."""
    name: str
    command: str
    input: str
    timeout: Optional[int] = None
    diff_rules: List[DiffRule] = field(default_factory=list)
    diff_rules_mode: str = "append"  # "append" or "override"


@dataclass
class Suite:
    """A collection of regression test cases defined by a JSON config."""
    name: str
    golden_dir: str
    output_dir: str
    cases: List[Case]
    diff_rules: List[DiffRule] = field(default_factory=list)
    ignore_rules_file: Optional[str] = None
    versions: Optional[Dict[str, Dict[str, str]]] = None
    env: Optional[Dict[str, str]] = None


class Verdict(Enum):
    """Result verdict for a single case."""
    PASS = "PASS"
    FAIL = "FAIL"
    NEW = "NEW"
    ERROR = "ERROR"


@dataclass
class RunResult:
    """Result of executing a command."""
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class CaseResult:
    """Full result for a single case after comparison."""
    case_name: str
    verdict: Verdict
    diffs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    run_result: Optional[RunResult] = None
