"""Document Review tools: MCP document access and local evidence validation."""
from database.models import ClaimDocument
from mcp_server.client import call_tool


def get_claim_details(db, claim_id):
    return call_tool(db, "get_claim_details", agent="document_review", claim_id=claim_id)


def sort_key(document):
    return (document.get("doc_type", ""), document.get("id", document.get("document_id", "")))


def get_claim_documents(db, claim_id):
    data = call_tool(db, "get_claim_documents", agent="document_review", claim_id=claim_id)
    return {**data, "documents": sorted(data["documents"], key=sort_key)}


def run_ocr(db, document_id):
    doc = db.query(ClaimDocument).filter(ClaimDocument.id == document_id).first()
    if doc is None:
        raise ValueError("Document was not found.")
    return call_tool(db, "run_document_ocr", agent="document_review", claim_id=doc.claim_id, document_id=document_id)


def get_document_text(db, claim_id, document_id):
    return call_tool(db, "extract_document_text", agent="document_review", claim_id=claim_id, document_id=document_id)


def verify_extracted_quote(ocr_text, quote):
    """Return whether an extracted quote is actually present in OCR source text."""
    source, candidate = str(ocr_text or ""), str(quote or "").strip()
    return {"verified": bool(candidate) and candidate in source, "quote": candidate[:500]}


def compare_document_facts(claim_facts, extracted_facts):
    """Compare matching normalized values and return discrepancies for human review."""
    discrepancies = []
    for key, extracted in (extracted_facts or {}).items():
        if key not in (claim_facts or {}) or extracted in (None, ""):
            continue
        claimed = str(claim_facts[key]).strip().casefold()
        observed = str(extracted).strip().casefold()
        if claimed and observed and claimed != observed:
            discrepancies.append({"field": key, "claim_value": claim_facts[key], "document_value": extracted})
    return {"matches": not discrepancies, "discrepancies": discrepancies}


LOCAL_TOOLS = {"verify_extracted_quote": verify_extracted_quote, "compare_document_facts": compare_document_facts}
MCP_TOOLS = {"get_claim_details": get_claim_details, "get_claim_documents": get_claim_documents,
             "run_ocr": run_ocr, "get_document_text": get_document_text}
TOOLS = {**MCP_TOOLS, **LOCAL_TOOLS}
