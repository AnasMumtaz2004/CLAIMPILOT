"""Policy Coverage tools: policy-specific MCP retrieval and local rule checks."""
from datetime import datetime
from mcp_server.client import call_tool


def get_claim_details(db, claim_id):
    return call_tool(db, "get_claim_details", agent="policy_coverage", claim_id=claim_id)


def get_customer_policy(db, claim_id):
    return call_tool(db, "get_customer_policy", agent="policy_coverage", claim_id=claim_id)


def search_policy_wording(db, claim_id, policy_number, query, top_k):
    # The claim-scoped MCP handler independently verifies policy ownership.
    return call_tool(db, "search_policy_wording", agent="policy_coverage", claim_id=claim_id, query=query, top_k=top_k)


def check_policy_period(loss_date, policy_start, policy_end):
    """Deterministically verify whether a loss date falls within policy dates."""
    if not loss_date or not policy_start or not policy_end:
        return {"valid": False, "reason": "A loss date or policy date is missing."}
    loss, start, end = map(lambda x: datetime.fromisoformat(str(x)), (loss_date, policy_start, policy_end))
    return {"valid": start <= loss <= end, "reason": None if start <= loss <= end else "Loss date is outside the policy period."}


def compare_claim_with_policy_conditions(claim_facts, policy_conditions):
    """Identify explicit condition mismatches; never infer coverage from missing terms."""
    mismatches = []
    for key, expected in (policy_conditions or {}).items():
        if key in (claim_facts or {}) and claim_facts[key] not in (None, "") and claim_facts[key] != expected:
            mismatches.append({"condition": key, "claim_value": claim_facts[key], "policy_value": expected})
    return {"status": "needs_review" if mismatches else "no_explicit_mismatch_found", "mismatches": mismatches}


LOCAL_TOOLS = {"check_policy_period": check_policy_period,
               "compare_claim_with_policy_conditions": compare_claim_with_policy_conditions}
MCP_TOOLS = {"get_claim_details": get_claim_details, "get_customer_policy": get_customer_policy,
             "search_policy_wording": search_policy_wording}
TOOLS = {**MCP_TOOLS, **LOCAL_TOOLS}
