from __future__ import annotations

import difflib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class PatchExecutor:
    """
    Safely applies an AI-generated unified diff inside an isolated
    temporary copy of the target repository.

    The original repository is never modified.
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()

    def _run(
        self,
        command: list[str],
        cwd: Path,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _git_root(self) -> Path:
        result = self._run(
            ["git", "rev-parse", "--show-toplevel"],
            self.repo_path,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Could not determine Git repository root.\n"
                f"{result.stderr.strip()}"
            )

        return Path(result.stdout.strip()).resolve()

    def _copy_repo_to_temp(self) -> tuple[Path, Path]:
        """
        Preserve the repository's path relative to the Git root.

        Example:

        Git root:
            C:/project

        Repo:
            C:/project/sample-repo

        Temporary workspace:
            temp/sample-repo
        """

        git_root = self._git_root()

        try:
            repo_relative = self.repo_path.relative_to(git_root)
        except ValueError as exc:
            raise RuntimeError(
                f"Repository {self.repo_path} is not inside Git root {git_root}"
            ) from exc

        temp_root = Path(
            tempfile.mkdtemp(prefix="autoheal-remediation-")
        )

        temp_repo = temp_root / repo_relative

        temp_repo.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copytree(
            self.repo_path,
            temp_repo,
            dirs_exist_ok=True,
        )

        return temp_root, temp_repo

    def _clean_patch(self, patch: str) -> str:
        """
        Remove common Markdown fencing accidentally returned by an LLM.
        """

        patch = patch.strip()

        if patch.startswith("```"):
            lines = patch.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            patch = "\n".join(lines)

        return patch.strip() + "\n"

    def _parse_file_patch(self, patch: str) -> tuple[str, str, list[str]]:
        """
        Parse a standard unified diff and return:

        old_path
        new_path
        diff_lines
        """

        lines = patch.splitlines()

        old_path = None
        new_path = None

        for line in lines:
            if line.startswith("--- "):
                old_path = line[4:].strip().split("\t")[0]

            elif line.startswith("+++ "):
                new_path = line[4:].strip().split("\t")[0]

            if old_path and new_path:
                break

        if not old_path or not new_path:
            raise ValueError(
                "Patch does not contain valid --- and +++ file paths."
            )

        diff_start = None

        for index, line in enumerate(lines):
            if line.startswith("@@ "):
                diff_start = index
                break

        if diff_start is None:
            raise ValueError(
                "Patch does not contain a unified-diff hunk."
            )

        return (
            old_path,
            new_path,
            lines[diff_start:],
        )

    def _normalize_path(self, path: str) -> Path:
        """
        Convert Git-style paths into paths relative to the temporary
        workspace.

        a/sample-repo/calculator.py
        b/sample-repo/calculator.py

        become:

        sample-repo/calculator.py
        """

        path = path.strip()

        if path.startswith("a/") or path.startswith("b/"):
            path = path[2:]

        if path == "/dev/null":
            return Path(path)

        return Path(path)

    def _apply_single_file_diff(
        self,
        temp_repo: Path,
        patch: str,
    ) -> list[str]:
        """
        Apply a unified diff using Python's difflib.

        This avoids Git's repository/index assumptions in the
        temporary workspace.
        """

        old_path, new_path, diff_lines = self._parse_file_patch(patch)

        old_path = self._normalize_path(old_path)
        new_path = self._normalize_path(new_path)

        if old_path == Path("/dev/null"):
            target = temp_repo / new_path

            if target.exists():
                raise RuntimeError(
                    f"Patch wants to create existing file: {target}"
                )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            new_lines: list[str] = []

            for line in diff_lines:
                if line.startswith("@@"):
                    continue

                if line.startswith("+"):
                    new_lines.append(line[1:] + "\n")

            target.write_text(
                "".join(new_lines),
                encoding="utf-8",
            )

            return [str(new_path)]

        if new_path == Path("/dev/null"):
            target = temp_repo / old_path

            if not target.exists():
                raise RuntimeError(
                    f"Patch wants to delete missing file: {target}"
                )

            target.unlink()

            return [str(old_path)]

        old_file = temp_repo / old_path
        new_file = temp_repo / new_path

        if not old_file.exists():
            raise FileNotFoundError(
                f"Patch target does not exist: {old_file}"
            )

        original_text = old_file.read_text(
            encoding="utf-8"
        )

        original_lines = original_text.splitlines(
            keepends=True
        )

        output_lines: list[str] = []

        old_index = 0

        i = 0

        while i < len(diff_lines):
            line = diff_lines[i]

            if line.startswith("@@"):
                match = re.match(
                    r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
                    line,
                )

                if not match:
                    raise ValueError(
                        f"Invalid unified diff hunk: {line}"
                    )

                old_start = int(match.group(1))

                target_index = old_start - 1

                while old_index < target_index:
                    if old_index >= len(original_lines):
                        raise RuntimeError(
                            "Patch context extends beyond target file."
                        )

                    output_lines.append(
                        original_lines[old_index]
                    )

                    old_index += 1

                i += 1

                while i < len(diff_lines):
                    hunk_line = diff_lines[i]

                    if hunk_line.startswith("@@"):
                        break

                    if hunk_line.startswith(" "):
                        expected = hunk_line[1:]

                        if old_index >= len(original_lines):
                            raise RuntimeError(
                                "Patch context does not match target file."
                            )

                        actual = original_lines[old_index]

                        if actual.rstrip("\r\n") != expected:
                            raise RuntimeError(
                                "Patch context does not match target file.\n"
                                f"Expected: {expected!r}\n"
                                f"Actual:   {actual.rstrip(chr(10) + chr(13))!r}"
                            )

                        output_lines.append(actual)
                        old_index += 1

                    elif hunk_line.startswith("-"):
                        expected = hunk_line[1:]

                        if old_index >= len(original_lines):
                            raise RuntimeError(
                                "Patch removal extends beyond target file."
                            )

                        actual = original_lines[old_index]

                        if actual.rstrip("\r\n") != expected:
                            raise RuntimeError(
                                "Patch removal does not match target file.\n"
                                f"Expected: {expected!r}\n"
                                f"Actual:   {actual.rstrip(chr(10) + chr(13))!r}"
                            )

                        old_index += 1

                    elif hunk_line.startswith("+"):
                        output_lines.append(
                            hunk_line[1:] + "\n"
                        )

                    elif hunk_line.startswith("\\"):
                        # Handles:
                        # \ No newline at end of file
                        pass

                    else:
                        raise ValueError(
                            f"Unexpected diff line: {hunk_line!r}"
                        )

                    i += 1

                continue

            i += 1

        while old_index < len(original_lines):
            output_lines.append(
                original_lines[old_index]
            )
            old_index += 1

        new_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        new_file.write_text(
            "".join(output_lines),
            encoding="utf-8",
        )

        return [str(new_path)]

    def execute(
        self,
        patch: str,
    ) -> dict[str, Any]:

        temp_root = None

        try:
            if not patch or not patch.strip():
                return {
                    "success": False,
                    "error": "No patch supplied.",
                }

            patch = self._clean_patch(patch)

            temp_root, temp_repo = self._copy_repo_to_temp()

            changed_files = self._apply_single_file_diff(
                temp_repo,
                patch,
            )

            verification = []

            for relative_file in changed_files:
                file_path = temp_repo / relative_file

                if file_path.exists():
                    verification.append(
                        {
                            "file": relative_file,
                            "exists": True,
                            "content_preview": file_path.read_text(
                                encoding="utf-8"
                            )[:1000],
                        }
                    )
                else:
                    verification.append(
                        {
                            "file": relative_file,
                            "exists": False,
                        }
                    )

            return {
                "success": True,
                "workspace": str(temp_root),
                "repo_workspace": str(temp_repo),
                "changed_files": changed_files,
                "verification": verification,
            }

        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "workspace": str(temp_root) if temp_root else None,
            }


def apply_patch(
    repo_path: str,
    patch: str,
) -> dict[str, Any]:
    """
    Convenience function used by the workflow.
    """

    executor = PatchExecutor(repo_path)

    return executor.execute(patch)