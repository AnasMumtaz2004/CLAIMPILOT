"""Orchestrator-only tools for consolidating specialist results and routing to review."""


def collect_specialist_risk_flags(results):
    """Collect deduplicated flags from all specialist outputs without changing them."""
    flags = []
    for agent_name, result in (results or {}).items():
        for flag in (result.get("flags", []) or result.get("risk_flags", [])):
            flags.append(f"{agent_name}:{str(flag)[:100]}")
    return list(dict.fromkeys(flags))


def build_human_review_route(preparation_status, review_flags):
    """Always route completed agent work to a human officer; never decide the claim."""
    flags = list(review_flags or [])
    if preparation_status != "ready_for_human_review":
        flags.append("approval_preparation_not_ready")
    return {
        "next_action": "pause_for_human_review",
        "reason": "Specialist processing completed. A Claims Officer must review the findings.",
        "review_flags": list(dict.fromkeys(flags)),
        "approval_preparation_status": preparation_status,
    }


TOOLS = {
    "collect_specialist_risk_flags": collect_specialist_risk_flags,
    "build_human_review_route": build_human_review_route,
}
