from datetime import datetime, timezone

from agents.orchestrator import tools


def coordinate(state):
    """
    Consolidate specialist findings and decide the next workflow action.

    The Orchestrator cannot approve, reject, declare fraud or release payment.
    The final decision always belongs to an authorized Claims Officer.
    """

    results = {
        "intake": state.get("intake_result") or {},
        "document_review": state.get("document_review_result") or {},
        "policy_coverage": state.get("policy_coverage_result") or {},
        "claim_assessment": state.get("claim_assessment_result") or {},
        "approval_preparation": state.get(
            "approval_preparation_result"
        ) or {},
    }

    review_flags = tools.collect_specialist_risk_flags(results)

    preparation = results["approval_preparation"]
    preparation_status = preparation.get("preparation_status", "unknown")
    route = tools.build_human_review_route(preparation_status, review_flags)

    return {
        "orchestration": {
            "agent": "orchestrator",
            "agent_version": "1.0.0",
            "claim_id": state["claim_id"],
            "next_action": route["next_action"],
            "reason": route["reason"],
            "review_flags": route["review_flags"],
            "approval_preparation_status": route["approval_preparation_status"],
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    }