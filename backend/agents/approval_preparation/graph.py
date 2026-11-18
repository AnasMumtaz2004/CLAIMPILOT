
from functools import partial

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agents.approval_preparation.config import AGENT_NAME
from agents.approval_preparation.config import AGENT_VERSION
from agents.approval_preparation.config import MAX_RETRIES
from agents.approval_preparation.config import MODEL_NAME
from agents.approval_preparation.config import MODEL_PROVIDER
from agents.approval_preparation.config import TEMPERATURE
from agents.approval_preparation.config import TIMEOUT_SECONDS
from agents.approval_preparation.nodes import pipeline
from agents.approval_preparation.state import ApprovalPreparationState
from agents.llm import get_llm
from agents.run_log import make_trace_config
from agents.run_log import run_with_log


def build_graph(db, llm):
    """Build the Approval Preparation graph."""

    graph = StateGraph(ApprovalPreparationState)

    graph.add_node(
        "load_inputs",
        partial(pipeline.load_inputs, db=db),
    )
    graph.add_node(
        "retrieve_approval_guidelines",
        partial(pipeline.retrieve_approval_guidelines, db=db),
    )
    graph.add_node(
        "run_completeness_checks",
        pipeline.run_completeness_checks,
    )
    graph.add_node(
        "prepare_package",
        partial(pipeline.prepare_package, llm=llm),
    )
    graph.add_node(
        "verify_requirements",
        pipeline.verify_requirements,
    )
    graph.add_node(
        "build_result",
        pipeline.build_result,
    )

    graph.add_edge(START, "load_inputs")

    graph.add_conditional_edges(
        "load_inputs",
        pipeline.route_after_load,
        {
            "continue": "retrieve_approval_guidelines",
            "stop": END,
        },
    )

    graph.add_edge(
        "retrieve_approval_guidelines",
        "run_completeness_checks",
    )
    graph.add_edge(
        "run_completeness_checks",
        "prepare_package",
    )
    graph.add_edge(
        "prepare_package",
        "verify_requirements",
    )
    graph.add_edge(
        "verify_requirements",
        "build_result",
    )
    graph.add_edge("build_result", END)

    return graph.compile()


def run_approval_preparation_agent(
    db,
    claim_id,
    intake_result=None,
    document_review_result=None,
    policy_coverage_result=None,
    claim_assessment_result=None,
    llm=None,
):
    """Run the approval preparation agent and save its execution log."""

    if llm is None:
        llm = get_llm(
            MODEL_PROVIDER,
            MODEL_NAME,
            TEMPERATURE,
            TIMEOUT_SECONDS,
            MAX_RETRIES,
        )

    graph = build_graph(db, llm)

    def work(run_id):
        config = make_trace_config(
            AGENT_NAME,
            AGENT_VERSION,
            run_id,
            claim_id,
        )

        start_state = {
            "claim_id": claim_id,
            "intake_result": intake_result or {},
            "document_review_result": document_review_result or {},
            "policy_coverage_result": policy_coverage_result or {},
            "claim_assessment_result": claim_assessment_result or {},
        }

        final_state = graph.invoke(
            start_state,
            config=config,
        )

        if final_state.get("error"):
            raise ValueError(
                "Approval preparation failed: "
                + final_state["error"]
            )

        result = final_state["result"]
        result["run_id"] = run_id

        return result

    return run_with_log(
        db,
        AGENT_NAME,
        AGENT_VERSION,
        MODEL_NAME,
        claim_id,
        {
            "claim_id": claim_id,
            "has_intake_result": bool(intake_result),
            "has_document_review_result": bool(document_review_result),
            "has_policy_coverage_result": bool(policy_coverage_result),
            "has_claim_assessment_result": bool(claim_assessment_result),
        },
        work,
    )
