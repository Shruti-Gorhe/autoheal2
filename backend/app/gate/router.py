from fastapi import APIRouter, HTTPException

from app.gate.models import GateRequest, GateResponse
from app.gate.service import run_remediation_gate


router = APIRouter(
    prefix="/api/gate",
    tags=["CI/CD Gate"],
)


@router.get("/health")
def gate_health():
    return {
        "status": "ok",
        "service": "autoheal-remediation-gate",
    }


@router.post("/check", response_model=GateResponse)
def check_gate(request: GateRequest):
    try:
        return run_remediation_gate(request)
    except Exception as exc:
        # Fail closed: an unavailable remediation gate must not
        # silently allow a failed CI pipeline to continue.
        raise HTTPException(
            status_code=500,
            detail=f"AutoHeal gate failed: {exc}",
        )