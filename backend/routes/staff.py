from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import User
from database.schemas import StaffNoteCreate
from services.auth_service import require_staff
from services.claim_service import add_staff_note
from services.claim_service import assign_claim_to_staff
from services.claim_service import build_staff_claim_detail
from services.claim_service import get_claim_for_staff
from services.claim_service import get_staff_dashboard
from services.claim_service import list_open_tasks
from services.claim_service import list_staff_claims
from services.document_service import get_document_ocr
from services.document_service import list_claim_documents
from services.document_service import open_claim_document

router = APIRouter(prefix="/staff", dependencies=[Depends(require_staff)])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """Get counts, open tasks and recent activity for the staff dashboard."""
    return get_staff_dashboard(db)


@router.get("/claims")
def get_claims(
    view: str = "all",
    line: str = "",
    search: str = "",
    db: Session = Depends(get_db),
):
    """Get submitted claims, filtered by view, insurance line and search text."""
    return list_staff_claims(db, view, line, search)


@router.get("/claims/{claim_id}")
def get_claim_detail(claim_id: str, db: Session = Depends(get_db)):
    """Get everything needed to review one claim."""
    claim = get_claim_for_staff(db, claim_id)
    detail = build_staff_claim_detail(db, claim)
    detail["documents"] = list_claim_documents(db, claim)
    return detail


@router.get("/claims/{claim_id}/documents/{document_id}/file")
def download_document(
    claim_id: str,
    document_id: str,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Return the original file of a document on a submitted claim."""
    claim = get_claim_for_staff(db, claim_id)
    doc, file_path = open_claim_document(db, staff, claim, document_id)
    return FileResponse(file_path, media_type=doc.mime_type)


@router.get("/claims/{claim_id}/documents/{document_id}/ocr")
def get_document_text(
    claim_id: str,
    document_id: str,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Return the text read from a document, with confidence per page."""
    claim = get_claim_for_staff(db, claim_id)
    return get_document_ocr(db, staff, claim, document_id)


@router.post("/claims/{claim_id}/assign")
def assign_to_me(claim_id: str, staff: User = Depends(require_staff), db: Session = Depends(get_db)):
    """Assign a claim to the logged-in officer."""
    return assign_claim_to_staff(db, staff, claim_id)


@router.post("/claims/{claim_id}/notes")
def add_note(
    claim_id: str,
    body: StaffNoteCreate,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Add a private staff note to a claim."""
    return add_staff_note(db, staff, claim_id, body)


@router.get("/tasks")
def get_tasks(db: Session = Depends(get_db)):
    """Get all open tasks."""
    return list_open_tasks(db)