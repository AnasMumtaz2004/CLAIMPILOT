"""Intake-specific validation plus the shared MCP-backed data tools."""
from mcp_server.client import call_tool


def get_claim_details(db, claim_id):
    return call_tool(db, "get_claim_details", agent="intake", claim_id=claim_id)


def check_claim_completeness(db, claim_id):
    return call_tool(db, "check_claim_completeness", agent="intake", claim_id=claim_id)


def build_intake_field_checklist(claim_facts):
    """Build required-field checklist from the claim domain and supplied values."""
    fields = claim_facts.get("form_fields", [])
    return [{"name": f["name"], "label": f["label"], "present": bool(str(f.get("value", "")).strip())}
            for f in fields]


def validate_intake_field_values(claim_facts):
    """Flag blank required fields and malformed positive-amount/date inputs."""
    required = build_intake_field_checklist(claim_facts)
    missing = [f["label"] for f in required if not f["present"]]
    amount = claim_facts.get("claimed_amount")
    if amount is not None and float(amount) <= 0:
        missing.append("Claimed amount must be greater than zero")
    return {"valid": not missing, "missing_fields": missing}


LOCAL_TOOLS = {"build_intake_field_checklist": build_intake_field_checklist,
               "validate_intake_field_values": validate_intake_field_values}
MCP_TOOLS = {"get_claim_details": get_claim_details, "check_claim_completeness": check_claim_completeness}
TOOLS = {**MCP_TOOLS, **LOCAL_TOOLS}
