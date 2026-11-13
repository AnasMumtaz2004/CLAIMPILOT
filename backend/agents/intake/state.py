from typing import TypedDict

from pydantic import BaseModel
from pydantic import Field


class IntakeReview(BaseModel):
    """What the language model must return."""

    event_type: str = Field(description="One value from the allowed list, or 'unclear'.")
    event_summary: str = Field(description="One or two plain sentences about what happened.")
    domain_matches_description: bool = Field(description="True if the description fits the insurance line.")
    domain_mismatch_reason: str = Field(default="", description="One short sentence when the description does not fit.")
    inconsistencies: list[str] = Field(default_factory=list, description="Clear contradictions inside the claim data.")


class IntakeState(TypedDict, total=False):
    """The data that moves through the intake graph."""

    claim_id: str
    facts: dict
    completeness: dict
    review: dict
    result: dict
    error: str