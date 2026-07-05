"""Graph assembly, shared by run_demo.py and the API."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from quickquotes.nodes import (GraphState, clarify, complete_validate, price,
                   route_after_validation)


def build_graph(checkpointer=None):
    g = StateGraph(GraphState)
    g.add_node("complete_validate", complete_validate)
    g.add_node("clarify", clarify)
    g.add_node("price", price)

    g.add_edge(START, "complete_validate")
    g.add_conditional_edges(
        "complete_validate",
        route_after_validation,               # nodes do work; edges route
        {"clarify": "clarify", "price": "price"},
    )
    g.add_edge("clarify", "complete_validate")  # corrections re-enter validation
    g.add_edge("price", END)

    # In prod on Cloud Run: Postgres checkpointer (Cloud SQL). Interrupts are
    # async and containers are stateless. MemorySaver for local demo.
    return g.compile(checkpointer=checkpointer or MemorySaver())
