import asyncio
import json
import os
from typing import Any

from google.adk.agents import Agent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.observability.telemetry import agent_span
from app.rag.rag_service import rag

APP_NAME = "autoheal_adk"
USER_ID = "autoheal-system"


def _model():
    model = os.getenv("LLM_MODEL", "llama3.2")
    return LiteLlm(
        model=f"ollama/{model}",
        api_base=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def retrieve_ci_knowledge(query: str) -> str:
    """Search the local AutoHeal troubleshooting knowledge base for CI failure evidence."""
    with agent_span("rag-retrieval", query=query[:500]) as span:
        results = rag.retrieve(query)
        span.set_attribute("rag.result_count", str(len(results)))
        return rag.format_context(results)


pipeline_agent = Agent(
    name="pipeline_agent",
    model=_model(),
    instruction="""You are the Pipeline Analysis Agent. Normalize the CI failure into JSON.
Use session variables scenario, github, logs and diff. Return ONLY JSON with keys:
status, stage, run_id, commit, branch, failure_summary.
If scenario is success or github conclusion is success, status is passed; otherwise failed.""",
    output_key="pipeline_json",
)

rag_agent = Agent(
    name="rag_retrieval_agent",
    model=_model(),
    instruction="""You are the RAG Retrieval Agent. You MUST call retrieve_ci_knowledge using a concise
query derived from the scenario, logs and diff. Return the retrieved troubleshooting context.""",
    tools=[retrieve_ci_knowledge],
    output_key="rag_context",
)

rca_agent = Agent(
    name="rca_agent",
    model=_model(),
    instruction="""You are the Root Cause Analysis Agent. Analyze the normalized pipeline, GitHub logs,
commit diff and retrieved RAG context. Return ONLY JSON with keys:
summary, confidence, evidence, likely_files. confidence must be 0..1.
Do not propose a fix yet.
Pipeline: {pipeline_json}
Scenario: {scenario}
Logs: {logs}
Diff: {diff}
RAG context: {rag_context}""",
    output_key="rca_json",
)

fix_agent = Agent(
    name="fix_agent",
    model=_model(),
    instruction="""You are the Fix Agent. Based on the RCA and evidence, propose a minimal candidate
remediation. Return ONLY JSON with keys: proposal, patch, validation_plan.
Never claim tests passed unless an actual test result is present.
RCA: {rca_json}
Logs: {logs}
Diff: {diff}""",
    output_key="fix_json",
)

release_agent = Agent(
    name="release_decision_agent",
    model=_model(),
    instruction="""You are the Release Decision Agent. You are a governance layer, not a deployment executor.
Return ONLY JSON with keys: decision, rationale, hitl_required.
Require HUMAN_REVIEW unless the original pipeline passed. A proposed fix alone is never sufficient for automatic release.
Pipeline: {pipeline_json}
Fix: {fix_json}""",
    output_key="release_json",
)

root_agent = SequentialAgent(
    name="autoheal_workflow",
    sub_agents=[pipeline_agent, rag_agent, rca_agent, fix_agent, release_agent],
)

_session_service = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=_session_service)


def _json_or_text(value: str) -> Any:
    if not value:
        return {}
    cleaned = value.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return value


def _build_result(state: dict[str, Any], session) -> dict[str, Any]:
    s = session.state or {}
    pipeline = _json_or_text(s.get("pipeline_json", ""))
    rca = _json_or_text(s.get("rca_json", ""))
    fix = _json_or_text(s.get("fix_json", ""))
    release = _json_or_text(s.get("release_json", ""))
    if not isinstance(pipeline, dict):
        pipeline = {"raw": pipeline}
    if not isinstance(rca, dict):
        rca = {"summary": rca, "confidence": 0.0, "evidence": [], "likely_files": []}
    if not isinstance(fix, dict):
        fix = {"proposal": fix, "patch": "", "validation_plan": ""}
    if not isinstance(release, dict):
        release = {"decision": "HUMAN_REVIEW", "rationale": release, "hitl_required": True}
    decision = release.get("decision", "HUMAN_REVIEW")
    return {
        **state,
        "pipeline": pipeline,
        "rag_context": s.get("rag_context", ""),
        "rca": rca,
        "fix": fix,
        "decision": decision,
        "hitl": {"status": "pending" if decision == "HUMAN_REVIEW" else "not_required"},
    }


def invoke_workflow(state: dict[str, Any]) -> dict[str, Any]:
    pipeline_id = state["pipeline_id"]

    with agent_span(
        "adk-autoheal-workflow",
        **{"pipeline.id": pipeline_id, "framework": "google-adk"},
    ):
        async def run():
            await _session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=pipeline_id,
                state=dict(state),
            )
            content = types.Content(
                role="user",
                parts=[types.Part(text=f"Process AutoHeal pipeline {pipeline_id} using the session state.")],
            )
            async for _event in _runner.run_async(
                user_id=USER_ID,
                session_id=pipeline_id,
                new_message=content,
            ):
                pass
            session = await _session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=pipeline_id,
            )
            return _build_result(state, session)

        return asyncio.run(run())


class _WorkflowAdapter:
    def invoke(self, state):
        return invoke_workflow(state)


workflow = _WorkflowAdapter()
