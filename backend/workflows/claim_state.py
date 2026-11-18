from typing import Any, TypedDict


class ClaimWorkflowState(TypedDict, total=False):
    claim_id: str

    intake_result: dict[str, Any]
    document_review_result: dict[str, Any]
    policy_coverage_result: dict[str, Any]
    claim_assessment_result: dict[str, Any]
    approval_preparation_result: dict[str, Any]

    orchestration: dict[str, Any]

    human_decision: dict[str, Any]
    workflow_error: str