"""CLI entry point for RegressionX."""
import argparse
import sys
from pathlib import Path

from .config import load_config
from .comparator import compare_directories
from .comparator.diff_rules import resolve_effective_rules
from .golden import GoldenManager
from .model import CaseResult, RunResult, Verdict
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

    # compare
    cmp_p = subparsers.add_parser("compare", help="Compare existing outputs with golden")
    cmp_p.add_argument("--config", required=True)
    cmp_p.add_argument("--case", default=None)
    cmp_p.add_argument("--report", default="regression_report.md")

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
    """Expand placeholders in a path template."""
    result = template
    for key, val in kwargs.items():
        result = result.replace(f"{{{key}}}", str(val))
    return Path(result)


def _cmd_run(args):
    suite = load_config(args.config)
    cases = suite.cases
    if args.case:
        cases = [c for c in cases if c.name == args.case]

    runner = SubprocessRunner()
    golden_mgr = GoldenManager(Path(suite.golden_dir).parent
                                if "{case}" in suite.golden_dir
                                else Path(suite.golden_dir))

    results = []
    for case in cases:
        output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
        golden_dir = _resolve_path(suite.golden_dir, case=case.name)

        # Build env
        env = dict(suite.env) if suite.env else None

        # Execute
        run_result = runner.run(case, output_dir, env=env)

        if run_result.returncode != 0:
            results.append(CaseResult(
                case_name=case.name,
                verdict=Verdict.ERROR,
                errors=[f"Command exited with code {run_result.returncode}"],
                run_result=run_result,
            ))
            continue

        # Check golden
        if not golden_dir.is_dir():
            results.append(CaseResult(
                case_name=case.name, verdict=Verdict.NEW,
            ))
            continue

        # Compare
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

    # Report
    reporter = MarkdownReporter(args.report)
    reporter.generate(results)

    has_failures = any(r.verdict == Verdict.FAIL or r.verdict == Verdict.ERROR
                       for r in results)
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

    reporter = MarkdownReporter(args.report)
    reporter.generate(results)

    has_failures = any(r.verdict == Verdict.FAIL for r in results)
    return 1 if has_failures else 0


def _cmd_promote(args):
    suite = load_config(args.config)
    cases = suite.cases
    if args.case:
        cases = [c for c in cases if c.name == args.case]

    # Determine golden root
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
