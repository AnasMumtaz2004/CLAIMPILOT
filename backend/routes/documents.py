from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import User
from services.auth_service import require_customer
from services.claim_service import get_own_claim
from services.document_service import list_claim_documents
from services.document_service import open_claim_document
from services.document_service import run_document_ocr_task
from services.document_service import upload_claim_document

router = APIRouter(prefix="/customer", dependencies=[Depends(require_customer)])


@router.get("/claims/{claim_id}/documents")
def get_documents(claim_id: str, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Get all documents on a claim. The OCR text is never included."""
    claim = get_own_claim(db, claim_id, user)
    return list_claim_documents(db, claim)


@router.post("/claims/{claim_id}/documents")
def upload_document(
    claim_id: str,
    background_tasks: BackgroundTasks,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Upload a document to a claim and start reading it in the background."""
    claim = get_own_claim(db, claim_id, user)
    result = upload_claim_document(db, user, claim, doc_type, file)

    # OCR runs after the response is sent, so the customer does not wait for it
    background_tasks.add_task(run_document_ocr_task, result["id"])
    return result


@router.get("/claims/{claim_id}/documents/{document_id}/file")
def download_document(
    claim_id: str,
    document_id: str,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Return the original file of a document the customer owns."""
    claim = get_own_claim(db, claim_id, user)
    doc, file_path = open_claim_document(db, user, claim, document_id)
    return FileResponse(file_path, media_type=doc.mime_type)