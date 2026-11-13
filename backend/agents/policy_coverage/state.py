from typing import TypedDict

from pydantic import BaseModel
from pydantic import Field


class CoverageFinding(BaseModel):
    """The model's finding for one topic."""

    topic: str = Field(description="The exact topic name from the list.")
    assessment: str = Field(description="supports_coverage, limits_coverage or needs_more_information.")
    explanation: str = Field(description="One or two short sentences.")
    citations: list[int] = Field(default_factory=list, description="Numbers of the clauses used.")
    evidence_quote: str = Field(default="", description="An exact quote, up to 150 characters, from a cited clause.")


class AddOnFinding(BaseModel):
    """One add-on named in the schedule."""

    name: str = Field(description="The name of the add-on as written in the schedule.")
    status: str = Field(description="selected, not_selected or not_shown.")
    citation: int = Field(description="The number of the schedule clause that names the add-on.")
    evidence_quote: str = Field(description="Exact text from that clause that contains the add-on name.")


class CoverageReview(BaseModel):
    """What the language model must return."""

    findings: list[CoverageFinding] = Field(default_factory=list, description="One finding for each topic.")
    add_ons: list[AddOnFinding] = Field(default_factory=list, description="Add-ons named in the schedule.")


class PolicyCoverageState(TypedDict, total=False):
    """The data that moves through the policy coverage graph."""

    claim_id: str
    intake: dict
    facts: dict
    schedule: dict
    checks: dict
    clauses: list
    review: dict
    findings: list
    add_ons: list
    notes: list
    result: dict
    error: str