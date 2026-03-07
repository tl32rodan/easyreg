"""Markdown report generator."""
from pathlib import Path
from typing import List

from ..model import CaseResult, Verdict


class MarkdownReporter:
    """Generates a Markdown regression report."""

    def __init__(self, output_path: str):
        self._path = Path(output_path)

    def generate(self, results: List[CaseResult]) -> None:
        """Write a Markdown report from case results."""
        total = len(results)
        passed = sum(1 for r in results if r.verdict == Verdict.PASS)
        failed = sum(1 for r in results if r.verdict == Verdict.FAIL)
        new = sum(1 for r in results if r.verdict == Verdict.NEW)
        errors = sum(1 for r in results if r.verdict == Verdict.ERROR)

        lines = []
        lines.append("# RegressionX Report\n")
        lines.append(
            f"**Total:** {total} | **Passed:** {passed} | "
            f"**Failed:** {failed} | **New:** {new} | **Errors:** {errors}\n"
        )

        # Summary table
        if results:
            lines.append("## Summary\n")
            lines.append("| Case | Status |")
            lines.append("| :--- | :--- |")
            for r in results:
                lines.append(f"| {r.case_name} | {r.verdict.value} |")
            lines.append("")

        # Failure details
        failures = [r for r in results if r.verdict in (Verdict.FAIL, Verdict.ERROR)]
        if failures:
            lines.append("## Failure Details\n")
            for r in failures:
                lines.append(f"### {r.case_name}\n")
                for err in r.errors:
                    lines.append(f"- [Struct] {err}")
                for diff in r.diffs:
                    lines.append(f"- [Content] {diff}")
                if r.run_result and r.run_result.returncode != 0:
                    lines.append(
                        f"- [Exec] Exit code: {r.run_result.returncode}"
                    )
                lines.append("")

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text("\n".join(lines), encoding="utf-8")
