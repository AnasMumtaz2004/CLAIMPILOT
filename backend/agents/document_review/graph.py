from functools import partial

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agents.document_review.config import AGENT_NAME
from agents.document_review.config import AGENT_VERSION
from agents.document_review.config import MAX_RETRIES
from agents.document_review.config import MODEL_NAME
from agents.document_review.config import MODEL_PROVIDER
from agents.document_review.config import TEMPERATURE
from agents.document_review.config import TIMEOUT_SECONDS
from agents.document_review.nodes import pipeline
from agents.document_review.state import DocumentReviewState
from agents.llm import get_llm
from agents.run_log import make_trace_config
from agents.run_log import run_with_log


def build_graph(db, llm):
    """Build the graph: load, read, extract, verify, compare, build the result."""
    graph = StateGraph(DocumentReviewState)

    graph.add_node("load_claim", partial(pipeline.load_claim, db=db))
    graph.add_node("read_documents", partial(pipeline.read_documents, db=db))
    graph.add_node("extract_facts", partial(pipeline.extract_facts, llm=llm))
    graph.add_node("verify_extractions", pipeline.verify_extractions)
    graph.add_node("cross_check", pipeline.cross_check)
    graph.add_node("build_result", pipeline.build_result)

    graph.add_edge(START, "load_claim")
    graph.add_conditional_edges(
        "load_claim",
        pipeline.route_after_load,
        {"continue": "read_documents", "stop": END},
    )
    graph.add_edge("read_documents", "extract_facts")
    graph.add_edge("extract_facts", "verify_extractions")
    graph.add_edge("verify_extractions", "cross_check")
    graph.add_edge("cross_check", "build_result")
    graph.add_edge("build_result", END)

    return graph.compile()


def run_document_review_agent(db, claim_id, llm=None):
    """Run the document review agent for one claim, save a log row, and return the result."""
    if llm is None:
        llm = get_llm(MODEL_PROVIDER, MODEL_NAME, TEMPERATURE, TIMEOUT_SECONDS, MAX_RETRIES)

    graph = build_graph(db, llm)

    def work(run_id):
        config = make_trace_config(AGENT_NAME, AGENT_VERSION, run_id, claim_id)
        final_state = graph.invoke({"claim_id": claim_id}, config=config)

        if final_state.get("error"):
            raise ValueError(f"Document review could not run: {final_state['error']}")

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