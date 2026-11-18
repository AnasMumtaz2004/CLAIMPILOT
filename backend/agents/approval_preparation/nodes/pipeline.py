from agents.approval_preparation import tools
from agents.approval_preparation.config import APPROVAL_QUERY_BY_LINE
from agents.approval_preparation.config import MAX_GUIDELINES
from agents.approval_preparation.config import MAX_GUIDELINE_CHARS
from agents.approval_preparation.config import MAX_HUMAN_REVIEW_POINTS
from agents.approval_preparation.config import MAX_OUTSTANDING_ITEMS
from agents.approval_preparation.config import REQUIREMENT_STATUSES
from agents.approval_preparation.state import ApprovalPreparationReview
from agents.prompts.approval_preparation import SYSTEM_PROMPT
from agents.prompts.approval_preparation import build_user_prompt


def load_inputs(state, db):
    """Load claim, policy and document information."""

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
    """Stop the graph if claim data cannot be loaded."""

    if state.get("error"):
        return "stop"

    return "continue"


def retrieve_approval_guidelines(state, db):
    """Retrieve approval requirements for the claim insurance line."""

    line = state["claim"]["line"]
    query = APPROVAL_QUERY_BY_LINE.get(line)

    if query is None:
        return {"approval_guidelines": []}

    results = tools.search_approval_guidelines(db, state["claim"]["id"], line, query)
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

    return {"approval_guidelines": guidelines}


def run_completeness_checks(state):
    """Run deterministic checks before asking the model for preparation."""

    result = tools.check_claim_completeness(
        state["claim"],
        state["documents"],
        state.get("intake_result", {}),
        state.get("document_review_result", {}),
        state.get("policy_coverage_result", {}),
        state.get("claim_assessment_result", {}),
    )

    checklist = tools.build_human_review_checklist(
        state["claim"], state["documents"], result,
        {"intake": state.get("intake_result", {}),
         "document_review": state.get("document_review_result", {}),
         "policy_coverage": state.get("policy_coverage_result", {}),
         "claim_assessment": state.get("claim_assessment_result", {})},
    )
    return {"deterministic_checks": result, "human_review_checklist": checklist}


def prepare_package(state, llm):
    """Use the LLM to prepare a structured human review package."""

    if not state["approval_guidelines"]:
        return {
            "review": {
                "requirements": [],
                "preparation_summary": (
                    "Approval preparation is incomplete because no internal "
                    "approval requirements were retrieved."
                ),
                "outstanding_items": [
                    "Relevant internal approval requirements were not found."
                ],
                "risk_flags": ["approval_guidelines_not_found"],
                "human_review_points": [
                    "A human officer must verify the applicable approval requirements."
                ],
            }
        }

    prompt = build_user_prompt(
        state["claim"],
        state["policy"],
        state["documents"],
        state.get("intake_result", {}),
        state.get("document_review_result", {}),
        state.get("policy_coverage_result", {}),
        state.get("claim_assessment_result", {}),
        state["approval_guidelines"],
        state["deterministic_checks"],
    )

    structured_llm = llm.with_structured_output(ApprovalPreparationReview)

    response = structured_llm.invoke([
        ("system", SYSTEM_PROMPT),
        ("human", prompt),
    ])

    return {"review": response.model_dump()}


def find_guideline(guidelines, reference):
    """Find one retrieved approval requirement by its reference number."""

    for guideline in guidelines:
        if guideline["ref"] == reference:
            return guideline

    return None


def verify_requirements(state):
    """Validate requirement citations and downgrade unsupported claims."""

    requirements = []
    notes = []

    for requirement in state["review"].get("requirements", []):
        status = str(requirement.get("status", "")).strip()
        citations = requirement.get("citations", [])
        quote = str(requirement.get("evidence_quote", "")).strip()
        valid_guideline = None

        if status in ["satisfied", "not_satisfied"]:
            for reference in citations:
                guideline = find_guideline(
                    state["approval_guidelines"],
                    reference,
                )

                if guideline is None:
                    continue

                if quote and quote in guideline["text"]:
                    valid_guideline = guideline
                    break

            if valid_guideline is None:
                status = "needs_verification"
                citations = []
                quote = ""
                notes.append("An unsupported requirement finding was downgraded.")

        if status not in REQUIREMENT_STATUSES:
            status = "needs_verification"
            citations = []
            quote = ""

        requirements.append({
            "requirement": str(requirement.get("requirement", "general"))[:150],
            "status": status,
            "explanation": str(requirement.get("explanation", ""))[:500],
            "citations": citations if valid_guideline else [],
            "evidence_quote": quote[:200],
            "source": valid_guideline["citation"] if valid_guideline else None,
        })

    return {
        "requirements": requirements,
        "notes": notes,
    }


def build_result(state):
    """Build the approval preparation package for a human officer."""

    review = state["review"]
    checks = state["deterministic_checks"]

    outstanding_items = []
    risk_flags = []
    human_review_points = []

    for item in checks["missing_items"]:
        if item not in outstanding_items:
            outstanding_items.append(item)

    for item in checks["warnings"]:
        if item not in outstanding_items:
            outstanding_items.append(item)

    for item in review.get("outstanding_items", []):
        clean_item = str(item).strip()

        if clean_item and clean_item not in outstanding_items:
            outstanding_items.append(clean_item[:300])

    for flag in review.get("risk_flags", []):
        clean_flag = str(flag).strip()

        if clean_flag and clean_flag not in risk_flags:
            risk_flags.append(clean_flag[:100])

    for point in review.get("human_review_points", []):
        clean_point = str(point).strip()

        if clean_point and clean_point not in human_review_points:
            human_review_points.append(clean_point[:300])

    for requirement in state["requirements"]:
        if requirement["status"] != "satisfied":
            risk_flags.append("approval_requirement_not_confirmed")

            if requirement["requirement"] not in human_review_points:
                human_review_points.append(
                    requirement["requirement"]
                )

    if not state["approval_guidelines"]:
        risk_flags.append("approval_guidelines_not_found")

    if not checks["complete"]:
        risk_flags.append("claim_completeness_not_confirmed")

    if not state.get("claim_assessment_result"):
        risk_flags.append("claim_assessment_missing")

    risk_flags = list(dict.fromkeys(risk_flags))
    outstanding_items = list(dict.fromkeys(outstanding_items))
    human_review_points = list(dict.fromkeys(human_review_points))

    preparation_status = "ready_for_human_review"

    if outstanding_items or risk_flags:
        preparation_status = "incomplete"

    return {
        "result": {
            "agent": "approval_preparation",
            "agent_version": "1.0.0",
            "claim_id": state["claim_id"],
            "preparation_status": preparation_status,
            "preparation_summary": review.get("preparation_summary", ""),
            "requirements": state["requirements"],
            "outstanding_items": outstanding_items[:MAX_OUTSTANDING_ITEMS],
            "risk_flags": risk_flags,
            "human_review_points": human_review_points[:MAX_HUMAN_REVIEW_POINTS],
            "deterministic_checks": checks,
            "claim_assessment": state.get("claim_assessment_result", {}),
            "approval_guidelines": [
                {
                    "ref": guideline["ref"],
                    "citation": guideline["citation"],
                    "heading": guideline["heading"],
                    "page_number": guideline["page_number"],
                }
                for guideline in state["approval_guidelines"]
            ],
            "notes": state.get("notes", []),
            "decision": None,
            "decision_maker": None,
            "payment_authorized": False,
        }
    }
