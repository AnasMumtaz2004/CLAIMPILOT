from functools import partial

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agents.llm import get_llm
from agents.policy_coverage.config import AGENT_NAME
from agents.policy_coverage.config import AGENT_VERSION
from agents.policy_coverage.config import MAX_RETRIES
from agents.policy_coverage.config import MODEL_NAME
from agents.policy_coverage.config import MODEL_PROVIDER
from agents.policy_coverage.config import TEMPERATURE
from agents.policy_coverage.config import TIMEOUT_SECONDS
from agents.policy_coverage.nodes import pipeline
from agents.policy_coverage.state import PolicyCoverageState
from agents.run_log import make_trace_config
from agents.run_log import run_with_log


def build_graph(db, llm):
    """Build the graph: load, check, search the policy, ask the model, verify, build the result."""
    graph = StateGraph(PolicyCoverageState)

    graph.add_node("load_inputs", partial(pipeline.load_inputs, db=db))
    graph.add_node("check_schedule", pipeline.check_schedule)
    graph.add_node("retrieve_clauses", partial(pipeline.retrieve_clauses, db=db))
    graph.add_node("analyze_coverage", partial(pipeline.analyze_coverage, llm=llm))
    graph.add_node("verify_findings", pipeline.verify_findings)
    graph.add_node("build_result", pipeline.build_result)

    graph.add_edge(START, "load_inputs")
    graph.add_conditional_edges(
        "load_inputs",
        pipeline.route_after_load,
        {"continue": "check_schedule", "stop": END},
    )
    graph.add_edge("check_schedule", "retrieve_clauses")
    graph.add_edge("retrieve_clauses", "analyze_coverage")
    graph.add_edge("analyze_coverage", "verify_findings")
    graph.add_edge("verify_findings", "build_result")
    graph.add_edge("build_result", END)

    return graph.compile()


def run_policy_coverage_agent(db, claim_id, llm=None, intake_result=None):
    """Run the policy coverage agent for one claim, save a log row, and return the result."""
    if llm is None:
        llm = get_llm(MODEL_PROVIDER, MODEL_NAME, TEMPERATURE, TIMEOUT_SECONDS, MAX_RETRIES)

    graph = build_graph(db, llm)

    def work(run_id):
        config = make_trace_config(AGENT_NAME, AGENT_VERSION, run_id, claim_id)
        start_state = {"claim_id": claim_id, "intake": intake_result or {}}
        final_state = graph.invoke(start_state, config=config)

        if final_state.get("error"):
            raise ValueError(f"Policy coverage could not run: {final_state['error']}")

        result = final_state["result"]
        result["run_id"] = run_id
        return result

    return run_with_log(
        db,
        AGENT_NAME,
        AGENT_VERSION,
        MODEL_NAME,
        claim_id,
        {"claim_id": claim_id, "used_intake_result": bool(intake_result)},
        work,
    )