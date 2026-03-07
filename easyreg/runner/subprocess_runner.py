"""Subprocess-based runner: executes commands in isolated sandbox directories."""
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

from ..model import Case, RunResult


class SubprocessRunner:
    """Executes case commands via subprocess in sandbox directories."""

    def run(
        self,
        case: Case,
        output_dir: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunResult:
        """Run a case command in the given output directory.

        Args:
            case: The test case to execute.
            output_dir: Working directory for the command; created if needed.
            env: Additional environment variables (merged with system env).
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Merge env: system env + injected env
        run_env = dict(os.environ)
        if env:
            run_env.update(env)

        timeout = case.timeout

        try:
            proc = subprocess.run(
                case.command,
                shell=True,
                cwd=str(output_dir),
                capture_output=True,
                text=True,
                env=run_env,
                timeout=timeout,
            )
            return RunResult(
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            return RunResult(
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
            )
