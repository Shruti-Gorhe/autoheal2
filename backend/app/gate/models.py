from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class GateRequest(BaseModel):
    repository: str
    commit_sha: str
    workflow_run_id: Optional[int] = None
    branch: Optional[str] = None
    build_id: Optional[str] = None
    failure_context: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GateResponse(BaseModel):
    gate: Literal["PASS", "FAIL", "PENDING"]
    run_id: str
    repository: str
    commit_sha: str

    remediation_attempted: bool
    root_cause: Optional[str] = None

    fix_proposed: bool = False
    fix_validated: bool = False
    tests_passed: bool = False

    governance_passed: bool = True
    hitl_required: bool = False
    approval: Optional[str] = None

    reason: str
    trace_id: Optional[str] = None

    workflow_result: dict[str, Any] = Field(default_factory=dict)