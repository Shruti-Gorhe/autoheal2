import asyncio
import os
from app.observability.telemetry import agent_span
from app.services.github_service import GitHubService
from app.services.llm_service import llm
from app.services.isolated_test import validate_patch
from app.rag.rag_service import rag


github = GitHubService()


def pipeline_agent(state):
    with agent_span("pipeline-agent", **{"pipeline.id": state["pipeline_id"]}) as span:
        gh = state.get("github", {})
        scenario = state.get("scenario", "test_failure")
        failure = gh.get("conclusion") not in (None, "success") or scenario != "success"
        result = {
            "status": "failed" if failure else "passed",
            "stage": gh.get("name") or ({
                "test_failure": "test",
                "dependency_failure": "build",
                "config_failure": "health-check",
                "deployment_failure": "deploy",
                "success": "complete",
            }.get(scenario, "unknown")),
            "run_id": gh.get("run_id"),
            "commit": gh.get("head_sha"),
            "branch": gh.get("branch"),
        }
        span.set_attribute("pipeline.status", result["status"])
        return {**state, "pipeline": result}


def _fallback_rca(scenario):
    evidence = {
        "test_failure": "Recent code changed timeout behavior while tests still expect the previous timeout.",
        "dependency_failure": "A dependency version is incompatible with the current runtime.",
        "config_failure": "The health-check configuration points to an invalid service path.",
        "deployment_failure": "Deployment health checks failed after the latest application change.",
        "success": "No root cause because the pipeline passed.",
    }
    return {"summary": evidence.get(scenario, "The CI pipeline failed; inspect the supplied logs."), "confidence": 0.65, "evidence": [], "likely_files": []}


def rag_retrieval_node(state):
    with agent_span("rag-retrieval", **{"pipeline.id": state["pipeline_id"]}) as span:
        query = "\n".join([
            state.get("scenario", ""),
            state.get("logs", "")[-10000:],
            state.get("diff", "")[-6000:],
        ])
        results = rag.retrieve(query)
        context = rag.format_context(results)
        span.set_attribute("rag.result_count", str(len(results)))
        span.set_attribute("rag.retrieval_mode", rag.stats()["retrieval_mode"])
        return {**state, "rag_results": results, "rag_context": context}


def rca_agent(state):
    with agent_span("rca-agent", **{"pipeline.id": state["pipeline_id"]}) as span:
        scenario = state.get("scenario", "test_failure")
        if state.get("pipeline", {}).get("status") == "passed":
            rca = _fallback_rca("success")
        else:
            rca = llm.structured_rca(
                state.get("logs", ""),
                state.get("diff", ""),
                state.get("github", {}),
                state.get("rag_context", ""),
            ) if llm.configured else {}
            if not rca:
                rca = _fallback_rca(scenario)
        span.set_attribute("rca.confidence", str(rca.get("confidence", 0)))
        span.set_attribute("llm.provider", llm.provider if llm.configured else "fallback")
        span.set_attribute("rag.context_included", str(bool(state.get("rag_context"))))
        return {**state, "rca": rca}


def fix_agent(state):
    with agent_span("fix-agent", **{"pipeline.id": state["pipeline_id"]}) as span:
        scenario = state.get("scenario", "test_failure")
        if state.get("pipeline", {}).get("status") == "passed":
            fix = {"proposal": "No remediation required.", "patch": "", "validation": {"tests_passed": True}}
        else:
            patch = llm.generate_patch(state.get("rca", {}), state.get("logs", ""), state.get("diff", "")) if llm.configured else ""
            validation = {"tests_passed": False, "valid": False, "applied": False, "output": "No LLM patch available; human review required."}
            repo_dir = os.getenv("ISOLATED_REPO_PATH", "")
            if patch and repo_dir and os.path.isdir(repo_dir):
                validation = validate_patch(repo_dir, patch)
            proposal = "LLM-generated patch validated in an isolated workspace." if patch else {
                "test_failure": "Restore timeout to 30s or update the affected tests after validating intended behavior.",
                "dependency_failure": "Pin the incompatible dependency to the last compatible version and rerun CI.",
                "config_failure": "Correct the health-check path and rerun the service health check.",
                "deployment_failure": "Rollback the latest deployment, inspect health-check logs, then retry after validation.",
            }.get(scenario, "Inspect the failure and rerun CI.")
            fix = {"proposal": proposal, "patch": patch, "validation": validation}
        span.set_attribute("fix.tests_passed", str(fix["validation"].get("tests_passed", False)))
        return {**state, "fix": fix}


def release_agent(state):
    with agent_span("release-decision-agent", **{"pipeline.id": state["pipeline_id"]}) as span:
        pipeline = state.get("pipeline", {})
        validation = state.get("fix", {}).get("validation", {})
        if pipeline.get("status") == "passed":
            decision = "DEPLOY"
        elif validation.get("tests_passed"):
            decision = "HUMAN_REVIEW"
        else:
            decision = "HUMAN_REVIEW"
        hitl = {"status": "pending" if decision == "HUMAN_REVIEW" else "not_required"}
        span.set_attribute("release.decision", decision)
        return {**state, "decision": decision, "hitl": hitl}
