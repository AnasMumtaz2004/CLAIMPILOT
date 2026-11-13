from rag import search
from services import claim_service


def get_claim_details(db, claim_id):
    """Tool: return the claim facts (form values, loss date, amount). None if not found."""
    return claim_service.get_claim_facts(db, claim_id)


def get_customer_policy(db, claim_id):
    """Tool: return the schedule facts of the policy on this claim. None if the claim is not found."""
    facts = claim_service.get_claim_facts(db, claim_id)
    if facts is None:
        return None
    return facts["policy"]


def search_policy_wording(db, policy_number, query, top_k):
    """Tool: search the wording and schedule of ONE policy. Other policies can never be returned."""
    return search.search_customer_policy(db, policy_number, query, top_k)


# Every tool of this agent, by name. A test checks that this matches agent.yaml
TOOLS = {
    "get_claim_details": get_claim_details,
    "get_customer_policy": get_customer_policy,
    "search_policy_wording": search_policy_wording,
}