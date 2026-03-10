"""Shared orchestration logic for CLI and MCP server."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .comparator import compare_directories
from .comparator.diff_rules import resolve_effective_rules
from .config import load_rules_file
from .golden import GoldenManager
from .model import Case, CaseResult, DiffRule, Suite, Verdict
from .runner.subprocess_runner import SubprocessRunner


def resolve_path(template: str, **kwargs) -> Path:
    """Replace {key} placeholders in a path template."""
    result = template
    for key, val in kwargs.items():
        result = result.replace(f"{{{key}}}", str(val))
    return Path(result)


def golden_root(suite: Suite) -> Path:
    """Extract the golden root directory from a suite's golden_dir template."""
    if "{case}" in suite.golden_dir:
        return Path(suite.golden_dir.split("{case}")[0].rstrip("/"))
    return Path(suite.golden_dir)


def filter_cases(suite: Suite, case_name: Optional[str] = None) -> List[Case]:
    """Filter suite cases by name. Raises ValueError if case_name given but not found."""
    if case_name is None:
        return list(suite.cases)
    cases = [c for c in suite.cases if c.name == case_name]
    if not cases:
        raise ValueError(
            f"No case named '{case_name}' in suite '{suite.name}'. "
            f"Available: {[c.name for c in suite.cases]}"
        )
    return cases


def _load_file_rules(suite: Suite) -> Optional[List[DiffRule]]:
    """Load rules from the suite's ignore_rules_file if set."""
    if suite.ignore_rules_file:
        return load_rules_file(suite.ignore_rules_file)
    return None


def _resolve_rules(
    suite: Suite,
    case: Case,
    cli_rules: Optional[List[DiffRule]] = None,
) -> List[DiffRule]:
    """Resolve effective rules for a case with all layers."""
    return resolve_effective_rules(
        suite.diff_rules,
        case.diff_rules,
        case.diff_rules_mode,
        file_rules=_load_file_rules(suite),
        cli_rules=cli_rules,
    )


def run_single_case(
    case: Case,
    suite: Suite,
    runner: SubprocessRunner,
    cli_rules: Optional[List[DiffRule]] = None,
) -> CaseResult:
    """Execute and compare a single case. Thread-safe."""
    output_dir = resolve_path(suite.output_dir, case=case.name, run_id="latest")
    golden_dir = resolve_path(suite.golden_dir, case=case.name)
    env = dict(suite.env) if suite.env else None

    run_result = runner.run(case, output_dir, env=env)

    if run_result.returncode != 0:
        return CaseResult(
            case_name=case.name,
            verdict=Verdict.ERROR,
            errors=[f"Command exited with code {run_result.returncode}"],
            run_result=run_result,
        )

    if not golden_dir.is_dir():
        return CaseResult(case_name=case.name, verdict=Verdict.NEW)

    effective_rules = _resolve_rules(suite, case, cli_rules)
    cmp = compare_directories(golden_dir, output_dir, diff_rules=effective_rules)

    if cmp.match:
        return CaseResult(case_name=case.name, verdict=Verdict.PASS)
    return CaseResult(
        case_name=case.name, verdict=Verdict.FAIL,
        diffs=cmp.diffs, errors=cmp.errors,
    )


def execute_cases(
    cases: List[Case],
    suite: Suite,
    parallel: int = 1,
    cli_rules: Optional[List[DiffRule]] = None,
) -> List[CaseResult]:
    """Execute cases sequentially or in parallel."""
    runner = SubprocessRunner()

    if parallel <= 1:
        return [run_single_case(case, suite, runner, cli_rules) for case in cases]

    results: List[CaseResult] = [None] * len(cases)  # type: ignore
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        future_to_idx = {
            executor.submit(run_single_case, case, suite, runner, cli_rules): idx
            for idx, case in enumerate(cases)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
    return results


def compare_single_case(
    case: Case,
    suite: Suite,
    cli_rules: Optional[List[DiffRule]] = None,
) -> CaseResult:
    """Compare one case's output against golden (no execution)."""
    output_dir = resolve_path(suite.output_dir, case=case.name, run_id="latest")
    golden_dir = resolve_path(suite.golden_dir, case=case.name)

    if not golden_dir.is_dir():
        return CaseResult(case_name=case.name, verdict=Verdict.NEW)

    effective_rules = _resolve_rules(suite, case, cli_rules)
    cmp = compare_directories(golden_dir, output_dir, diff_rules=effective_rules)

    if cmp.match:
        return CaseResult(case_name=case.name, verdict=Verdict.PASS)
    return CaseResult(
        case_name=case.name, verdict=Verdict.FAIL,
        diffs=cmp.diffs, errors=cmp.errors,
    )


def compare_cases(
    cases: List[Case],
    suite: Suite,
    cli_rules: Optional[List[DiffRule]] = None,
) -> List[CaseResult]:
    """Compare existing outputs against golden for all given cases."""
    return [compare_single_case(case, suite, cli_rules) for case in cases]


def promote_cases(
    cases: List[Case],
    suite: Suite,
    cli_rules: Optional[List[DiffRule]] = None,
) -> List[str]:
    """Promote output dirs to golden for each case. Returns list of promoted names."""
    mgr = GoldenManager(golden_root(suite))
    promoted = []
    for case in cases:
        output_dir = resolve_path(suite.output_dir, case=case.name, run_id="latest")
        effective_rules = _resolve_rules(suite, case, cli_rules)

        metadata_entry = {
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "source_output_dir": str(output_dir),
            "suite_config": {
                "suite": suite.name,
                "golden_dir": suite.golden_dir,
                "output_dir": suite.output_dir,
            },
            "effective_rules": [
                {"type": r.type, "pattern": r.pattern, "replace": r.replace}
                for r in effective_rules
            ],
        }

        mgr.promote_with_rules(case.name, output_dir, effective_rules, metadata_entry)
        promoted.append(case.name)
    return promoted


def get_golden_status(suite: Suite) -> Dict[str, bool]:
    """Return golden existence status for all cases."""
    mgr = GoldenManager(golden_root(suite))
    return mgr.status()
