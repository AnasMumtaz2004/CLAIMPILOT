
import logging

from workflows.claim_workflow import resume_claim_workflow

logger = logging.getLogger(__name__)


def resume_after_human_decision(claim_id, decision):
    """
    Resume the paused LangGraph workflow after the
    Claims Officer decision has been committed.
    """

    try:
        resume_claim_workflow(
            claim_id,
            {
                "decision": decision
            }
        )

    except Exception:
        # The human decision has already been committed.
        # A workflow resume error must not undo it.
        logger.exception(
            "Could not resume workflow for claim %s",
            claim_id
        )
