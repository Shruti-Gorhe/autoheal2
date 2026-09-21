import uuid
from typing import Any

from app.services.workflow import workflow
from app.gate.models import GateRequest, GateResponse


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def run_remediation_gate(request: GateRequest) -> GateResponse:
    run_id = f"gate-{uuid.uuid4().hex[:10]}"

    state = {
        "pipeline_id": run_id,
        "scenario": "test_failure",
        "logs": request.failure_context or "",
        "diff": "",
        "github": {
            "repository": request.repository,
            "run_id": request.workflow_run_id,
            "head_sha": request.commit_sha,
            "branch": request.branch,
        },
        "metadata": request.metadata,
    }

    result = workflow.invoke(state)

    pipeline = _as_dict(result.get("pipeline"))
    rca = _as_dict(result.get("rca"))
    fix = _as_dict(result.get("fix"))

    decision = str(result.get("decision", "HUMAN_REVIEW"))
    hitl = _as_dict(result.get("hitl"))

    root_cause = rca.get("summary")
    fix_proposed = bool(fix.get("patch") or fix.get("proposal"))

    # Current Fix Agent only proposes a remediation.
    # It does not yet apply the patch or execute tests.
    fix_validated = False
    tests_passed = False

    hitl_required = (
        decision == "HUMAN_REVIEW"
        or hitl.get("status") == "pending"
    )

    if hitl_required:
        gate = "PENDING"
        reason = (
            "AutoHeal generated a candidate remediation, but human approval "
            "is required before release."
        )
    elif decision in {"REJECTED", "FAILED"}:
        gate = "FAIL"
        reason = f"Release decision was {decision}."
    elif pipeline.get("status") == "passed":
        gate = "PASS"
        reason = "Original CI pipeline passed."
    else:
        gate = "FAIL"
        reason = (
            "A remediation was proposed, but the current Fix Agent does not "
            "yet apply and validate the patch automatically."
        )

    return GateResponse(
        gate=gate,
        run_id=run_id,
        repository=request.repository,
        commit_sha=request.commit_sha,
        remediation_attempted=True,
        root_cause=root_cause,
        fix_proposed=fix_proposed,
        fix_validated=fix_validated,
        tests_passed=tests_passed,
        governance_passed=True,
        hitl_required=hitl_required,
        approval=None,
        reason=reason,
        workflow_result=result,
    )