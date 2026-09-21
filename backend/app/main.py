import hashlib
import hmac
import os
import subprocess
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.workflow import workflow
from app.services.github_service import GitHubService
from app.observability.telemetry import agent_span
from app.rag.rag_service import rag
from evaluation.evaluate import run as run_evaluation
from app.gate.router import router as gate_router


app = FastAPI(
    title="AutoHeal CI/CD",
    version="0.3.0",
)

app.include_router(gate_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


runs = {}
github = GitHubService()


class PipelineRequest(BaseModel):
    scenario: str = "test_failure"


class DecisionRequest(BaseModel):
    action: str


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "github_configured": github.configured(),
        "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
        "llm_model": os.getenv("LLM_MODEL", "llama3.2"),
        "llm_configured": __import__(
            "app.services.llm_service",
            fromlist=["llm"],
        ).llm.configured,
        "rag": rag.stats(),
    }


# ============================================================
# RAG
# ============================================================

@app.get("/api/rag/stats")
def rag_stats():
    return rag.stats()


@app.post("/api/rag/refresh")
def rag_refresh():
    return rag.refresh()


# ============================================================
# EVALUATION
# ============================================================

@app.post("/api/evaluation/run")
def evaluation_run():
    return run_evaluation()


@app.get("/api/evaluation/results")
def evaluation_results():
    from pathlib import Path
    import json

    path = (
        Path(__file__).resolve().parents[2]
        / "evaluation"
        / "results"
        / "evaluation_summary.json"
    )

    if not path.exists():
        return {
            "status": "not_run",
            "message": "Run POST /api/evaluation/run first.",
        }

    return json.loads(path.read_text())


# ============================================================
# PIPELINE RESULT
# ============================================================

@app.get("/api/pipelines/{pipeline_id}")
def get_pipeline(pipeline_id: str):
    if pipeline_id not in runs:
        raise HTTPException(
            404,
            "Pipeline not found",
        )

    return runs[pipeline_id]


# ============================================================
# LOCAL PIPELINE RUN
# ============================================================

@app.post("/api/pipelines/run")
def run_pipeline(req: PipelineRequest):
    allowed = {"success", "test_failure"}

    if req.scenario not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"scenario must be one of {sorted(allowed)}",
        )

    pipeline_id = f"demo-{uuid4().hex[:8]}"

    # ------------------------------------------------------------
    # LOCAL SAMPLE-REPO CI EXECUTION
    # ------------------------------------------------------------
    sample_repo = (
        Path(__file__).resolve().parents[2]
        / "sample-repo"
    )

    logs = ""

    if req.scenario == "test_failure":
        try:
            import sys

            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=str(sample_repo),
                capture_output=True,
                text=True,
                timeout=120,
            )

            logs = (
                "COMMAND: pytest -q\n"
                f"EXIT CODE: {result.returncode}\n\n"
                "STDOUT:\n"
                f"{result.stdout}\n\n"
                "STDERR:\n"
                f"{result.stderr}"
            )

        except subprocess.TimeoutExpired as exc:
            logs = (
                "COMMAND: pytest -q\n"
                "STATUS: TIMEOUT\n"
                f"STDOUT:\n{exc.stdout or ''}\n"
                f"STDERR:\n{exc.stderr or ''}"
            )

        except Exception as exc:
            logs = (
                "COMMAND: pytest -q\n"
                "STATUS: EXECUTION_ERROR\n"
                f"ERROR: {exc}"
            )

    else:
        logs = (
            "COMMAND: local success scenario\n"
            "STATUS: success\n"
            "No test failure was simulated."
        )

    # ------------------------------------------------------------
    # COLLECT SAMPLE REPO DIFF
    # ------------------------------------------------------------
    diff = ""

    try:
        git_diff = subprocess.run(
            ["git", "diff", "--", "."],
            cwd=str(sample_repo),
            capture_output=True,
            text=True,
            timeout=30,
        )

        diff = git_diff.stdout

    except Exception:
        diff = ""

    # ------------------------------------------------------------
    # RUN ADK AUTOHEAL WORKFLOW
    # ------------------------------------------------------------
    result = workflow.invoke(
        {
            "pipeline_id": pipeline_id,
            "scenario": req.scenario,
            "github": {},
            "logs": logs,
            "diff": diff,
            "validation_result": {},
        }
    )

    runs[pipeline_id] = result

    return result

# ============================================================
# GITHUB ACTIONS WEBHOOK
# ============================================================

async def _process_github_webhook(
    pipeline_id: str,
    scenario: str,
    run: dict,
):
    """Process a GitHub workflow_run event after the webhook is acknowledged."""
    try:
        with agent_span(
            "github-webhook",
            **{
                "pipeline.id": pipeline_id,
                "github.run_id": str(run.get("id")),
            },
        ):
            logs = ""
            diff = ""

            if github.configured():
                try:
                    logs = await github.get_workflow_logs(int(run["id"]))

                    if run.get("head_sha"):
                        diff = await github.get_commit_diff(run.get("head_sha"))

                except Exception as exc:
                    logs = f"Unable to retrieve GitHub logs: {exc}"

            state = await workflow.ainvoke(
                {
                    "pipeline_id": pipeline_id,
                    "scenario": scenario,
                    "github": {
                        "run_id": run.get("id"),
                        "name": run.get("name"),
                        "conclusion": run.get("conclusion"),
                        "head_sha": run.get("head_sha"),
                        "branch": run.get("head_branch"),
                        "html_url": run.get("html_url"),
                    },
                    "logs": logs,
                    "diff": diff,
                    "validation_result": {},
                }
            )

            runs[pipeline_id] = state

    except Exception as exc:
        runs[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "status": "error",
            "error": str(exc),
            "github": {
                "run_id": run.get("id"),
                "name": run.get("name"),
                "conclusion": run.get("conclusion"),
                "head_sha": run.get("head_sha"),
                "branch": run.get("head_branch"),
                "html_url": run.get("html_url"),
            },
        }


@app.post("/api/github/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
):
    body = await request.body()

    secret = os.getenv(
        "GITHUB_WEBHOOK_SECRET",
        "",
    )

    if secret:
        expected = (
            "sha256="
            + hmac.new(
                secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()
        )

        if (
            not x_hub_signature_256
            or not hmac.compare_digest(
                expected,
                x_hub_signature_256,
            )
        ):
            raise HTTPException(
                401,
                "Invalid webhook signature",
            )

    payload = await request.json()

    if x_github_event != "workflow_run":
        return {
            "ignored": True,
            "event": x_github_event,
        }

    action = payload.get("action")
    run = payload.get(
        "workflow_run",
        {},
    )

    if (
        action not in (None, "completed")
        or run.get("status") != "completed"
    ):
        return {
            "ignored": True,
            "reason": "workflow run is not completed",
        }

    pipeline_id = f"gh-{run.get('id')}"

    scenario = (
        "success"
        if run.get("conclusion") == "success"
        else "test_failure"
    )

    runs[pipeline_id] = {
        "pipeline_id": pipeline_id,
        "status": "processing",
        "github": {
            "run_id": run.get("id"),
            "name": run.get("name"),
            "conclusion": run.get("conclusion"),
            "head_sha": run.get("head_sha"),
            "branch": run.get("head_branch"),
            "html_url": run.get("html_url"),
        },
    }

    background_tasks.add_task(
        _process_github_webhook,
        pipeline_id,
        scenario,
        run,
    )

    return {
        "accepted": True,
        "status": "processing",
        "pipeline_id": pipeline_id,
    }


# ============================================================
# HUMAN-IN-THE-LOOP DECISION
# ============================================================

@app.post("/api/pipelines/{pipeline_id}/decision")
def hitl_decision(
    pipeline_id: str,
    req: DecisionRequest,
):

    if pipeline_id not in runs:
        raise HTTPException(
            404,
            "Pipeline not found",
        )

    if req.action not in {
        "approve",
        "reject",
    }:
        raise HTTPException(
            400,
            "action must be approve or reject",
        )

    state = runs[pipeline_id]

    if req.action == "approve":

        state["hitl"] = {
            "status": "approved",
        }

        state["decision"] = (
            "APPROVED_FOR_RELEASE"
        )

    else:

        state["hitl"] = {
            "status": "rejected",
        }

        state["decision"] = "REJECTED"

    return state