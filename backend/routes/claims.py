from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import User
from database.schemas import DraftCreate
from database.schemas import DraftUpdate
from database.schemas import MessageCreate
from services.auth_service import require_customer
from services.claim_service import add_claim_message
from services.claim_service import claim_to_dict
from services.claim_service import create_draft
from services.claim_service import get_claim_config
from services.claim_service import get_own_claim
from services.claim_service import list_claim_messages
from services.claim_service import list_customer_claims
from services.claim_service import list_customer_policies
from services.claim_service import list_status_history
from services.claim_service import respond_to_info_request
from services.claim_service import submit_claim
from services.claim_service import update_draft

router = APIRouter(prefix="/customer", dependencies=[Depends(require_customer)])


@router.get("/claim-config")
def claim_config():
    """Return form fields and document types for each insurance line."""
    return get_claim_config()


@router.get("/policies")
def get_policies(user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Get all policies for the current customer."""
    return list_customer_policies(db, user)


@router.get("/claims")
def get_claims(user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Get all claims, including drafts, for the current customer."""
    return list_customer_claims(db, user)


@router.post("/claims")
def start_draft(body: DraftCreate, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Create a new draft claim."""
    return create_draft(db, user, body)


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Get one claim for the current customer."""
    claim = get_own_claim(db, claim_id, user)
    return claim_to_dict(claim)


@router.patch("/claims/{claim_id}")
def save_draft(
    claim_id: str,
    body: DraftUpdate,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Autosave a draft."""
    return update_draft(db, user, claim_id, body)


@router.post("/claims/{claim_id}/submit")
def submit(claim_id: str, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Submit a draft claim."""
    return submit_claim(db, user, claim_id)


@router.post("/claims/{claim_id}/respond")
def respond(claim_id: str, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Tell the claims team that the requested information has been sent."""
    return respond_to_info_request(db, user, claim_id)


@router.get("/claims/{claim_id}/history")
def get_history(claim_id: str, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Get the customer-visible status history of a claim."""
    claim = get_own_claim(db, claim_id, user)
    return list_status_history(db, claim)


@router.get("/claims/{claim_id}/messages")
def get_messages(claim_id: str, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Get all messages on a claim."""
    claim = get_own_claim(db, claim_id, user)
    return list_claim_messages(db, claim)


@router.post("/claims/{claim_id}/messages")
def post_message(
    claim_id: str,
    body: MessageCreate,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Post a message on a claim."""
    claim = get_own_claim(db, claim_id, user)
    return add_claim_message(db, user, claim, body)