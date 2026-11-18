
from typing import TypedDict

from pydantic import BaseModel
from pydantic import Field


class ApprovalRequirement(BaseModel):
    """One requirement that must be checked before human review."""

    requirement: str = Field(description="The approval requirement.")
    status: str = Field(description="satisfied, not_satisfied, or needs_verification.")
    explanation: str = Field(description="Evidence-based explanation.")
    citations: list[int] = Field(default_factory=list)
    evidence_quote: str = ""


class ApprovalPreparationReview(BaseModel):
    """Structured approval preparation response from the LLM."""

    requirements: list[ApprovalRequirement] = Field(default_factory=list)
    preparation_summary: str
    outstanding_items: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    human_review_points: list[str] = Field(default_factory=list)


class ApprovalPreparationState(TypedDict, total=False):
    """Data passed between approval preparation graph nodes."""

    claim_id: str
    intake_result: dict
    document_review_result: dict
    policy_coverage_result: dict
    claim_assessment_result: dict
    claim: dict
    policy: dict
    documents: list
    approval_guidelines: list
    deterministic_checks: dict
    review: dict
    requirements: list
    result: dict
    error: str
