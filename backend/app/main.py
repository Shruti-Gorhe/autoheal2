import hashlib
import hmac
import os
from uuid import uuid4
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.services.workflow import workflow
from app.services.github_service import GitHubService
from app.observability.telemetry import agent_span
from app.rag.rag_service import rag
from evaluation.evaluate import run as run_evaluation

app = FastAPI(title="AutoHeal CI/CD", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

runs = {}
github = GitHubService()


class PipelineRequest(BaseModel):
    scenario: str = "test_failure"


class DecisionRequest(BaseModel):
    action: str


@app.get("/api/health")
def health():
    return {"status": "ok", "github_configured": github.configured(), "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
        "llm_model": os.getenv("LLM_MODEL", "llama3.2"),
        "llm_configured": __import__("app.services.llm_service", fromlist=["llm"]).llm.configured, "rag": rag.stats()}


@app.get("/api/rag/stats")
def rag_stats():
    return rag.stats()


@app.post("/api/rag/refresh")
def rag_refresh():
    return rag.refresh()


@app.post("/api/evaluation/run")
def evaluation_run():
    return run_evaluation()


@app.get("/api/evaluation/results")
def evaluation_results():
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "evaluation" / "results" / "evaluation_summary.json"
    if not path.exists():
        return {"status": "not_run", "message": "Run POST /api/evaluation/run first."}
    import json
    return json.loads(path.read_text())


@app.get("/api/pipelines/{pipeline_id}")
def get_pipeline(pipeline_id: str):
    if pipeline_id not in runs:
        raise HTTPException(404, "Pipeline not found")
    return runs[pipeline_id]


@app.post("/api/pipelines/run")
def run_pipeline(req: PipelineRequest):
    allowed = {"test_failure", "dependency_failure", "config_failure", "deployment_failure", "success"}
    if req.scenario not in allowed:
        raise HTTPException(400, f"scenario must be one of {sorted(allowed)}")
    pid = f"demo-{uuid4().hex[:8]}"
    result = workflow.invoke({"pipeline_id": pid, "scenario": req.scenario, "logs": "", "diff": ""})
    runs[pid] = result
    return result


@app.post("/api/github/webhook")
async def github_webhook(request: Request, x_hub_signature_256: str | None = Header(default=None), x_github_event: str | None = Header(default=None)):
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not x_hub_signature_256 or not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(401, "Invalid webhook signature")

    payload = await request.json()
    if x_github_event != "workflow_run":
        return {"ignored": True, "event": x_github_event}

    action = payload.get("action")
    run = payload.get("workflow_run", {})
    if action not in (None, "completed") or run.get("status") != "completed":
        return {"ignored": True, "reason": "workflow run is not completed"}

    pipeline_id = f"gh-{run.get('id')}"
    scenario = "success" if run.get("conclusion") == "success" else "test_failure"
    with agent_span("github-webhook", **{"pipeline.id": pipeline_id, "github.run_id": str(run.get("id"))}):
        logs = ""
        diff = ""
        if github.configured():
            try:
                logs = await github.get_workflow_logs(int(run["id"]))
                diff = await github.get_commit_diff(run.get("head_sha", "")) if run.get("head_sha") else ""
            except Exception as exc:
                logs = f"Unable to retrieve GitHub logs: {exc}"

        state = workflow.invoke({
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
        })
        runs[pipeline_id] = state
        return {"accepted": True, "pipeline_id": pipeline_id, "decision": state.get("decision"), "hitl": state.get("hitl")}


@app.post("/api/pipelines/{pipeline_id}/decision")
def hitl_decision(pipeline_id: str, req: DecisionRequest):
    if pipeline_id not in runs:
        raise HTTPException(404, "Pipeline not found")
    if req.action not in {"approve", "reject"}:
        raise HTTPException(400, "action must be approve or reject")
    state = runs[pipeline_id]
    state["hitl"] = {"status": "approved" if req.action == "approve" else "rejected"}
    state["decision"] = "APPROVED_FOR_RELEASE" if req.action == "approve" else "REJECTED"
    return state
