"""CLI entry point for RegressionX."""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

from .config import load_config
from .comparator import compare_directories
from .comparator.diff_rules import resolve_effective_rules
from .golden import GoldenManager
from .model import Case, CaseResult, Suite, Verdict
from .reporter.json_reporter import JsonReporter
from .reporter.markdown import MarkdownReporter
from .runner.subprocess_runner import SubprocessRunner


def _build_parser():
    parser = argparse.ArgumentParser(description="RegressionX - Regression Testing Platform")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = subparsers.add_parser("run", help="Execute cases and compare with golden")
    run_p.add_argument("--config", required=True)
    run_p.add_argument("--case", default=None, help="Run only this case")
    run_p.add_argument("--report", default="regression_report.md")
    run_p.add_argument("--report-format", dest="report_format",
                       choices=["md", "json"], default="md")
    run_p.add_argument("--parallel", type=int, default=1, metavar="N",
                       help="Number of parallel workers (default: 1)")

    # compare
    cmp_p = subparsers.add_parser("compare", help="Compare existing outputs with golden")
    cmp_p.add_argument("--config", required=True)
    cmp_p.add_argument("--case", default=None)
    cmp_p.add_argument("--report", default="regression_report.md")
    cmp_p.add_argument("--report-format", dest="report_format",
                       choices=["md", "json"], default="md")

    # promote
    pro_p = subparsers.add_parser("promote", help="Promote output to golden")
    pro_p.add_argument("--config", required=True)
    pro_p.add_argument("--case", default=None, help="Promote only this case")

    # golden
    gld_p = subparsers.add_parser("golden", help="Golden reference management")
    gld_p.add_argument("--config", required=True)
    gld_p.add_argument("--status", action="store_true", help="Show golden status")

    return parser


def _resolve_path(template: str, **kwargs) -> Path:
    result = template
    for key, val in kwargs.items():
        result = result.replace(f"{{{key}}}", str(val))
    return Path(result)


def _make_reporter(report_path: str, fmt: str):
    if fmt == "json":
        return JsonReporter(report_path)
    return MarkdownReporter(report_path)


def _run_single_case(case: Case, suite: Suite, runner: SubprocessRunner) -> CaseResult:
    """Execute and compare a single case. Thread-safe."""
    output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
    golden_dir = _resolve_path(suite.golden_dir, case=case.name)
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

    effective_rules = resolve_effective_rules(
        suite.diff_rules, case.diff_rules, case.diff_rules_mode,
    )
    cmp = compare_directories(golden_dir, output_dir, diff_rules=effective_rules)

    if cmp.match:
        return CaseResult(case_name=case.name, verdict=Verdict.PASS)
    return CaseResult(
        case_name=case.name, verdict=Verdict.FAIL,
        diffs=cmp.diffs, errors=cmp.errors,
    )


def _execute_cases(cases: List[Case], suite: Suite, parallel: int) -> List[CaseResult]:
    """Execute cases sequentially or in parallel."""
    runner = SubprocessRunner()

    if parallel <= 1:
        return [_run_single_case(case, suite, runner) for case in cases]

    # Parallel execution — preserve original case order in results
    results: List[CaseResult] = [None] * len(cases)  # type: ignore
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        future_to_idx = {
            executor.submit(_run_single_case, case, suite, runner): idx
            for idx, case in enumerate(cases)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
    return results


def _cmd_run(args):
    suite = load_config(args.config)
    cases = suite.cases
    if args.case:
        cases = [c for c in cases if c.name == args.case]

    parallel = getattr(args, "parallel", 1)
    results = _execute_cases(cases, suite, parallel)

    reporter = _make_reporter(args.report, getattr(args, "report_format", "md"))
    reporter.generate(results)

    has_failures = any(r.verdict in (Verdict.FAIL, Verdict.ERROR) for r in results)
    return 1 if has_failures else 0


def _cmd_compare(args):
    suite = load_config(args.config)
    cases = suite.cases
    if args.case:
        cases = [c for c in cases if c.name == args.case]

    results = []
    for case in cases:
        output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
        golden_dir = _resolve_path(suite.golden_dir, case=case.name)

        if not golden_dir.is_dir():
            results.append(CaseResult(case_name=case.name, verdict=Verdict.NEW))
            continue

        effective_rules = resolve_effective_rules(
            suite.diff_rules, case.diff_rules, case.diff_rules_mode,
        )
        cmp = compare_directories(golden_dir, output_dir, diff_rules=effective_rules)

        if cmp.match:
            results.append(CaseResult(case_name=case.name, verdict=Verdict.PASS))
        else:
            results.append(CaseResult(
                case_name=case.name, verdict=Verdict.FAIL,
                diffs=cmp.diffs, errors=cmp.errors,
            ))

    reporter = _make_reporter(args.report, getattr(args, "report_format", "md"))
    reporter.generate(results)

    has_failures = any(r.verdict == Verdict.FAIL for r in results)
    return 1 if has_failures else 0


def _cmd_promote(args):
    suite = load_config(args.config)
    cases = suite.cases
    if args.case:
        cases = [c for c in cases if c.name == args.case]

    if "{case}" in suite.golden_dir:
        golden_root = Path(suite.golden_dir.split("{case}")[0].rstrip("/"))
    else:
        golden_root = Path(suite.golden_dir)

    mgr = GoldenManager(golden_root)

    for case in cases:
        output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
        mgr.promote(case.name, output_dir)
        print(f"Promoted: {case.name}")

    return 0


def _cmd_golden(args):
    suite = load_config(args.config)

    if "{case}" in suite.golden_dir:
        golden_root = Path(suite.golden_dir.split("{case}")[0].rstrip("/"))
    else:
        golden_root = Path(suite.golden_dir)

    mgr = GoldenManager(golden_root)

    if args.status:
        status = mgr.status()
        if not status:
            print("No golden references found.")
        else:
            for name, exists in status.items():
                print(f"  {name}: {'EXISTS' if exists else 'MISSING'}")
    return 0


COMMANDS = {
    "run": _cmd_run,
    "compare": _cmd_compare,
    "promote": _cmd_promote,
    "golden": _cmd_golden,
}


def main(args=None):
    parser = _build_parser()
    parsed = parser.parse_args(args)

    handler = COMMANDS.get(parsed.command)
    if handler is None:
        parser.error(f"Unknown command: {parsed.command}")

    return handler(parsed)


if __name__ == "__main__":
    sys.exit(main() or 0)
