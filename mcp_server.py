#!/usr/bin/env python3
"""RegressionX MCP (Model Context Protocol) Server.

A stdio-based JSON-RPC 2.0 server that exposes RegressionX functionality
as MCP tools. Designed for integration with AI agents / LLM tool-use.

Zero external dependencies — pure Python stdlib.

Usage:
    python mcp_server.py
"""
import json
import os
import sys
from pathlib import Path

# Ensure regressionx package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from regressionx.config import load_config
from regressionx.comparator import compare_directories
from regressionx.comparator.diff_rules import resolve_effective_rules
from regressionx.golden import GoldenManager
from regressionx.model import Verdict
from regressionx.runner.subprocess_runner import SubprocessRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_path(template: str, **kwargs) -> Path:
    result = template
    for key, val in kwargs.items():
        result = result.replace(f"{{{key}}}", str(val))
    return Path(result)


def _case_result_to_dict(cr):
    return {
        "case_name": cr.case_name,
        "verdict": cr.verdict.value,
        "diffs": cr.diffs,
        "errors": cr.errors,
    }


# ---------------------------------------------------------------------------
# MCP Tool Implementations
# ---------------------------------------------------------------------------

def tool_run_suite(arguments: dict) -> dict:
    """Run regression suite and return verdicts.

    Required: config_path
    Optional: case_name, parallel (default 1)
    """
    config_path = arguments.get("config_path")
    if not config_path:
        return {"error": "config_path is required"}

    case_filter = arguments.get("case_name")
    parallel = int(arguments.get("parallel", 1))

    try:
        suite = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

    cases = suite.cases
    if case_filter:
        cases = [c for c in cases if c.name == case_filter]
        if not cases:
            return {"error": f"No case named '{case_filter}' found in suite"}

    runner = SubprocessRunner()
    results = []
    for case in cases:
        output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
        golden_dir = _resolve_path(suite.golden_dir, case=case.name)
        env = dict(suite.env) if suite.env else None

        run_result = runner.run(case, output_dir, env=env)

        if run_result.returncode != 0:
            from regressionx.model import CaseResult
            results.append({
                "case_name": case.name,
                "verdict": "ERROR",
                "diffs": [],
                "errors": [f"Command exited with code {run_result.returncode}"],
            })
            continue

        if not golden_dir.is_dir():
            results.append({
                "case_name": case.name,
                "verdict": "NEW",
                "diffs": [],
                "errors": [],
            })
            continue

        effective_rules = resolve_effective_rules(
            suite.diff_rules, case.diff_rules, case.diff_rules_mode,
        )
        cmp = compare_directories(golden_dir, output_dir, diff_rules=effective_rules)

        if cmp.match:
            results.append({
                "case_name": case.name,
                "verdict": "PASS",
                "diffs": [],
                "errors": [],
            })
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


def tool_compare(arguments: dict) -> dict:
    """Compare existing outputs with golden (no execution).

    Required: config_path
    Optional: case_name
    """
    config_path = arguments.get("config_path")
    if not config_path:
        return {"error": "config_path is required"}

    case_filter = arguments.get("case_name")

    try:
        suite = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

    cases = suite.cases
    if case_filter:
        cases = [c for c in cases if c.name == case_filter]
        if not cases:
            return {"error": f"No case named '{case_filter}' found in suite"}

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
                "case_name": case.name, "verdict": "FAIL",
                "diffs": cmp.diffs, "errors": cmp.errors,
            })

    return {"suite": suite.name, "results": results}


def tool_promote(arguments: dict) -> dict:
    """Promote current output to golden reference.

    Required: config_path
    Optional: case_name (if omitted, promotes ALL cases)
    """
    config_path = arguments.get("config_path")
    if not config_path:
        return {"error": "config_path is required"}

    case_filter = arguments.get("case_name")

    try:
        suite = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

    cases = suite.cases
    if case_filter:
        cases = [c for c in cases if c.name == case_filter]
        if not cases:
            return {"error": f"No case named '{case_filter}' found in suite"}

    if "{case}" in suite.golden_dir:
        golden_root = Path(suite.golden_dir.split("{case}")[0].rstrip("/"))
    else:
        golden_root = Path(suite.golden_dir)

    mgr = GoldenManager(golden_root)
    promoted = []

    for case in cases:
        output_dir = _resolve_path(suite.output_dir, case=case.name, run_id="latest")
        try:
            mgr.promote(case.name, output_dir)
            promoted.append(case.name)
        except FileNotFoundError as exc:
            return {"error": str(exc), "promoted_before_error": promoted}

    return {"promoted": promoted}


def tool_golden_status(arguments: dict) -> dict:
    """Show which golden references exist.

    Required: config_path
    """
    config_path = arguments.get("config_path")
    if not config_path:
        return {"error": "config_path is required"}

    try:
        suite = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

    if "{case}" in suite.golden_dir:
        golden_root = Path(suite.golden_dir.split("{case}")[0].rstrip("/"))
    else:
        golden_root = Path(suite.golden_dir)

    mgr = GoldenManager(golden_root)
    status = mgr.status()

    return {"golden_root": str(golden_root), "cases": status}


def tool_show_config(arguments: dict) -> dict:
    """Parse and display a suite config for inspection.

    Required: config_path
    """
    config_path = arguments.get("config_path")
    if not config_path:
        return {"error": "config_path is required"}

    try:
        suite = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

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


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOLS = {
    "regressionx_run": {
        "handler": tool_run_suite,
        "description": (
            "Execute regression test cases defined in a suite JSON config, "
            "then compare outputs against golden references. "
            "Returns verdict (PASS/FAIL/NEW/ERROR) for each case."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": (
                        "REQUIRED. Absolute or relative path to the suite JSON "
                        "config file. Example: 'examples/simple_suite.json'"
                    ),
                },
                "case_name": {
                    "type": "string",
                    "description": (
                        "OPTIONAL. Run only this specific case. Must exactly "
                        "match a case 'name' in the config. If omitted, ALL "
                        "cases are run."
                    ),
                },
                "parallel": {
                    "type": "integer",
                    "description": (
                        "OPTIONAL. Number of parallel workers. Default is 1 "
                        "(sequential). Set to 2+ for parallel execution."
                    ),
                    "default": 1,
                },
            },
            "required": ["config_path"],
        },
    },
    "regressionx_compare": {
        "handler": tool_compare,
        "description": (
            "Compare existing output directories against golden references "
            "WITHOUT re-executing any commands. Use this when outputs already "
            "exist and you only want to check differences."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": (
                        "REQUIRED. Absolute or relative path to the suite JSON "
                        "config file."
                    ),
                },
                "case_name": {
                    "type": "string",
                    "description": (
                        "OPTIONAL. Compare only this case. Must exactly match "
                        "a case 'name' in the config."
                    ),
                },
            },
            "required": ["config_path"],
        },
    },
    "regressionx_promote": {
        "handler": tool_promote,
        "description": (
            "Promote current run outputs to become the new golden references. "
            "WARNING: This OVERWRITES existing golden data (a .bak backup is "
            "kept). Only call after confirming that outputs are correct."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": (
                        "REQUIRED. Absolute or relative path to the suite JSON "
                        "config file."
                    ),
                },
                "case_name": {
                    "type": "string",
                    "description": (
                        "OPTIONAL. Promote only this case. If omitted, ALL "
                        "cases are promoted."
                    ),
                },
            },
            "required": ["config_path"],
        },
    },
    "regressionx_golden_status": {
        "handler": tool_golden_status,
        "description": (
            "List all golden reference directories and whether they exist. "
            "Use this to check if golden data has been set up before running "
            "or comparing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": (
                        "REQUIRED. Absolute or relative path to the suite JSON "
                        "config file."
                    ),
                },
            },
            "required": ["config_path"],
        },
    },
    "regressionx_show_config": {
        "handler": tool_show_config,
        "description": (
            "Parse a suite JSON config and return its structured contents. "
            "Use this FIRST to understand what cases, diff rules, and paths "
            "are defined before running or comparing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": (
                        "REQUIRED. Absolute or relative path to the suite JSON "
                        "config file."
                    ),
                },
            },
            "required": ["config_path"],
        },
    },
}


# ---------------------------------------------------------------------------
# MCP Protocol (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

SERVER_INFO = {
    "name": "regressionx-mcp",
    "version": "0.1.0",
}

CAPABILITIES = {
    "tools": {},
}


def _make_response(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _make_error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _handle_request(msg: dict) -> dict | None:
    method = msg.get("method", "")
    id_ = msg.get("id")
    params = msg.get("params", {})

    # --- Lifecycle ---
    if method == "initialize":
        return _make_response(id_, {
            "protocolVersion": "2024-11-05",
            "serverInfo": SERVER_INFO,
            "capabilities": CAPABILITIES,
        })

    if method == "notifications/initialized":
        return None  # notification, no response

    # --- Tool discovery ---
    if method == "tools/list":
        tool_list = []
        for name, spec in TOOLS.items():
            tool_list.append({
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            })
        return _make_response(id_, {"tools": tool_list})

    # --- Tool invocation ---
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name not in TOOLS:
            return _make_response(id_, {
                "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {tool_name}"})}],
                "isError": True,
            })

        try:
            result = TOOLS[tool_name]["handler"](arguments)
            return _make_response(id_, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            })
        except Exception as exc:
            return _make_response(id_, {
                "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                "isError": True,
            })

    # --- Ping ---
    if method == "ping":
        return _make_response(id_, {})

    # Ignore unknown notifications
    if id_ is None:
        return None

    return _make_error(id_, -32601, f"Method not found: {method}")


def main():
    """Run the MCP server, reading JSON-RPC messages from stdin."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = _make_error(None, -32700, "Parse error")
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
            continue

        resp = _handle_request(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
