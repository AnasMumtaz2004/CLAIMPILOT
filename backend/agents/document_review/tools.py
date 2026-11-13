from services import claim_service
from services import document_service


def get_claim_details(db, claim_id):
    """Tool: return the claim facts (form values, loss date, amount, policyholder). None if not found."""
    return claim_service.get_claim_facts(db, claim_id)


def sort_key(document):
    """Sort documents by type and then by ID, so every run reads them in the same order."""
    return (document["doc_type"], document["id"])


def get_claim_documents(db, claim_id):
    """Tool: return the documents of a claim and which required documents are missing. None if not found."""
    claim = claim_service.get_submitted_claim(db, claim_id)
    if claim is None:
        return None

    documents = document_service.list_claim_documents(db, claim)
    for document in documents:
        document["label"] = claim_service.DOC_TYPE_LABELS.get(document["doc_type"], document["doc_type"])

    completeness = claim_service.check_claim_completeness(db, claim_id)
    return {
        "documents": sorted(documents, key=sort_key),
        "required_documents": completeness["required_documents"],
        "missing_documents": completeness["missing_documents"],
    }


def run_ocr(db, document_id):
    """Tool: read a document that has not been read yet. Returns the new OCR status."""
    return document_service.run_ocr_now(db, document_id)


def get_document_text(db, claim_id, document_id):
    """Tool: return the OCR pages of one document of the claim. None if there is no such document."""
    return document_service.get_ocr_text_for_agent(db, claim_id, document_id)


# Every tool of this agent, by name. A test checks that this matches agent.yaml
TOOLS = {
    "get_claim_details": get_claim_details,
    "get_claim_documents": get_claim_documents,
    "run_ocr": run_ocr,
    "get_document_text": get_document_text,
}