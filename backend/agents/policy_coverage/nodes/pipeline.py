import re
from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

from agents.document_review.checks import quote_in_text
from agents.document_review.checks import value_in_quote
from agents.policy_coverage import tools
from agents.policy_coverage.config import ADD_ON_STATUSES
from agents.policy_coverage.config import AGENT_NAME
from agents.policy_coverage.config import AGENT_VERSION
from agents.policy_coverage.config import ASSESSMENTS
from agents.policy_coverage.config import MAX_ADD_ONS
from agents.policy_coverage.config import MAX_CLAUSE_CHARS_IN_PROMPT
from agents.policy_coverage.config import MAX_CLAUSES
from agents.policy_coverage.config import MAX_EVENT_TEXT_CHARS
from agents.policy_coverage.config import MAX_EXPLANATION_CHARS
from agents.policy_coverage.config import MAX_QUOTE_CHARS
from agents.policy_coverage.config import QUERIES
from agents.policy_coverage.config import RESULTS_PER_QUERY
from agents.policy_coverage.config import SCHEDULE_QUERY
from agents.policy_coverage.config import TOPICS
from agents.policy_coverage.config import TOPIC_NAMES
from agents.policy_coverage.state import CoverageReview
from agents.prompts.policy_coverage import SYSTEM_PROMPT
from agents.prompts.policy_coverage import build_user_prompt
from services.claim_service import LINE_LABELS


def short_text(text, limit):
    """Trim a text to a limit of characters."""
    clean = str(text).strip()
    if len(clean) > limit:
        return clean[: limit - 3] + "..."
    return clean


def format_amount(amount):
    """Write an amount with thousands separators and two decimals."""
    return f"{float(amount):,.2f}"


# ---------------------------------------------------------------------------
# Step 1 and 2: load the claim and the policy schedule, then check them with code
# ---------------------------------------------------------------------------


def load_inputs(state, db):
    """Node: load the claim facts and the policy schedule. Stops when the claim does not exist."""
    facts = tools.get_claim_details(db, state["claim_id"])
    if facts is None:
        return {"error": "claim_not_found"}

    schedule = tools.get_customer_policy(db, state["claim_id"])
    return {"facts": facts, "schedule": schedule}


def route_after_load(state):
    """Choose the next step after the claim was loaded."""
    if state.get("error"):
        return "stop"
    return "continue"


def check_schedule(state):
    """Node: check the policy facts with code. The model never does dates or amounts."""
    facts = state["facts"]
    schedule = state["schedule"]

    checks = {
        "policy_found": schedule["found"],
        "line_matches": False,
        "loss_date_in_period": False,
        "days_since_policy_start": None,
        "claim_within_sum_insured": None,
    }

    if not schedule["found"]:
        return {"checks": checks}

    checks["line_matches"] = schedule["line"] == facts["line"]

    if facts["loss_date"]:
        loss_date = datetime.fromisoformat(facts["loss_date"])
        start_date = datetime.fromisoformat(schedule["start_date"])
        end_date = datetime.fromisoformat(schedule["end_date"])
        period_check = tools.check_policy_period(facts["loss_date"], schedule["start_date"], schedule["end_date"])
        checks["loss_date_in_period"] = period_check["valid"]
        checks["days_since_policy_start"] = (loss_date.date() - start_date.date()).days

    if facts["claimed_amount"] is not None:
        checks["claim_within_sum_insured"] = facts["claimed_amount"] <= schedule["sum_insured"]

    condition_check = tools.compare_claim_with_policy_conditions(facts.get("details", {}), schedule.get("terms", {}))
    checks["policy_condition_mismatches"] = condition_check["mismatches"]
    return {"checks": checks}


# ---------------------------------------------------------------------------
# Step 3: find the clauses of this customer's policy
# ---------------------------------------------------------------------------


def clean_words(text):
    """Keep only letters, numbers and spaces, so free text cannot add odd characters to a search."""
    return re.sub(r"[^A-Za-z0-9 ]", " ", str(text)).strip()


def build_event_text(facts, intake):
    """Write a short event text from the intake event type and the form fields. Used for the search."""
    parts = []

    event_type = str(intake.get("event_type", ""))
    if event_type != "" and event_type != "unclear":
        parts.append(event_type.replace("_", " "))

    for key in ["diagnosis", "loss_type"]:
        value = clean_words(str(facts["details"].get(key, "")).replace("_", " "))
        if value != "":
            parts.append(value)

    text = " ".join(parts).strip()
    if text == "":
        return "the reported event"
    return text[:MAX_EVENT_TEXT_CHARS]


def retrieve_clauses(state, db):
    """Node: search the customer's own policy once for the schedule and once for each topic."""
    schedule = state["schedule"]
    if not schedule["found"]:
        return {"clauses": []}

    policy_number = schedule["policy_number"]
    line_queries = QUERIES.get(state["facts"]["line"], {})
    event_text = build_event_text(state["facts"], state.get("intake", {}))

    queries = [SCHEDULE_QUERY]
    for topic in TOPIC_NAMES:
        template = line_queries.get(topic)
        if template is not None:
            queries.append(template.replace("{event}", event_text))

    clauses = []
    seen_ids = []
    for query in queries:
        results = tools.search_policy_wording(db, state["claim_id"], policy_number, query, RESULTS_PER_QUERY)
        for result in results:
            # Safety check: text of any other policy is never used, even if a search returned it
            if result["policy_number"] != policy_number:
                continue
            if result["chunk_id"] in seen_ids:
                continue
            if len(clauses) >= MAX_CLAUSES:
                continue

            seen_ids.append(result["chunk_id"])
            clauses.append({
                "ref": len(clauses) + 1,
                "chunk_id": result["chunk_id"],
                "citation": result["citation"],
                "heading": result["heading"],
                "clause_number": result["clause_number"],
                "clause_code": result["clause_code"],
                "page_number": result["page_number"],
                "text": result["text"],
            })

    return {"clauses": clauses}


# ---------------------------------------------------------------------------
# Step 4: ask the model for clause-backed findings
# ---------------------------------------------------------------------------


def build_fact_lines(state):
    """Write the facts that the system calculated, so the model does not have to."""
    facts = state["facts"]
    schedule = state["schedule"]
    checks = state["checks"]

    lines = [
        f"Date of loss: {facts['loss_date']}",
        f"Policy start date: {schedule['start_date']}",
        f"Policy end date: {schedule['end_date']}",
        f"Days from policy start to date of loss: {checks['days_since_policy_start']}",
        f"Claimed amount: {format_amount(facts['claimed_amount'])}",
        f"Sum insured: {format_amount(schedule['sum_insured'])}",
        f"Deductible in the schedule: {format_amount(schedule['deductible'])}",
        f"Co-payment in the schedule: {schedule['copay_percent']}%",
    ]
    return lines


def analyze_coverage(state, llm):
    """Node: ask the model for one finding for each topic. It is skipped when no clauses were found."""
    if len(state["clauses"]) == 0:
        return {"review": None}

    facts = state["facts"]
    schedule = state["schedule"]
    intake = state.get("intake", {})

    event_type = str(intake.get("event_type", "")).strip()
    if event_type == "":
        event_type = "unknown"

    claim_lines = []
    for key, value in facts["details"].items():
        text = str(value).strip()
        if text != "":
            claim_lines.append(key.replace("_", " ") + ": " + text)

    user_prompt = build_user_prompt(
        LINE_LABELS.get(facts["line"], facts["line"]),
        schedule["product"],
        schedule["policy_number"],
        event_type.replace("_", " "),
        "\n".join(claim_lines),
        build_fact_lines(state),
        TOPICS,
        state["clauses"],
        MAX_CLAUSE_CHARS_IN_PROMPT,
    )
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]

    model = llm.with_structured_output(CoverageReview)
    review = model.invoke(messages)
    return {"review": review.model_dump()}


# ---------------------------------------------------------------------------
# Step 5: check every citation and quote with code
# ---------------------------------------------------------------------------


def find_clause(clauses, ref):
    """Return the retrieved clause with this number, or None."""
    for clause in clauses:
        if clause["ref"] == ref:
            return clause
    return None


def valid_citations(clauses, numbers):
    """Keep only the clause numbers that were really retrieved, once each."""
    kept = []
    for number in numbers:
        if isinstance(number, int) and find_clause(clauses, number) is not None and number not in kept:
            kept.append(number)
    return kept


def quote_is_in_clauses(clauses, numbers, quote):
    """Return True if the quote is found in the text of one of the cited clauses."""
    for number in numbers:
        clause = find_clause(clauses, number)
        if quote_in_text(quote, clause["text"]):
            return True
    return False


def check_one_finding(finding, clauses):
    """Check one finding. A finding that supports or limits coverage needs a real citation and a real quote."""
    assessment = str(finding["assessment"]).strip().lower()
    if assessment not in ASSESSMENTS:
        assessment = "needs_more_information"

    citations = valid_citations(clauses, finding["citations"])
    quote = str(finding["evidence_quote"]).strip()
    explanation = short_text(finding["explanation"], MAX_EXPLANATION_CHARS)

    verified = None
    downgraded = False
    if assessment in ["supports_coverage", "limits_coverage"]:
        if len(citations) > 0 and quote_is_in_clauses(clauses, citations, quote):
            verified = True
        else:
            verified = False
            downgraded = True
            assessment = "needs_more_information"
            explanation = "The model did not give a citation and exact quote that could be checked. " + explanation

    checked = {
        "topic": str(finding["topic"]).strip(),
        "assessment": assessment,
        "verified": verified,
        "explanation": explanation.strip(),
        "citations": citations,
        "evidence_quote": short_text(quote, MAX_QUOTE_CHARS),
    }
    return checked, downgraded


def check_add_ons(review, clauses):
    """Keep only the add-ons that are named in a schedule clause, with a real quote."""
    add_ons = []
    dropped = 0

    for add_on in review["add_ons"][:MAX_ADD_ONS]:
        status = str(add_on["status"]).strip().lower()
        clause = find_clause(clauses, add_on["citation"]) if isinstance(add_on["citation"], int) else None

        # An add-on only counts when the schedule (section 1) names it
        valid = clause is not None and str(clause["clause_number"]).startswith("1.")
        valid = valid and status in ADD_ON_STATUSES
        valid = valid and quote_in_text(add_on["evidence_quote"], clause["text"] if clause else "")
        valid = valid and value_in_quote(add_on["name"], add_on["evidence_quote"])

        if not valid:
            dropped += 1
            continue

        add_ons.append({
            "name": short_text(add_on["name"], MAX_QUOTE_CHARS),
            "status": status,
            "citation": add_on["citation"],
            "evidence_quote": short_text(add_on["evidence_quote"], MAX_QUOTE_CHARS),
        })

    return add_ons, dropped


def verify_findings(state):
    """Node: check every finding and add-on, and make sure there is one finding for each topic."""
    clauses = state["clauses"]
    review = state["review"]
    notes = []
    findings = []
    seen_topics = []
    any_downgraded = False

    if review is not None:
        for finding in review["findings"]:
            topic = str(finding["topic"]).strip()
            if topic not in TOPIC_NAMES or topic in seen_topics:
                notes.append(f"A finding with the topic '{short_text(topic, 40)}' was ignored.")
                continue
            seen_topics.append(topic)

            checked, downgraded = check_one_finding(finding, clauses)
            if downgraded:
                any_downgraded = True
            findings.append(checked)

    # Every topic must have a finding, so a topic the model skipped shows up as unknown
    for topic in TOPIC_NAMES:
        if topic in seen_topics:
            continue
        reason = "The policy clauses that were found did not answer this topic."
        if len(clauses) == 0:
            reason = "No wording was found for this policy."
        findings.append({
            "topic": topic,
            "assessment": "needs_more_information",
            "verified": None,
            "explanation": reason,
            "citations": [],
            "evidence_quote": "",
        })

    add_ons = []
    if review is not None:
        add_ons, dropped = check_add_ons(review, clauses)
        if dropped > 0:
            notes.append(f"{dropped} add-on(s) were ignored because the schedule does not show them with a real quote.")

    if any_downgraded:
        notes.append("Some findings were changed to needs_more_information because their citation could not be checked.")

    return {"findings": findings, "add_ons": add_ons, "notes": notes}


# ---------------------------------------------------------------------------
# Step 6: build the result
# ---------------------------------------------------------------------------


def build_result(state):
    """Node: collect the confirmed facts, the findings and the flags into the final result."""
    facts = state["facts"]
    schedule = state["schedule"]
    checks = state["checks"]
    clauses = state["clauses"]
    findings = state["findings"]
    add_ons = state["add_ons"]

    flags = []
    if not checks["policy_found"]:
        flags.append("policy_not_found")
    else:
        if not checks["line_matches"]:
            flags.append("policy_line_mismatch")
        if not checks["loss_date_in_period"]:
            flags.append("policy_not_active_on_loss_date")
        if checks["claim_within_sum_insured"] is False:
            flags.append("claim_exceeds_sum_insured")
    if len(clauses) == 0:
        flags.append("policy_wording_not_found")

    has_limit = False
    has_unknown = False
    has_unsupported = False
    for finding in findings:
        if finding["assessment"] == "limits_coverage":
            has_limit = True
        if finding["assessment"] == "needs_more_information":
            has_unknown = True
        if finding["verified"] is False:
            has_unsupported = True
    if has_limit:
        flags.append("limiting_clause_found")
    if has_unknown and len(clauses) > 0:
        flags.append("coverage_uncertain")
    if has_unsupported:
        flags.append("unsupported_finding")

    # The summary describes what was found. It is not a decision
    summary = "no_limitations_found"
    if "policy_not_found" in flags or "policy_line_mismatch" in flags or "policy_not_active_on_loss_date" in flags:
        summary = "policy_conditions_not_met"
    elif has_limit:
        summary = "limitations_found"
    elif has_unknown:
        summary = "uncertain"

    status = "complete"
    if len(flags) > 0:
        status = "needs_review"

    # The full clause text is kept only for clauses that a checked finding or add-on cites
    cited_refs = []
    for finding in findings:
        if finding["verified"]:
            cited_refs.extend(finding["citations"])
    for add_on in add_ons:
        cited_refs.append(add_on["citation"])

    clause_results = []
    for clause in clauses:
        entry = {
            "ref": clause["ref"],
            "chunk_id": clause["chunk_id"],
            "citation": clause["citation"],
            "heading": clause["heading"],
            "clause_number": clause["clause_number"],
            "clause_code": clause["clause_code"],
            "page_number": clause["page_number"],
            "cited": clause["ref"] in cited_refs,
        }
        if entry["cited"]:
            entry["text"] = clause["text"]
        clause_results.append(entry)

    unknowns = []
    for finding in findings:
        if finding["assessment"] == "needs_more_information":
            unknowns.append(finding["topic"])

    policy_number = None
    schedule_facts = None
    if schedule["found"]:
        policy_number = schedule["policy_number"]
        schedule_facts = {
            "policy_number": schedule["policy_number"],
            "product": schedule["product"],
            "sum_insured": schedule["sum_insured"],
            "deductible": schedule["deductible"],
            "copay_percent": schedule["copay_percent"],
            "start_date": schedule["start_date"],
            "end_date": schedule["end_date"],
        }

    result = {
        "agent": AGENT_NAME,
        "agent_version": AGENT_VERSION,
        "claim_id": facts["claim_id"],
        "claim_number": facts["claim_number"],
        "insurance_line": facts["line"],
        "policy_number": policy_number,
        "status": status,
        "coverage_summary": summary,
        "flags": flags,
        "schedule": schedule_facts,
        "checks": checks,
        "findings": findings,
        "add_ons": add_ons,
        "clauses": clause_results,
        "unknowns": unknowns,
        "notes": state["notes"],
    }
    return {"result": result}