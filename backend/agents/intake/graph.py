from functools import partial

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agents.intake.config import AGENT_NAME
from agents.intake.config import AGENT_VERSION
from agents.intake.config import MAX_RETRIES
from agents.intake.config import MODEL_NAME
from agents.intake.config import MODEL_PROVIDER
from agents.intake.config import TEMPERATURE
from agents.intake.config import TIMEOUT_SECONDS
from agents.intake.nodes import pipeline
from agents.intake.state import IntakeState
from agents.llm import get_llm
from agents.run_log import make_trace_config
from agents.run_log import run_with_log


def build_graph(db, llm):
    """Build the intake graph: load, check completeness, ask the model, build the result."""
    graph = StateGraph(IntakeState)

    graph.add_node("load_claim", partial(pipeline.load_claim, db=db))
    graph.add_node("check_completeness", partial(pipeline.check_completeness, db=db))
    graph.add_node("classify_event", partial(pipeline.classify_event, llm=llm))
    graph.add_node("build_result", pipeline.build_result)

    graph.add_edge(START, "load_claim")
    graph.add_conditional_edges(
        "load_claim",
        pipeline.route_after_load,
        {"continue": "check_completeness", "stop": END},
    )
    graph.add_edge("check_completeness", "classify_event")
    graph.add_edge("classify_event", "build_result")
    graph.add_edge("build_result", END)

    return graph.compile()


def run_intake_agent(db, claim_id, llm=None):
    """Run the intake agent for one claim, save a log row, and return the result."""
    if llm is None:
        llm = get_llm(MODEL_PROVIDER, MODEL_NAME, TEMPERATURE, TIMEOUT_SECONDS, MAX_RETRIES)

    graph = build_graph(db, llm)

    def work(run_id):
        config = make_trace_config(AGENT_NAME, AGENT_VERSION, run_id, claim_id)
        final_state = graph.invoke({"claim_id": claim_id}, config=config)

        if final_state.get("error"):
            raise ValueError(f"Intake could not run: {final_state['error']}")

        result = final_state["result"]
        result["run_id"] = run_id
        return result

    return run_with_log(
        db,
        AGENT_NAME,
        AGENT_VERSION,
        MODEL_NAME,
        claim_id,
        {"claim_id": claim_id},
        work,
    )