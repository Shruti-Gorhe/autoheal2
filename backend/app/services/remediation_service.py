from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(
    Path(__file__).resolve().parents[2] / ".env"
)

from app.services.patch_executor import apply_patch
from app.services.isolated_test import run_isolated_test


def _get_repo_path() -> str:
    """
    Repository used for isolated remediation.

    Set ISOLATED_REPO_PATH in .env.
    """

    repo_path = os.getenv("ISOLATED_REPO_PATH", "").strip()

    if not repo_path:
        raise RuntimeError(
            "ISOLATED_REPO_PATH is not configured."
        )

    return repo_path


def execute_remediation(
    fix_result: Any,
) -> dict[str, Any]:
    """
    Apply the Fix Agent's candidate patch to an isolated copy
    and execute the configured test command.

    The original repository is never modified.
    """

    # ------------------------------------------------------------
    # Normalize Fix Agent output
    # ------------------------------------------------------------

    if isinstance(fix_result, str):
        try:
            fix_result = json.loads(fix_result)
        except json.JSONDecodeError:
            return {
                "attempted": False,
                "patch_applied": False,
                "tests_passed": False,
                "error": "Fix Agent output was not valid JSON.",
            }

    if not isinstance(fix_result, dict):
        return {
            "attempted": False,
            "patch_applied": False,
            "tests_passed": False,
            "error": "Fix Agent output is not a JSON object.",
        }

    patch = fix_result.get("patch", "")

    if not patch or not str(patch).strip():
        return {
            "attempted": False,
            "patch_applied": False,
            "tests_passed": False,
            "error": "Fix Agent did not provide a candidate patch.",
        }

    # ------------------------------------------------------------
    # Get repository configuration
    # ------------------------------------------------------------

    try:
        repo_path = _get_repo_path()
    except Exception as exc:
        return {
            "attempted": False,
            "patch_applied": False,
            "tests_passed": False,
            "error": str(exc),
        }

    test_command = os.getenv(
        "ISOLATED_TEST_COMMAND",
        "python -m pytest -q",
    )

    # ------------------------------------------------------------
    # Apply patch in isolated workspace
    # ------------------------------------------------------------

    patch_result = apply_patch(
        repo_path=repo_path,
        patch=str(patch),
    )

    if not patch_result.get("success"):
        return {
            "attempted": True,
            "patch_applied": False,
            "tests_passed": False,
            "patch_error": patch_result.get(
                "error",
                "Patch application failed.",
            ),
            "workspace": patch_result.get("workspace"),
            "repo_workspace": patch_result.get(
                "repo_workspace"
            ),
        }

    # ------------------------------------------------------------
    # Run tests in patched workspace
    # ------------------------------------------------------------

    repo_workspace = patch_result.get(
        "repo_workspace"
    )

    if not repo_workspace:
        return {
            "attempted": True,
            "patch_applied": True,
            "tests_passed": False,
            "error": (
                "Patch was applied but no isolated "
                "repository workspace was returned."
            ),
        }

    test_result = run_isolated_test(
        workspace=repo_workspace,
        test_command=test_command,
    )

    # ------------------------------------------------------------
    # Build validation result
    # ------------------------------------------------------------

    return {
        "attempted": True,
        "patch_applied": True,
        "tests_passed": bool(
            test_result.get("passed", False)
        ),
        "test_execution_success": bool(
            test_result.get("success", False)
        ),
        "exit_code": test_result.get(
            "exit_code",
            -1,
        ),
        "command": test_result.get(
            "command",
            test_command,
        ),
        "stdout": test_result.get(
            "stdout",
            "",
        ),
        "stderr": test_result.get(
            "stderr",
            "",
        ),
        "workspace": patch_result.get(
            "workspace"
        ),
        "repo_workspace": repo_workspace,
        "changed_files": patch_result.get(
            "changed_files",
            [],
        ),
        "patch_verification": patch_result.get(
            "verification",
            [],
        ),
    }