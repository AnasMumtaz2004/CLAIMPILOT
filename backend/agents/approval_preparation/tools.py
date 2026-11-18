"""Approval preparation tools: MCP retrieval and local human-review packaging."""
from mcp_server.client import call_tool


def get_claim_details(db, claim_id):
    loaded = call_tool(db, "get_claim_details", agent="approval_preparation", claim_id=claim_id)
    return {"claim": loaded["claim"], "policy": loaded["policy_record"]}


def get_claim_documents(db, claim_id):
    listing = call_tool(db, "get_claim_documents", agent="approval_preparation", claim_id=claim_id)
    return [{"document_id": d.get("id"), "doc_type": d.get("doc_type"),
             "mime_type": d.get("mime_type"), "ocr_status": d.get("ocr_status"),
             "extracted": d.get("extracted", {})} for d in listing["documents"]]


def search_approval_guidelines(db, claim_id, insurance_line, query):
    return call_tool(db, "get_approval_requirements", agent="approval_preparation", claim_id=claim_id, query=query, top_k=8)


def check_claim_completeness(claim, documents, intake_result, document_review_result,
                             policy_coverage_result, claim_assessment_result):
    missing, warnings = [], []
    if not claim.get("claim_number"): missing.append("Claim number is missing.")
    if not claim.get("policy_id"): missing.append("Policy reference is missing.")
    if not claim.get("description"): missing.append("Claim description is missing.")
    if claim.get("claimed_amount") is None: missing.append("Claimed amount is missing.")
    if not documents: missing.append("No claim documents have been uploaded.")
    if any(d.get("ocr_status") not in ["completed", "complete", "success"] for d in documents):
        warnings.append("One or more documents have not completed OCR.")
    for label, result in [("Intake", intake_result), ("Document Review", document_review_result),
                          ("Policy Coverage", policy_coverage_result), ("Claim Assessment", claim_assessment_result)]:
        if result.get("status") not in ("complete", "covered", "clear", "ready"):
            warnings.append(f"{label} reported unresolved items or has not completed.")
    calculation = claim_assessment_result.get("calculation") or {}
    if not calculation.get("available", False): warnings.append("The claim calculation is unavailable.")
    return {"complete": not missing and not warnings, "missing_items": missing, "warnings": warnings}


def build_human_review_checklist(claim, documents, deterministic_checks, specialist_results):
    """Create a concise evidence and unresolved-item checklist for the officer."""
    items = []
    for missing in deterministic_checks.get("missing_items", []):
        items.append({"category": "missing_information", "item": str(missing)})
    for warning in deterministic_checks.get("warnings", []):
        items.append({"category": "review_warning", "item": str(warning)})
    for name, result in specialist_results.items():
        for flag in result.get("risk_flags", result.get("flags", [])):
            items.append({"category": name, "item": str(flag)[:300]})
    return {"claim_number": claim.get("claim_number"), "documents_received": len(documents),
            "review_items": items, "human_decision_required": True}


LOCAL_TOOLS = {"check_claim_completeness": check_claim_completeness,
               "build_human_review_checklist": build_human_review_checklist}
MCP_TOOLS = {"get_claim_details": get_claim_details, "get_claim_documents": get_claim_documents,
             "search_approval_requirements": search_approval_guidelines}
TOOLS = {**MCP_TOOLS, **LOCAL_TOOLS}
