#!/usr/bin/env python3
"""easyreg MCP Server — built with FastMCP.

Usage:
    python mcp_server.py          # stdio transport (default)
    fastmcp run mcp_server.py     # via fastmcp CLI
"""
import os
import sys
from typing import Optional

from fastmcp import FastMCP

# Ensure regressionx package is importable when run from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from easyreg.config import load_config, load_rules_file
from easyreg.model import CaseResult, Verdict
from easyreg.orchestrator import (
    compare_cases,
    execute_cases,
    filter_cases,
    get_golden_status,
    golden_root,
    promote_cases,
)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="easyreg-mcp",
    version="0.2.0",
    instructions=(
        "easyreg regression testing tools. "
        "Recommended workflow: "
        "1) show_config — inspect suite before anything else; "
        "2) golden_status — check if golden references exist; "
        "3) run — execute cases and compare against golden; "
        "4) promote — promote outputs to golden when verdict is NEW."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _case_result_to_dict(cr: CaseResult) -> dict:
    """Convert a CaseResult dataclass to the MCP dict format."""
    return {
        "case_name": cr.case_name,
        "verdict": cr.verdict.value,
        "diffs": list(cr.diffs),
        "errors": list(cr.errors),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Parse a suite JSON config and return its structured contents. "
        "Use this FIRST to understand what cases, diff_rules, and paths "
        "are defined before running or comparing. "
        "HINT: config_path must end with '.json'. "
        "Example: 'examples/simple_suite.json'."
    )
)
def show_config(
    config_path: str,
) -> dict:
    """Inspect a easyreg suite config file.

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
                     Example: 'examples/simple_suite.json'
    """
    suite = load_config(config_path)
    return {
        "suite_name": suite.name,
        "golden_dir": suite.golden_dir,
        "output_dir": suite.output_dir,
        "global_diff_rules": [
            {"type": r.type, "pattern": r.pattern, "replace": r.replace}
            for r in suite.diff_rules
        ],
        "cases": [
            {
                "name": c.name,
                "command": c.command,
                "input": c.input,
                "timeout": c.timeout,
                "diff_rules_mode": c.diff_rules_mode,
                "diff_rules": [
                    {"type": r.type, "pattern": r.pattern, "replace": r.replace}
                    for r in c.diff_rules
                ],
            }
            for c in suite.cases
        ],
        "env": suite.env,
        "versions": suite.versions,
    }


@mcp.tool(
    description=(
        "List all golden reference directories and whether they exist. "
        "Call this BEFORE run to know if golden has been set up. "
        "If a case has no golden yet, running will return verdict=NEW — "
        "you then need promote to create it. "
        "HINT: config_path must be a path to a .json file."
    )
)
def golden_status(
    config_path: str,
) -> dict:
    """Check which golden references exist for a suite.

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
    """
    suite = load_config(config_path)
    root = golden_root(suite)
    return {
        "golden_root": str(root),
        "cases": get_golden_status(suite),
    }


@mcp.tool(
    description=(
        "Execute regression test cases defined in a suite JSON config, "
        "then compare outputs against golden references. "
        "Returns verdict PASS/FAIL/NEW/ERROR for each case. "
        "PASS = matches golden. "
        "FAIL = differs from golden (check 'diffs' field). "
        "NEW = no golden exists yet (run promote to create one). "
        "ERROR = command failed (check 'errors' field). "
        "HINT: If case_name is omitted ALL cases run. "
        "HINT: case_name must exactly match a case 'name' in the config — "
        "use show_config first to get the correct names. "
        "HINT: parallel defaults to 1; only increase for independent cases."
    )
)
def run(
    config_path: str,
    case_name: Optional[str] = None,
    parallel: int = 1,
    ignore_rules_file: Optional[str] = None,
) -> dict:
    """Execute cases and compare against golden references.

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
                     Example: 'examples/simple_suite.json'
        case_name:   OPTIONAL. Run only this case. Must exactly match a
                     case 'name' in the config. Omit to run ALL cases.
        parallel:    OPTIONAL. Number of parallel workers. Default is 1.
                     Do NOT pass 0 or negative values.
        ignore_rules_file: OPTIONAL. Path to an external ignore rules JSON file.
    """
    suite = load_config(config_path)
    cases = filter_cases(suite, case_name)
    cli_rules = load_rules_file(ignore_rules_file) if ignore_rules_file else None

    results = execute_cases(cases, suite, parallel, cli_rules=cli_rules)

    summary = {v: 0 for v in ("PASS", "FAIL", "NEW", "ERROR")}
    for r in results:
        summary[r.verdict.value] += 1

    return {
        "suite": suite.name,
        "summary": summary,
        "results": [_case_result_to_dict(r) for r in results],
    }


@mcp.tool(
    description=(
        "Compare existing output directories against golden references "
        "WITHOUT re-executing any commands. "
        "Use this when a previous run already produced outputs and you only "
        "want to re-check the diff — faster than run. "
        "HINT: If outputs do not exist yet, use run instead. "
        "HINT: case_name must exactly match a case 'name' in the config."
    )
)
def compare(
    config_path: str,
    case_name: Optional[str] = None,
    ignore_rules_file: Optional[str] = None,
) -> dict:
    """Compare existing outputs against golden (no execution).

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
        case_name:   OPTIONAL. Compare only this case. Omit for ALL cases.
        ignore_rules_file: OPTIONAL. Path to an external ignore rules JSON file.
    """
    suite = load_config(config_path)
    cases = filter_cases(suite, case_name)
    cli_rules = load_rules_file(ignore_rules_file) if ignore_rules_file else None

    results = compare_cases(cases, suite, cli_rules=cli_rules)

    return {
        "suite": suite.name,
        "results": [_case_result_to_dict(r) for r in results],
    }


@mcp.tool(
    description=(
        "Promote current run outputs to become the new golden references. "
        "Call this after run returns verdict=NEW (first-time setup) "
        "or after confirming that a FAIL is an intentional change. "
        "WARNING: This OVERWRITES existing golden data. "
        "A .bak backup of the previous golden is kept automatically. "
        "HINT: You must run before promoting — "
        "promote copies the output directory produced by the last run. "
        "HINT: If case_name is omitted ALL cases are promoted."
    )
)
def promote(
    config_path: str,
    case_name: Optional[str] = None,
    ignore_rules_file: Optional[str] = None,
) -> dict:
    """Promote run outputs to golden references.

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
        case_name:   OPTIONAL. Promote only this case. Omit to promote ALL.
                     Must exactly match a case 'name' in the config.
        ignore_rules_file: OPTIONAL. Path to an external ignore rules JSON file.
    """
    suite = load_config(config_path)
    cases = filter_cases(suite, case_name)
    cli_rules = load_rules_file(ignore_rules_file) if ignore_rules_file else None

    promoted = promote_cases(cases, suite, cli_rules=cli_rules)

    return {"promoted": promoted}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
