import io
import os
import zipfile
from typing import Any

import httpx


class GitHubService:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.owner = os.getenv("GITHUB_OWNER", "")
        self.repo = os.getenv("GITHUB_REPO", "")
        self.base = "https://api.github.com"

    def configured(self) -> bool:
        return bool(self.token and self.owner and self.repo)

    @property
    def repo_slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def _headers(self):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_workflow_run(self, run_id: int) -> dict[str, Any]:
        url = f"{self.base}/repos/{self.repo_slug}/actions/runs/{run_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def get_workflow_logs(self, run_id: int) -> str:
        """Download the GitHub Actions log archive and return readable text."""
        url = f"{self.base}/repos/{self.repo_slug}/actions/runs/{run_id}/logs"
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            content = response.content

        if content.startswith(b"PK"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                chunks = []
                for name in sorted(archive.namelist()):
                    if name.endswith("/"):
                        continue
                    try:
                        text = archive.read(name).decode("utf-8", errors="replace")
                    except Exception:
                        continue
                    chunks.append(f"===== {name} =====\n{text}")
                return "\n\n".join(chunks)
        return content.decode("utf-8", errors="replace")

    async def get_commit_diff(self, sha: str) -> str:
        url = f"{self.base}/repos/{self.repo_slug}/commits/{sha}"
        headers = self._headers()
        headers["Accept"] = "application/vnd.github.diff"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    async def trigger_workflow(self, workflow_file: str, ref: str = "main", inputs: dict[str, str] | None = None):
        url = f"{self.base}/repos/{self.repo_slug}/actions/workflows/{workflow_file}/dispatches"
        payload = {"ref": ref, "inputs": inputs or {}}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
        return {"triggered": True, "workflow": workflow_file, "ref": ref}
