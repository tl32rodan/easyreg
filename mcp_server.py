#!/usr/bin/env python3
"""RegressionX MCP Server — built with FastMCP.

Usage:
    python mcp_server.py          # stdio transport (default)
    fastmcp run mcp_server.py     # via fastmcp CLI
"""
import os
import sys
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

# Ensure regressionx package is importable when run from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from regressionx.comparator import compare_directories
from regressionx.comparator.diff_rules import resolve_effective_rules
from regressionx.config import load_config
from regressionx.golden import GoldenManager
from regressionx.runner.subprocess_runner import SubprocessRunner


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="regressionx-mcp",
    version="0.2.0",
    instructions=(
        "RegressionX regression testing tools. "
        "Recommended workflow: "
        "1) regressionx_show_config — inspect suite before anything else; "
        "2) regressionx_golden_status — check if golden references exist; "
        "3) regressionx_run — execute cases and compare against golden; "
        "4) regressionx_promote — promote outputs to golden when verdict is NEW."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_path(template: str, **kwargs) -> Path:
    result = template
    for key, val in kwargs.items():
        result = result.replace(f"{{{key}}}", str(val))
    return Path(result)


def _golden_root(suite) -> Path:
    if "{case}" in suite.golden_dir:
        return Path(suite.golden_dir.split("{case}")[0].rstrip("/"))
    return Path(suite.golden_dir)


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
def regressionx_show_config(
    config_path: str,
) -> dict:
    """Inspect a RegressionX suite config file.

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
        "Call this BEFORE regressionx_run to know if golden has been set up. "
        "If a case has no golden yet, running will return verdict=NEW — "
        "you then need regressionx_promote to create it. "
        "HINT: config_path must be a path to a .json file."
    )
)
def regressionx_golden_status(
    config_path: str,
) -> dict:
    """Check which golden references exist for a suite.

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
    """
    suite = load_config(config_path)
    mgr = GoldenManager(_golden_root(suite))
    return {
        "golden_root": str(_golden_root(suite)),
        "cases": mgr.status(),
    }


@mcp.tool(
    description=(
        "Execute regression test cases defined in a suite JSON config, "
        "then compare outputs against golden references. "
        "Returns verdict PASS/FAIL/NEW/ERROR for each case. "
        "PASS = matches golden. "
        "FAIL = differs from golden (check 'diffs' field). "
        "NEW = no golden exists yet (run regressionx_promote to create one). "
        "ERROR = command failed (check 'errors' field). "
        "HINT: If case_name is omitted ALL cases run. "
        "HINT: case_name must exactly match a case 'name' in the config — "
        "use regressionx_show_config first to get the correct names. "
        "HINT: parallel defaults to 1; only increase for independent cases."
    )
)
def regressionx_run(
    config_path: str,
    case_name: Optional[str] = None,
    parallel: int = 1,
) -> dict:
    """Execute cases and compare against golden references.

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
                     Example: 'examples/simple_suite.json'
        case_name:   OPTIONAL. Run only this case. Must exactly match a
                     case 'name' in the config. Omit to run ALL cases.
        parallel:    OPTIONAL. Number of parallel workers. Default is 1.
                     Do NOT pass 0 or negative values.
    """
    suite = load_config(config_path)
    cases = suite.cases

    if case_name is not None:
        cases = [c for c in cases if c.name == case_name]
        if not cases:
            raise ValueError(
                f"No case named '{case_name}' in suite '{suite.name}'. "
                f"Available: {[c.name for c in suite.cases]}"
            )

    runner = SubprocessRunner()
    results = []

    for case in cases:
        output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
        golden_dir = _resolve_path(suite.golden_dir, case=case.name)
        env = dict(suite.env) if suite.env else None

        run_result = runner.run(case, output_dir, env=env)

        if run_result.returncode != 0:
            results.append({
                "case_name": case.name,
                "verdict": "ERROR",
                "diffs": [],
                "errors": [f"Command exited with code {run_result.returncode}: {run_result.stderr.strip()}"],
            })
            continue

        if not golden_dir.is_dir():
            results.append({"case_name": case.name, "verdict": "NEW", "diffs": [], "errors": []})
            continue

        effective_rules = resolve_effective_rules(
            suite.diff_rules, case.diff_rules, case.diff_rules_mode,
        )
        cmp = compare_directories(golden_dir, output_dir, diff_rules=effective_rules)

        if cmp.match:
            results.append({"case_name": case.name, "verdict": "PASS", "diffs": [], "errors": []})
        else:
            results.append({
                "case_name": case.name,
                "verdict": "FAIL",
                "diffs": cmp.diffs,
                "errors": cmp.errors,
            })

    summary = {v: 0 for v in ("PASS", "FAIL", "NEW", "ERROR")}
    for r in results:
        summary[r["verdict"]] += 1

    return {"suite": suite.name, "summary": summary, "results": results}


@mcp.tool(
    description=(
        "Compare existing output directories against golden references "
        "WITHOUT re-executing any commands. "
        "Use this when a previous run already produced outputs and you only "
        "want to re-check the diff — faster than regressionx_run. "
        "HINT: If outputs do not exist yet, use regressionx_run instead. "
        "HINT: case_name must exactly match a case 'name' in the config."
    )
)
def regressionx_compare(
    config_path: str,
    case_name: Optional[str] = None,
) -> dict:
    """Compare existing outputs against golden (no execution).

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
        case_name:   OPTIONAL. Compare only this case. Omit for ALL cases.
    """
    suite = load_config(config_path)
    cases = suite.cases

    if case_name is not None:
        cases = [c for c in cases if c.name == case_name]
        if not cases:
            raise ValueError(
                f"No case named '{case_name}' in suite '{suite.name}'. "
                f"Available: {[c.name for c in suite.cases]}"
            )

    results = []
    for case in cases:
        output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
        golden_dir = _resolve_path(suite.golden_dir, case=case.name)

        if not golden_dir.is_dir():
            results.append({"case_name": case.name, "verdict": "NEW", "diffs": [], "errors": []})
            continue

        effective_rules = resolve_effective_rules(
            suite.diff_rules, case.diff_rules, case.diff_rules_mode,
        )
        cmp = compare_directories(golden_dir, output_dir, diff_rules=effective_rules)

        if cmp.match:
            results.append({"case_name": case.name, "verdict": "PASS", "diffs": [], "errors": []})
        else:
            results.append({
                "case_name": case.name,
                "verdict": "FAIL",
                "diffs": cmp.diffs,
                "errors": cmp.errors,
            })

    return {"suite": suite.name, "results": results}


@mcp.tool(
    description=(
        "Promote current run outputs to become the new golden references. "
        "Call this after regressionx_run returns verdict=NEW (first-time setup) "
        "or after confirming that a FAIL is an intentional change. "
        "WARNING: This OVERWRITES existing golden data. "
        "A .bak backup of the previous golden is kept automatically. "
        "HINT: You must run regressionx_run BEFORE promoting — "
        "promote copies the output directory produced by the last run. "
        "HINT: If case_name is omitted ALL cases are promoted."
    )
)
def regressionx_promote(
    config_path: str,
    case_name: Optional[str] = None,
) -> dict:
    """Promote run outputs to golden references.

    Args:
        config_path: REQUIRED. Path to the suite JSON config file.
        case_name:   OPTIONAL. Promote only this case. Omit to promote ALL.
                     Must exactly match a case 'name' in the config.
    """
    suite = load_config(config_path)
    cases = suite.cases

    if case_name is not None:
        cases = [c for c in cases if c.name == case_name]
        if not cases:
            raise ValueError(
                f"No case named '{case_name}' in suite '{suite.name}'. "
                f"Available: {[c.name for c in suite.cases]}"
            )

    mgr = GoldenManager(_golden_root(suite))
    promoted = []

    for case in cases:
        output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
        mgr.promote(case.name, output_dir)
        promoted.append(case.name)

    return {"promoted": promoted}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
