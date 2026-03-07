"""JSON config loading, validation, and placeholder management."""
import json
from pathlib import Path
from typing import List

from .model import Suite, Case, DiffRule

REQUIRED_SUITE_FIELDS = ("suite", "golden_dir", "output_dir", "cases")
REQUIRED_CASE_FIELDS = ("name", "command")


def _parse_diff_rule(raw: dict) -> DiffRule:
    return DiffRule(
        type=raw["type"],
        pattern=raw["pattern"],
        replace=raw.get("replace"),
    )


def _parse_diff_rules(raw_list: list) -> List[DiffRule]:
    return [_parse_diff_rule(r) for r in raw_list]


def _parse_case(raw: dict) -> Case:
    for f in REQUIRED_CASE_FIELDS:
        if f not in raw:
            raise ValueError(f"Case missing required field: {f!r}")
    return Case(
        name=raw["name"],
        command=raw["command"],
        input=raw.get("input", ""),
        timeout=raw.get("timeout"),
        diff_rules=_parse_diff_rules(raw.get("diff_rules", [])),
        diff_rules_mode=raw.get("diff_rules_mode", "append"),
    )


def load_config(path: str) -> Suite:
    """Load a JSON config file and return a Suite object."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for f in REQUIRED_SUITE_FIELDS:
        if f not in data:
            raise ValueError(f"Config missing required field: {f!r}")

    return Suite(
        name=data["suite"],
        golden_dir=data["golden_dir"],
        output_dir=data["output_dir"],
        cases=[_parse_case(c) for c in data["cases"]],
        diff_rules=_parse_diff_rules(data.get("diff_rules", [])),
        versions=data.get("versions"),
        env=data.get("env"),
    )
