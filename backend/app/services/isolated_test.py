from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def run_isolated_test(
    workspace: str,
    test_command: str = "python -m pytest -q",
    timeout: int = 120,
) -> dict[str, Any]:
    """
    Run tests inside the isolated remediation workspace.

    The original repository is never touched.
    """

    workspace_path = Path(workspace).resolve()

    if not workspace_path.exists():
        return {
            "success": False,
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": f"Workspace does not exist: {workspace_path}",
        }

    try:
        result = subprocess.run(
            test_command,
            cwd=str(workspace_path),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "success": True,
            "passed": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": test_command,
            "workspace": str(workspace_path),
        }

    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "passed": False,
            "exit_code": -1,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "command": test_command,
            "workspace": str(workspace_path),
            "error": f"Test execution timed out after {timeout} seconds.",
        }

    except Exception as exc:
        return {
            "success": False,
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "command": test_command,
            "workspace": str(workspace_path),
            "error": str(exc),
        }