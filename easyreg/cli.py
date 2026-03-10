"""CLI entry point for RegressionX."""
import argparse
import sys

from .config import load_config, load_rules_file
from .model import Verdict
from .orchestrator import (
    compare_cases,
    execute_cases,
    filter_cases,
    get_golden_status,
    promote_cases,
)
from .reporter.json_reporter import JsonReporter
from .reporter.markdown import MarkdownReporter


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
    run_p.add_argument("--ignore-rules", dest="ignore_rules", default=None,
                       help="Path to external ignore rules JSON file")

    # compare
    cmp_p = subparsers.add_parser("compare", help="Compare existing outputs with golden")
    cmp_p.add_argument("--config", required=True)
    cmp_p.add_argument("--case", default=None)
    cmp_p.add_argument("--report", default="regression_report.md")
    cmp_p.add_argument("--report-format", dest="report_format",
                       choices=["md", "json"], default="md")
    cmp_p.add_argument("--ignore-rules", dest="ignore_rules", default=None,
                       help="Path to external ignore rules JSON file")

    # promote
    pro_p = subparsers.add_parser("promote", help="Promote output to golden")
    pro_p.add_argument("--config", required=True)
    pro_p.add_argument("--case", default=None, help="Promote only this case")
    pro_p.add_argument("--ignore-rules", dest="ignore_rules", default=None,
                       help="Path to external ignore rules JSON file")

    # golden
    gld_p = subparsers.add_parser("golden", help="Golden reference management")
    gld_p.add_argument("--config", required=True)
    gld_p.add_argument("--status", action="store_true", help="Show golden status")

    return parser


def _load_cli_rules(args):
    """Load rules from --ignore-rules arg if provided."""
    ignore_rules_path = getattr(args, "ignore_rules", None)
    if ignore_rules_path:
        return load_rules_file(ignore_rules_path)
    return None


def _make_reporter(report_path: str, fmt: str):
    if fmt == "json":
        return JsonReporter(report_path)
    return MarkdownReporter(report_path)


def _cmd_run(args):
    suite = load_config(args.config)
    cases = filter_cases(suite, args.case)
    cli_rules = _load_cli_rules(args)

    parallel = getattr(args, "parallel", 1)
    results = execute_cases(cases, suite, parallel, cli_rules=cli_rules)

    reporter = _make_reporter(args.report, getattr(args, "report_format", "md"))
    reporter.generate(results)

    has_failures = any(r.verdict in (Verdict.FAIL, Verdict.ERROR) for r in results)
    return 1 if has_failures else 0


def _cmd_compare(args):
    suite = load_config(args.config)
    cases = filter_cases(suite, args.case)
    cli_rules = _load_cli_rules(args)

    results = compare_cases(cases, suite, cli_rules=cli_rules)

    reporter = _make_reporter(args.report, getattr(args, "report_format", "md"))
    reporter.generate(results)

    has_failures = any(r.verdict == Verdict.FAIL for r in results)
    return 1 if has_failures else 0


def _cmd_promote(args):
    suite = load_config(args.config)
    cases = filter_cases(suite, args.case)
    cli_rules = _load_cli_rules(args)

    promoted = promote_cases(cases, suite, cli_rules=cli_rules)
    for name in promoted:
        print(f"Promoted: {name}")

    return 0


def _cmd_golden(args):
    suite = load_config(args.config)
    status = get_golden_status(suite)

    if args.status:
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
