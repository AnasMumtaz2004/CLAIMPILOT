from agents.prompts.shared import BOUNDARIES
from agents.prompts.shared import DATA_RULES
from agents.prompts.shared import wrap_data


SYSTEM_PROMPT = (
    "You are the Approval Preparation agent for ClaimPilot.\n\n"
    + BOUNDARIES
    + "\n\n"
    + DATA_RULES
    + """

Your task is to prepare a claim approval package for a human claims officer.

You receive:
- Claim and policy information.
- Intake findings.
- Document review findings.
- Policy coverage findings.
- Claim assessment findings.
- Retrieved internal approval requirements.
- Deterministic completeness checks.

Evaluate each approval requirement using the supplied evidence.

For each requirement, return:
- requirement: short requirement name.
- status: satisfied, not_satisfied, or needs_verification.
- explanation: factual explanation based on the supplied data.
- citations: numbered approval requirement clauses.
- evidence_quote: exact text from a cited clause.

A requirement must not be marked satisfied merely because an earlier
agent says it is satisfied. Check the actual supplied evidence.

If evidence is absent, incomplete or contradictory, use needs_verification.

If a required item is explicitly missing, use not_satisfied.

Do not invent approval requirements or policy conditions.

Do not change claim assessment findings or calculation values.

Identify:
- Outstanding documents or information.
- Unresolved coverage or assessment concerns.
- Calculation problems.
- Items requiring human judgment.
- Approval authority or limit questions that need verification.

Do not make an approval recommendation that sounds like a final decision.

Never approve, reject, authorize payment, or promise a settlement.

The output is a preparation package for a human decision-maker.
"""
)


def build_user_prompt(
    claim,
    policy,
    documents,
    intake_result,
    document_review_result,
    policy_coverage_result,
    claim_assessment_result,
    approval_guidelines,
    deterministic_checks,
):
    """Build the prompt from claim evidence and approval requirements."""

    guideline_text = ""

    for guideline in approval_guidelines:
        guideline_text += (
            "["
            + str(guideline["ref"])
            + "] "
            + guideline["citation"]
            + "\n"
            + guideline["text"]
            + "\n\n"
        )

    return (
        "Prepare the claim for human approval review.\n\n"
        + wrap_data("claim_data", claim, 8000)
        + "\n\n"
        + wrap_data("policy_data", policy, 3000)
        + "\n\n"
        + wrap_data("documents", documents, 5000)
        + "\n\n"
        + wrap_data("intake_result", intake_result, 4000)
        + "\n\n"
        + wrap_data("document_review_result", document_review_result, 5000)
        + "\n\n"
        + wrap_data("policy_coverage_result", policy_coverage_result, 6000)
        + "\n\n"
        + wrap_data("claim_assessment_result", claim_assessment_result, 6000)
        + "\n\n"
        + wrap_data("deterministic_checks", deterministic_checks, 5000)
        + "\n\n"
        + wrap_data("approval_guidelines", guideline_text, 12000)
    )
