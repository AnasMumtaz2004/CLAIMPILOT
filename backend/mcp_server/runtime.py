"""Shared ClaimPilot tool implementations used by MCP and agent runtimes.

The LangGraph application runs in-process and calls this same allowlisted
registry with its existing SQLAlchemy session. The FastMCP server exposes the
identical handlers over MCP stdio for compatible external clients.
"""
from __future__ import annotations

import logging
from typing import Any

from database.models import Claim, ClaimDocument, Policy, User
from rag.search import search_approval_requirements, search_claims_guidelines, search_customer_policy
from services import claim_service, document_service
from services.calculation_service import calculate_claim_amount as calculate_amount

logger = logging.getLogger("claimpilot.mcp")


def _claim(db, claim_id: str):
    claim = claim_service.get_submitted_claim(db, claim_id)
    if claim is None:
        raise ValueError("Submitted claim was not found.")
    return claim


def get_claim_details(db, claim_id: str) -> dict[str, Any]:
    claim = _claim(db, claim_id)
    policy = db.query(Policy).filter(Policy.id == claim.policy_id).first()
    if policy is None:
        raise ValueError("The claim policy was not found.")
    facts = claim_service.get_claim_facts(db, claim_id)
    customer = db.query(User).filter(User.id == claim.claimant_id).first()
    return {
        **facts,
        "form_fields": [
            {"name": f["name"], "label": f["label"], "value": str((claim.details or {}).get(f["name"], "")).strip()}
            for f in claim_service.DOMAIN_FIELDS.get(claim.line, [])
        ],
        "line_label": claim_service.LINE_LABELS.get(claim.line, claim.line),
        "claim": {
            "id": claim.id, "claim_number": claim.claim_number,
            "claimant_id": claim.claimant_id, "policy_id": claim.policy_id,
            "line": claim.line, "status": claim.status,
            "loss_date": claim.loss_date.isoformat() if claim.loss_date else None,
            "claimed_amount": float(claim.claimed_amount) if claim.claimed_amount is not None else None,
            "description": claim.description, "details": claim.details or {},
        },
        "policy_record": {
            "id": policy.id, "policy_number": policy.policy_number,
            "line": policy.line, "product": policy.product,
            "sum_insured": float(policy.sum_insured),
            "deductible": float(policy.deductible),
            "copay_percent": float(policy.copay_percent),
            "start_date": policy.start_date.isoformat(), "end_date": policy.end_date.isoformat(),
            "terms": policy.terms or {},
        },
    }


def get_customer_policy(db, claim_id: str):
    facts = claim_service.get_claim_facts(db, claim_id)
    if facts is None:
        raise ValueError("Submitted claim was not found.")
    policy = facts["policy"]
    if not policy.get("found") or not policy.get("owner_matches"):
        raise ValueError("The claim's policy could not be verified for this policyholder.")
    policy_row = db.query(Policy).filter(Policy.policy_number == policy["policy_number"]).first()
    return {**policy, "terms": (policy_row.terms or {}) if policy_row is not None else {}}


def search_policy_wording_tool(db, claim_id: str, query: str, top_k: int = 6):
    policy = get_customer_policy(db, claim_id)
    _validate_query(query, top_k)
    return search_customer_policy(db, policy["policy_number"], query, top_k=top_k)


def get_claim_documents(db, claim_id: str):
    claim = _claim(db, claim_id)
    docs = document_service.list_claim_documents(db, claim)
    rows = {d.id: d for d in db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()}
    for item in docs:
        item["label"] = claim_service.DOC_TYPE_LABELS.get(item["doc_type"], item["doc_type"])
        item["extracted"] = (rows[item["id"]].extracted or {}) if item["id"] in rows else {}
    completeness = claim_service.check_claim_completeness(db, claim_id) or {}
    return {
        "documents": sorted(docs, key=lambda d: (d.get("doc_type", ""), d.get("id", ""))),
        "required_documents": completeness.get("required_documents", []),
        "missing_documents": completeness.get("missing_documents", []),
    }


def run_document_ocr(db, claim_id: str, document_id: str):
    _claim(db, claim_id)
    doc = db.query(ClaimDocument).filter(ClaimDocument.id == document_id, ClaimDocument.claim_id == claim_id).first()
    if doc is None:
        raise ValueError("Document does not belong to this claim.")
    return document_service.run_ocr_now(db, document_id)


def extract_document_text(db, claim_id: str, document_id: str):
    _claim(db, claim_id)
    result = document_service.get_ocr_text_for_agent(db, claim_id, document_id)
    if result is None:
        raise ValueError("Document does not belong to this claim.")
    return result


def check_claim_completeness(db, claim_id: str):
    result = claim_service.check_claim_completeness(db, claim_id)
    if result is None:
        raise ValueError("Submitted claim was not found.")
    return result


def _validate_query(query: str, top_k: int):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("query must contain between 1 and 2000 characters")
    if not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20")


def search_claims_guidelines_tool(db, claim_id: str, query: str, top_k: int = 8):
    facts = claim_service.get_claim_facts(db, claim_id)
    if facts is None:
        raise ValueError("Submitted claim was not found.")
    _validate_query(query, top_k)
    return search_claims_guidelines(db, facts["line"], query, top_k=top_k)


def calculate_claim_amount_tool(db, claim_id: str):
    loaded = get_claim_details(db, claim_id)
    details, policy = loaded["claim"]["details"], loaded["policy_record"]
    line_items = details.get("line_items")
    if not isinstance(line_items, list) or not line_items:
        return {"available": False, "reason": "Claim details do not contain bill line_items.", "result": None}
    already_paid = float(details.get("already_paid", 0) or 0)
    sum_insured = policy.get("sum_insured")
    remaining = max(float(sum_insured) - already_paid, 0) if sum_insured is not None else None
    try:
        result = calculate_amount(
            line_items=line_items, salvage_value=details.get("salvage_value", 0),
            sum_insured=sum_insured if details.get("value_at_risk") is not None else None,
            value_at_risk=details.get("value_at_risk"),
            copay_percent=policy.get("copay_percent", 0), deductible=policy.get("deductible", 0),
            remaining_sum_insured=remaining,
        )
        return {"available": True, "reason": None, "result": result}
    except (TypeError, ValueError, ArithmeticError) as exc:
        return {"available": False, "reason": str(exc), "result": None}


def get_approval_requirements(db, claim_id: str, query: str, top_k: int = 8):
    facts = claim_service.get_claim_facts(db, claim_id)
    if facts is None:
        raise ValueError("Submitted claim was not found.")
    _validate_query(query, top_k)
    return search_approval_requirements(db, facts["line"], query, top_k=top_k)


HANDLERS = {
    "get_claim_details": get_claim_details,
    "get_customer_policy": get_customer_policy,
    "search_policy_wording": search_policy_wording_tool,
    "get_claim_documents": get_claim_documents,
    "run_document_ocr": run_document_ocr,
    "extract_document_text": extract_document_text,
    "check_claim_completeness": check_claim_completeness,
    "search_claims_guidelines": search_claims_guidelines_tool,
    "calculate_claim_amount": calculate_claim_amount_tool,
    "get_approval_requirements": get_approval_requirements,
}


def call_tool(db, name: str, **arguments):
    """Invoke an allowlisted MCP handler using the caller's request-scoped DB session."""
    handler = HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"MCP tool is not allowlisted: {name}")
    logger.info("MCP tool invoked: %s", name)
    return handler(db, **arguments)
