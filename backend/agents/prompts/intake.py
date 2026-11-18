from agents.prompts.shared import BOUNDARIES
from agents.prompts.shared import DATA_RULES
from agents.prompts.shared import wrap_data

SYSTEM_PROMPT = (
    "You are the Intake agent.\n\n"
    + BOUNDARIES
    + "\n\n"
    + DATA_RULES
    + """

Your task is to read one submitted claim and fill in these fields:
1. event_type: the type of event described. Choose exactly one value from the allowed list in the user message.
   Use "unclear" if the description is empty or too vague to decide.
2. event_summary: one or two plain sentences about what happened, using only facts from the claim data.
3. domain_matches_description: true if the description fits the insurance line. false if it clearly describes
   something else, for example a car accident on a health claim. If the description is empty, answer true.
4. domain_mismatch_reason: one short sentence when domain_matches_description is false, otherwise empty.
5. inconsistencies: clear contradictions inside the claim data, for example the description says theft but the
   type of loss says fire, or the discharge date is before the admission date. Leave the list empty when you
   see none. Do not list missing information, that is checked somewhere else."""
)


def build_user_prompt(insurance_line_label, allowed_event_types, loss_date, claimed_amount, description, form_lines):
    """Build the user message for one claim."""
    claim_text = "Date of loss: " + str(loss_date) + "\n"
    claim_text = claim_text + "Claimed amount: " + str(claimed_amount) + "\n"
    claim_text = claim_text + "Description written by the customer: " + str(description or "(empty)") + "\n"
    claim_text = claim_text + "Form fields:\n"
    for line in form_lines:
        claim_text = claim_text + "- " + line + "\n"

    return (
        "Insurance line: " + insurance_line_label + "\n"
        + "Allowed event types: " + ", ".join(allowed_event_types) + "\n\n"
        + wrap_data("claim_data", claim_text)
    )