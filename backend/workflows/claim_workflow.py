from functools import partial
import time
import uuid

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agents.intake.graph import run_intake_agent
from agents.document_review.graph import run_document_review_agent
from agents.policy_coverage.graph import run_policy_coverage_agent
from agents.claim_assessment.graph import run_claim_assessment_agent
from agents.approval_preparation.graph import (
    run_approval_preparation_agent
)
from agents.orchestrator.graph import run_orchestrator

from database.models import (
    Claim,
    ClaimStatusHistory,
    AgentExecutionLog,
    utc_now,
)

from services.claim_service import STATUS_INFO
from workflows.claim_state import ClaimWorkflowState


# ---------------------------------------------------------
# Existing specialist agent adapters
# ---------------------------------------------------------

def run_intake(state, db):
    result = run_intake_agent(db, state["claim_id"])

    return {
        "intake_result": result
    }


def run_document_review(state, db):
    result = run_document_review_agent(
        db,
        state["claim_id"]
    )

    return {
        "document_review_result": result
    }


def run_policy_coverage(state, db):
    result = run_policy_coverage_agent(
        db,
        state["claim_id"],
        intake_result=state.get("intake_result") or {}
    )

    return {
        "policy_coverage_result": result
    }


def run_claim_assessment(state, db):
    result = run_claim_assessment_agent(
        db,
        state["claim_id"],
        intake_result=state.get("intake_result") or {},
        document_review_result=(
            state.get("document_review_result") or {}
        ),
        policy_coverage_result=(
            state.get("policy_coverage_result") or {}
        ),
    )

    return {
        "claim_assessment_result": result
    }


def run_approval_preparation(state, db):
    result = run_approval_preparation_agent(
        db,
        state["claim_id"],
        intake_result=state.get("intake_result") or {},
        document_review_result=(
            state.get("document_review_result") or {}
        ),
        policy_coverage_result=(
            state.get("policy_coverage_result") or {}
        ),
        claim_assessment_result=(
            state.get("claim_assessment_result") or {}
        ),
    )

    return {
        "approval_preparation_result": result
    }


# ---------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------

def run_orchestrator_node(state, db):
    started = time.monotonic()

    result = run_orchestrator(state)
    output = result.get("orchestration", {})

    db.add(
        AgentExecutionLog(
            run_id=str(uuid.uuid4()),
            claim_id=state["claim_id"],
            agent_name="orchestrator",
            agent_version="1.0.0",
            model_name="deterministic-router",
            status="success",
            input_summary={
                "specialist_results_present": [
                    key
                    for key in (
                        "intake_result",
                        "document_review_result",
                        "policy_coverage_result",
                        "claim_assessment_result",
                        "approval_preparation_result",
                    )
                    if bool(state.get(key))
                ]
            },
            output=output,
            error=None,
            duration_ms=int(
                (time.monotonic() - started) * 1000
            ),
        )
    )

    db.commit()

    return result


# ---------------------------------------------------------
# Update claim status for human review
# ---------------------------------------------------------

def mark_for_review(state, db):
    claim = (
        db.query(Claim)
        .filter(Claim.id == state["claim_id"])
        .first()
    )

    if claim is None:
        raise ValueError("Claim not found.")

    final_statuses = {
        "approved",
        "rejected",
        "settled",
        "closed",
        "info_required",
    }

    if claim.status not in final_statuses:
        if claim.status != "approval_review":
            claim.status = "approval_review"
            claim.version += 1
            claim.updated_at = utc_now()

            info = STATUS_INFO["approval_review"]

            db.add(
                ClaimStatusHistory(
                    claim_id=claim.id,
                    status="approval_review",
                    label=info["label"],
                    description=info["description"],
                    actor_id=None,
                )
            )

            db.commit()

    return {
        "workflow_error": ""
    }


# ---------------------------------------------------------
# Human-in-the-loop interrupt
# ---------------------------------------------------------

def human_review_gate(state):
    decision = interrupt(
        {
            "type": "claims_officer_review_required",
            "claim_id": state["claim_id"],
            "orchestration": state.get("orchestration", {}),
            "approval_preparation": (
                state.get("approval_preparation_result", {})
            ),
        }
    )

    return {
        "human_decision": decision or {}
    }


# ---------------------------------------------------------
# Build complete workflow
# ---------------------------------------------------------

def build_claim_workflow(db, checkpointer):

    graph = StateGraph(ClaimWorkflowState)

    graph.add_node(
        "intake",
        partial(run_intake, db=db)
    )

    graph.add_node(
        "document_review",
        partial(run_document_review, db=db)
    )

    graph.add_node(
        "policy_coverage",
        partial(run_policy_coverage, db=db)
    )

    graph.add_node(
        "claim_assessment",
        partial(run_claim_assessment, db=db)
    )

    graph.add_node(
        "approval_preparation",
        partial(run_approval_preparation, db=db)
    )

    graph.add_node(
        "orchestrator",
        partial(run_orchestrator_node, db=db)
    )

    graph.add_node(
        "mark_for_review",
        partial(mark_for_review, db=db)
    )

    graph.add_node(
        "human_review",
        human_review_gate
    )

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "document_review")
    graph.add_edge("document_review", "policy_coverage")
    graph.add_edge("policy_coverage", "claim_assessment")
    graph.add_edge("claim_assessment", "approval_preparation")
    graph.add_edge("approval_preparation", "orchestrator")
    graph.add_edge("orchestrator", "mark_for_review")
    graph.add_edge("mark_for_review", "human_review")
    graph.add_edge("human_review", END)

    return graph.compile(
        checkpointer=checkpointer
    )


# ---------------------------------------------------------
# Resume after Claims Officer decision
# ---------------------------------------------------------

def resume_claim_workflow(claim_id: str, decision: dict):
    from database.connection import SessionLocal
    from workflows.persistence import open_checkpointer

    db = SessionLocal()

    try:
        with open_checkpointer() as checkpointer:
            checkpointer.setup()

            graph = build_claim_workflow(
                db,
                checkpointer
            )

            return graph.invoke(
                Command(resume=decision),
                config={
                    "configurable": {
                        "thread_id": claim_id
                    }
                }
            )

    finally:
        db.close()