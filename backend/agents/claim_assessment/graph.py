
from functools import partial

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agents.claim_assessment.config import AGENT_NAME
from agents.claim_assessment.config import AGENT_VERSION
from agents.claim_assessment.config import MAX_RETRIES
from agents.claim_assessment.config import MODEL_NAME
from agents.claim_assessment.config import MODEL_PROVIDER
from agents.claim_assessment.config import TEMPERATURE
from agents.claim_assessment.config import TIMEOUT_SECONDS
from agents.claim_assessment.nodes import pipeline
from agents.claim_assessment.state import ClaimAssessmentState
from agents.llm import get_llm
from agents.run_log import make_trace_config
from agents.run_log import run_with_log


def build_graph(db, llm):
    """Build the Claim Assessment graph."""

    graph = StateGraph(ClaimAssessmentState)

    graph.add_node("load_inputs", partial(pipeline.load_inputs, db=db))
    graph.add_node("retrieve_guidelines", partial(pipeline.retrieve_guidelines, db=db))
    graph.add_node("calculate_amount", partial(pipeline.calculate_amount, db=db))
    graph.add_node("analyze_claim", partial(pipeline.analyze_claim, llm=llm))
    graph.add_node("verify_findings", pipeline.verify_findings)
    graph.add_node("build_result", pipeline.build_result)

    graph.add_edge(START, "load_inputs")

    graph.add_conditional_edges(
        "load_inputs",
        pipeline.route_after_load,
        {
            "continue": "retrieve_guidelines",
            "stop": END,
        },
    )

    graph.add_edge("retrieve_guidelines", "calculate_amount")
    graph.add_edge("calculate_amount", "analyze_claim")
    graph.add_edge("analyze_claim", "verify_findings")
    graph.add_edge("verify_findings", "build_result")
    graph.add_edge("build_result", END)

    return graph.compile()


def run_claim_assessment_agent(
    db,
    claim_id,
    llm=None,
    intake_result=None,
    document_review_result=None,
    policy_coverage_result=None,
):
    """Run the assessment agent, save its execution log and return its result."""

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
        }

        final_state = graph.invoke(start_state, config=config)

        if final_state.get("error"):
            raise ValueError(
                "Claim assessment could not run: " + final_state["error"]
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
        },
        work,
    )
