from agents.claim_assessment import tools
from agents.claim_assessment.config import ASSESSMENT_STATUSES
from agents.claim_assessment.config import GUIDELINE_QUERY_BY_LINE
from agents.claim_assessment.config import MAX_EVIDENCE_QUOTE
from agents.claim_assessment.config import MAX_FINDING_EXPLANATION
from agents.claim_assessment.config import MAX_GUIDELINES
from agents.claim_assessment.config import MAX_GUIDELINE_CHARS
from agents.claim_assessment.state import AssessmentReview
from agents.prompts.claim_assessment import SYSTEM_PROMPT
from agents.prompts.claim_assessment import build_user_prompt


def load_inputs(state, db):
    """Load claim, policy, documents and previous specialist results."""

    try:
        loaded = tools.get_claim_details(db, state["claim_id"])
        documents = tools.get_claim_documents(db, state["claim_id"])

        return {
            "claim": loaded["claim"],
            "policy": loaded["policy"],
            "documents": documents,
        }
    except Exception as error:
        return {"error": str(error)}


def route_after_load(state):
    """Stop the graph when claim information could not be loaded."""

    if state.get("error"):
        return "stop"
    return "continue"


def retrieve_guidelines(state, db):
    """Retrieve internal guideline clauses for the claim's insurance line."""

    line = state["claim"]["line"]
    query = GUIDELINE_QUERY_BY_LINE.get(line)

    if query is None:
        return {"guidelines": []}

    results = tools.search_guidelines(db, state["claim"]["id"], line, query)
    guidelines = []

    for result in results[:MAX_GUIDELINES]:
        text = str(result.get("text", ""))
        if len(text) > MAX_GUIDELINE_CHARS:
            text = text[:MAX_GUIDELINE_CHARS]

        guidelines.append({
            "ref": len(guidelines) + 1,
            "chunk_id": result.get("chunk_id"),
            "citation": result.get("citation", "Unknown source"),
            "heading": result.get("heading") or result.get("section_title") or "",
            "page_number": result.get("page_number"),
            "text": text,
        })

    return {"guidelines": guidelines}


def calculate_amount(state, db):
    """Run the existing calculation service when sufficient line item data exists."""

    line_items = (state["claim"].get("details") or {}).get("line_items", [])
    validation = tools.validate_claim_line_items(line_items)
    if not validation["valid"]:
        result = {"available": False, "reason": "; ".join(validation["errors"]), "result": None}
    else:
        result = tools.calculate_claim_amount(db, state["claim"]["id"])
    reconciliation = tools.reconcile_claim_calculation(state["claim"].get("claimed_amount"), result)
    return {"calculation": result, "calculation_reconciliation": reconciliation}


def analyze_claim(state, llm):
    """Ask the model to assess the claim against the retrieved guidelines."""

    if len(state["guidelines"]) == 0:
        return {
            "review": {
                "findings": [],
                "overall_summary": "No internal claims guideline clauses were retrieved.",
                "missing_information": ["Relevant internal claims guidelines were not found."],
                "risk_flags": ["guidelines_not_found"],
            }
        }

    prompt = build_user_prompt(
        state["claim"],
        state["policy"],
        state["documents"],
        state.get("intake_result", {}),
        state.get("document_review_result", {}),
        state.get("policy_coverage_result", {}),
        state["guidelines"],
    )

    structured_llm = llm.with_structured_output(AssessmentReview)
    response = structured_llm.invoke([
        ("system", SYSTEM_PROMPT),
        ("human", prompt),
    ])

    return {"review": response.model_dump()}


def find_guideline(guidelines, reference):
    """Find one retrieved guideline by its numbered reference."""

    for guideline in guidelines:
        if guideline["ref"] == reference:
            return guideline

    return None


def verify_findings(state):
    """Check model citations and downgrade unsupported findings."""

    findings = []
    notes = []

    review = state["review"]

    for finding in review.get("findings", []):
        status = str(finding.get("status", "")).strip()
        citations = finding.get("citations", [])
        quote = str(finding.get("evidence_quote", "")).strip()
        explanation = str(finding.get("explanation", "")).strip()

        valid_citation = None

        if status in ["compliant", "concern"]:
            for reference in citations:
                guideline = find_guideline(state["guidelines"], reference)

                if guideline is None:
                    continue

                if quote and quote in guideline["text"]:
                    valid_citation = guideline
                    break

            if valid_citation is None:
                status = "needs_more_information"
                citations = []
                quote = ""
                notes.append("An unsupported guideline finding was downgraded.")

        if status not in ASSESSMENT_STATUSES:
            status = "needs_more_information"
            citations = []
            quote = ""

        findings.append({
            "topic": str(finding.get("topic", "general"))[:100],
            "status": status,
            "explanation": explanation[:MAX_FINDING_EXPLANATION],
            "citations": citations if valid_citation is not None else [],
            "evidence_quote": quote[:MAX_EVIDENCE_QUOTE],
            "source": valid_citation["citation"] if valid_citation else None,
        })

    return {
        "findings": findings,
        "notes": notes,
    }


def build_result(state):
    """Build the final assessment result without making a claim decision."""

    review = state["review"]
    flags = []

    for flag in review.get("risk_flags", []):
        clean_flag = str(flag).strip()
        if clean_flag and clean_flag not in flags:
            flags.append(clean_flag[:100])

    for finding in state["findings"]:
        if finding["status"] == "concern":
            if "guideline_concern" not in flags:
                flags.append("guideline_concern")

        if finding["status"] == "needs_more_information":
            if "assessment_incomplete" not in flags:
                flags.append("assessment_incomplete")

    if not state["calculation"]["available"]:
        if "calculation_unavailable" not in flags:
            flags.append("calculation_unavailable")

    missing_information = []
    for item in review.get("missing_information", []):
        clean_item = str(item).strip()
        if clean_item and clean_item not in missing_information:
            missing_information.append(clean_item[:300])

    if not state["calculation"]["available"]:
        missing_information.append(state["calculation"]["reason"])

    guideline_citations = []
    for finding in state["findings"]:
        if finding["source"] is not None:
            guideline_citations.append(finding["source"])

    result = {
        "agent": "claim_assessment",
        "agent_version": "1.0.0",
        "claim_id": state["claim_id"],
        "status": "complete" if len(flags) == 0 else "needs_review",
        "summary": review.get("overall_summary", ""),
        "findings": state["findings"],
        "risk_flags": flags,
        "missing_information": missing_information,
        "calculation": state["calculation"],
        "guideline_citations": list(dict.fromkeys(guideline_citations)),
        "guidelines_used": [
            {
                "ref": guideline["ref"],
                "citation": guideline["citation"],
                "heading": guideline["heading"],
                "page_number": guideline["page_number"],
            }
            for guideline in state["guidelines"]
        ],
        "notes": state.get("notes", []),
    }

    return {"result": result}
