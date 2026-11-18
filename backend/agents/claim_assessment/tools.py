"""Claim Assessment: MCP retrieval/calculation plus specialist numeric validation."""
from mcp_server.client import call_tool
from services.calculation_service import calculate_claim_amount


def get_claim_details(db, claim_id):
    loaded = call_tool(db, "get_claim_details", agent="claim_assessment", claim_id=claim_id)
    return {"claim": loaded["claim"], "policy": loaded["policy_record"]}


def get_claim_documents(db, claim_id):
    listing = call_tool(db, "get_claim_documents", agent="claim_assessment", claim_id=claim_id)
    return [{"document_id": d.get("id"), "doc_type": d.get("doc_type"),
             "mime_type": d.get("mime_type"), "ocr_status": d.get("ocr_status"),
             "extracted": d.get("extracted", {})} for d in listing["documents"]]


def search_guidelines(db, claim_id, insurance_line, query):
    return call_tool(db, "search_claims_guidelines", agent="claim_assessment", claim_id=claim_id, query=query, top_k=8)


def calculate_claim_amount(db, claim_id):
    return call_tool(db, "calculate_claim_amount", agent="claim_assessment", claim_id=claim_id)


def calculate_claim(db, claim_data, policy_data):
    details = claim_data.get("details") or {}
    line_items = details.get("line_items")
    if not isinstance(line_items, list) or not line_items:
        return {"available": False, "reason": "Claim details do not contain bill line_items.", "result": None}
    sum_insured = policy_data.get("sum_insured")
    remaining = max(float(sum_insured) - float(details.get("already_paid", 0) or 0), 0) if sum_insured is not None else None
    try:
        result = calculate_claim_amount(
            line_items=line_items, salvage_value=details.get("salvage_value", 0),
            sum_insured=sum_insured if details.get("value_at_risk") is not None else None,
            value_at_risk=details.get("value_at_risk"), copay_percent=policy_data.get("copay_percent", 0),
            deductible=policy_data.get("deductible", 0), remaining_sum_insured=remaining)
        return {"available": True, "reason": None, "result": result}
    except (TypeError, ValueError, ArithmeticError) as exc:
        return {"available": False, "reason": str(exc), "result": None}


def validate_claim_line_items(line_items):
    """Validate assessment inputs before deterministic calculation."""
    errors = []
    if not isinstance(line_items, list) or not line_items:
        errors.append("At least one line item is required.")
    else:
        for index, item in enumerate(line_items, 1):
            if not isinstance(item, dict):
                errors.append(f"Line item {index} must be an object.")
                continue
            try:
                if float(item.get("amount", 0)) < 0:
                    errors.append(f"Line item {index} has a negative amount.")
            except (TypeError, ValueError):
                errors.append(f"Line item {index} has an invalid amount.")
    return {"valid": not errors, "errors": errors}


def reconcile_claim_calculation(claimed_amount, calculation):
    """Compare claimed and calculated values; this is a review flag, not a decision."""
    if not calculation or not calculation.get("available"):
        return {"comparable": False, "difference": None, "reason": "Calculation is unavailable."}
    result = calculation.get("result") or {}
    payable = result.get("final_payable", result.get("final_amount", result.get("payable_amount")))
    if claimed_amount is None or payable is None:
        return {"comparable": False, "difference": None, "reason": "One amount is missing."}
    difference = round(float(claimed_amount) - float(payable), 2)
    return {"comparable": True, "claimed_amount": float(claimed_amount),
            "calculated_amount": float(payable), "difference": difference,
            "matches": abs(difference) <= 0.01}


LOCAL_TOOLS = {"validate_claim_line_items": validate_claim_line_items,
               "reconcile_claim_calculation": reconcile_claim_calculation}
MCP_TOOLS = {"get_claim_details": get_claim_details, "get_claim_documents": get_claim_documents,
             "search_claims_guidelines": search_guidelines, "calculate_claim_amount": calculate_claim_amount}
TOOLS = {**MCP_TOOLS, **LOCAL_TOOLS}
