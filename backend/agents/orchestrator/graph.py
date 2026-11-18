from langgraph.graph import END, START, StateGraph

from agents.orchestrator.nodes.pipeline import coordinate
from agents.orchestrator.state import OrchestratorState


def build_graph():
    graph = StateGraph(OrchestratorState)

    graph.add_node("coordinate", coordinate)

    graph.add_edge(START, "coordinate")
    graph.add_edge("coordinate", END)

    return graph.compile()


def run_orchestrator(state):
    return build_graph().invoke(state)