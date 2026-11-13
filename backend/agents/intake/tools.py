from services import claim_service


def get_claim_details(db, claim_id):
    """Tool: return the claim facts, with the form fields written as label and value. None if not found."""
    facts = claim_service.get_claim_facts(db, claim_id)
    if facts is None:
        return None

    form_fields = []
    for field in claim_service.DOMAIN_FIELDS.get(facts["line"], []):
        value = str(facts["details"].get(field["name"], "")).strip()
        form_fields.append({"name": field["name"], "label": field["label"], "value": value})

    facts["form_fields"] = form_fields
    facts["line_label"] = claim_service.LINE_LABELS.get(facts["line"], facts["line"])
    return facts


def check_claim_completeness(db, claim_id):
    """Tool: return the missing fields and documents of a claim. None if not found."""
    return claim_service.check_claim_completeness(db, claim_id)


# Every tool of this agent, by name. A test checks that this matches agent.yaml
TOOLS = {
    "get_claim_details": get_claim_details,
    "check_claim_completeness": check_claim_completeness,
}