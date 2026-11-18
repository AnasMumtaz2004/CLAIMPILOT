from typing import TypedDict

from pydantic import BaseModel
from pydantic import Field


class AssessmentFinding(BaseModel):
    """One guideline-based finding about the claim."""

    topic: str = Field(description="The assessment topic.")
    status: str = Field(description="compliant, concern, or needs_more_information.")
    explanation: str = Field(description="A short factual explanation.")
    citations: list[int] = Field(default_factory=list, description="Numbers of the guideline clauses used.")
    evidence_quote: str = Field(default="", description="An exact quote from one cited guideline clause.")


class AssessmentReview(BaseModel):
    """The structured response returned by the assessment model."""

    findings: list[AssessmentFinding] = Field(default_factory=list)
    overall_summary: str = Field(description="A neutral summary of the assessment.")
    missing_information: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class ClaimAssessmentState(TypedDict, total=False):
    """The data passed between Claim Assessment graph nodes."""

    claim_id: str
    intake_result: dict
    document_review_result: dict
    policy_coverage_result: dict
    claim: dict
    policy: dict
    documents: list
    guidelines: list
    calculation: dict
    calculation_error: str
    review: dict
    findings: list
    result: dict
    error: str
