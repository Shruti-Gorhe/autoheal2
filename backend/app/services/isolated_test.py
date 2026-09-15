import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def _run(command: list[str], cwd: str, timeout: int = 90):
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def validate_patch(repo_dir: str, patch: str) -> dict:
    if not patch.strip():
        return {"valid": False, "applied": False, "tests_passed": False, "output": "No patch generated."}

    with tempfile.TemporaryDirectory(prefix="autoheal-") as temp:
        worktree = Path(temp) / "repo"
        shutil.copytree(repo_dir, worktree, ignore=shutil.ignore_patterns(".git", "node_modules", ".venv", "__pycache__"))
        patch_file = Path(temp) / "fix.patch"
        patch_file.write_text(patch, encoding="utf-8")

        check = _run(["git", "apply", "--check", str(patch_file)], str(worktree))
        if check.returncode != 0:
            return {"valid": False, "applied": False, "tests_passed": False, "output": check.stderr or check.stdout}

        apply = _run(["git", "apply", str(patch_file)], str(worktree))
        if apply.returncode != 0:
            return {"valid": True, "applied": False, "tests_passed": False, "output": apply.stderr or apply.stdout}

        # Personal-project default: run pytest if present. Otherwise use the configured command.
        command = os.getenv("ISOLATED_TEST_COMMAND", "python -m pytest -q")
        result = subprocess.run(command, cwd=str(worktree), shell=True, text=True, capture_output=True, timeout=120)
        output = (result.stdout + "\n" + result.stderr)[-12000:]
        return {
            "valid": True,
            "applied": True,
            "tests_passed": result.returncode == 0,
            "output": output,
        }
