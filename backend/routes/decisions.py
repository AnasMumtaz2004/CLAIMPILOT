from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import User
from database.schemas import DecisionRequest
from services.auth_service import require_staff
from services.claim_service import get_claim_for_staff
from services.claim_service import list_decisions
from services.claim_service import record_decision
from services.workflow_service import resume_after_human_decision

router = APIRouter(prefix="/decisions", dependencies=[Depends(require_staff)])

@router.post("/claims/{claim_id}/approve")
def approve(
    claim_id: str,
    body: DecisionRequest,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Approve a claim."""
    result = record_decision(db, staff, claim_id, "approve", body)

    resume_after_human_decision(claim_id, "approve")

    return result

@router.post("/claims/{claim_id}/reject")
def reject(
    claim_id: str,
    body: DecisionRequest,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Reject a claim."""
    result = record_decision(db, staff, claim_id, "reject", body)

    resume_after_human_decision(claim_id, "reject")

    return result


@router.post("/claims/{claim_id}/request-info")
def request_info(
    claim_id: str,
    body: DecisionRequest,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Ask the customer for more information."""
    result = record_decision(db, staff, claim_id, "request_info", body)

    resume_after_human_decision(claim_id, "request_info")

    return result


@router.post("/claims/{claim_id}/escalate")
def escalate(
    claim_id: str,
    body: DecisionRequest,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Escalate a claim for specialist review."""
    result = record_decision(db, staff, claim_id, "escalate", body)

    resume_after_human_decision(claim_id, "escalate")

    return result

@router.get("/claims/{claim_id}/history")
def get_history(claim_id: str, db: Session = Depends(get_db)):
    """Get the decision history of a claim."""
    claim = get_claim_for_staff(db, claim_id)
    return list_decisions(db, claim)