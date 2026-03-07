"""JSON report generator for CI integration."""
import json
from pathlib import Path
from typing import List

from ..model import CaseResult, Verdict


class JsonReporter:
    """Generates a JSON regression report suitable for CI consumption."""

    def __init__(self, output_path: str):
        self._path = Path(output_path)

    def generate(self, results: List[CaseResult]) -> None:
        total = len(results)
        passed = sum(1 for r in results if r.verdict == Verdict.PASS)
        failed = sum(1 for r in results if r.verdict == Verdict.FAIL)
        new = sum(1 for r in results if r.verdict == Verdict.NEW)
        errors = sum(1 for r in results if r.verdict == Verdict.ERROR)
        passed_overall = failed == 0 and errors == 0

        cases = []
        for r in results:
            entry = {
                "name": r.case_name,
                "verdict": r.verdict.value,
                "diffs": r.diffs,
                "errors": r.errors,
            }
            if r.run_result is not None:
                entry["returncode"] = r.run_result.returncode
            cases.append(entry)

        report = {
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "new": new,
                "errors": errors,
                "passed_overall": passed_overall,
            },
            "cases": cases,
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
