from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

from agents.intake import tools
from agents.intake.config import AGENT_NAME
from agents.intake.config import AGENT_VERSION
from agents.intake.config import EVENT_TYPES
from agents.intake.config import MAX_INCONSISTENCIES
from agents.intake.config import MAX_ITEM_CHARS
from agents.intake.config import MAX_SUMMARY_CHARS
from agents.intake.state import IntakeReview
from agents.prompts.intake import SYSTEM_PROMPT
from agents.prompts.intake import build_user_prompt


def short_text(text, limit):
    """Trim a text to a limit of characters."""
    clean = str(text).strip()
    if len(clean) > limit:
        return clean[: limit - 3] + "..."
    return clean


def load_claim(state, db):
    """Node: load the claim facts. Stops the graph when the claim does not exist."""
    facts = tools.get_claim_details(db, state["claim_id"])
    if facts is None:
        return {"error": "claim_not_found"}
    return {"facts": facts}


def route_after_load(state):
    """Choose the next step after the claim was loaded."""
    if state.get("error"):
        return "stop"
    return "continue"


def check_completeness(state, db):
    """Node: find the missing fields and documents. This is done by code, not by the model."""
    completeness = tools.check_claim_completeness(db, state["claim_id"])
    return {"completeness": completeness}


def classify_event(state, llm):
    """Node: ask the model for the event type, a summary and any contradictions."""
    facts = state["facts"]

    allowed_types = EVENT_TYPES.get(facts["line"], ["other", "unclear"])

    form_lines = []
    for field in facts["form_fields"]:
        value = field["value"]
        if value == "":
            value = "(empty)"
        form_lines.append(field["label"] + ": " + value)

    user_prompt = build_user_prompt(
        facts["line_label"],
        allowed_types,
        facts["loss_date"],
        facts["claimed_amount"],
        facts["description"],
        form_lines,
    )
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]

    model = llm.with_structured_output(IntakeReview)
    review = model.invoke(messages)
    return {"review": review.model_dump()}


def check_policy(facts):
    """Check the policy facts with code: it exists, belongs to the customer, and covers the loss date."""
    policy = facts["policy"]
    result = {"policy_found": policy["found"], "owner_matches": False, "loss_date_in_period": False}

    if not policy["found"]:
        return result

    result["owner_matches"] = policy["owner_matches"]

    if facts["loss_date"]:
        loss_date = datetime.fromisoformat(facts["loss_date"])
        start_date = datetime.fromisoformat(policy["start_date"])
        end_date = datetime.fromisoformat(policy["end_date"])
        result["loss_date_in_period"] = start_date <= loss_date <= end_date

    return result


def build_result(state):
    """Node: join the checks done by code with the model's review and check the model's answer."""
    facts = state["facts"]
    completeness = state["completeness"]
    review = state["review"]

    # The model must choose from the allowed list, anything else becomes 'unclear'
    allowed_types = EVENT_TYPES.get(facts["line"], ["other", "unclear"])
    event_type = str(review["event_type"]).strip().lower()
    if event_type not in allowed_types:
        event_type = "unclear"

    inconsistencies = []
    for item in review["inconsistencies"][:MAX_INCONSISTENCIES]:
        text = short_text(item, MAX_ITEM_CHARS)
        if text:
            inconsistencies.append(text)

    domain_matches = bool(review["domain_matches_description"])
    mismatch_reason = ""
    if not domain_matches:
        mismatch_reason = short_text(review["domain_mismatch_reason"], MAX_ITEM_CHARS)

    policy_check = check_policy(facts)

    # Flags are neutral labels that tell the next step what to look at
    flags = []
    if not policy_check["policy_found"]:
        flags.append("unregistered_policy")
    elif not policy_check["owner_matches"]:
        flags.append("policy_owner_mismatch")
    if policy_check["policy_found"] and not policy_check["loss_date_in_period"]:
        flags.append("loss_date_outside_policy_period")
    if not domain_matches:
        flags.append("domain_mismatch")
    if len(inconsistencies) > 0:
        flags.append("inconsistent_information")
    if event_type == "unclear":
        flags.append("event_unclear")
    if not completeness["is_complete"]:
        flags.append("missing_information")

    # Missing information alone only asks the customer for more, every other flag needs a person to look
    status = "complete"
    if flags == ["missing_information"]:
        status = "incomplete"
    elif len(flags) > 0:
        status = "needs_review"

    result = {
        "agent": AGENT_NAME,
        "agent_version": AGENT_VERSION,
        "claim_id": facts["claim_id"],
        "claim_number": facts["claim_number"],
        "insurance_line": facts["line"],
        "status": status,
        "flags": flags,
        "event_type": event_type,
        "event_summary": short_text(review["event_summary"], MAX_SUMMARY_CHARS),
        "domain_matches_description": domain_matches,
        "domain_mismatch_reason": mismatch_reason,
        "inconsistencies": inconsistencies,
        "policy_check": policy_check,
        "missing_fields": completeness["missing_fields"],
        "missing_documents": completeness["missing_documents"],
        "checklist": {
            "fields": completeness["required_fields"],
            "documents": completeness["required_documents"],
        },
        "document_problems": completeness["document_problems"],
    }
    return {"result": result}