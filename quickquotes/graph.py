"""Graph assembly, shared by run_demo.py and the API."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

# Our custom types that legitimately live in checkpointed state. Registering
# them explicitly (rather than pickle fallback) keeps checkpoints portable.
SERDE = JsonPlusSerializer(allowed_msgpack_modules=[
    ("quickquotes.quote_spec", "QuoteSpec"),
    ("quickquotes.quote_spec", "Provenance"),
    ("quickquotes.quote_spec", "SpecField"),
])

from quickquotes.nodes import (GraphState, clarify, complete_validate,
                   extract_resolve, price, route_after_validation)


def route_entry(state: GraphState) -> str:
    """Raw requests enter through extraction; pre-built specs (tests, spec
    injection) skip straight to validation."""
    return "complete_validate" if state.get("spec") else "extract_resolve"


def build_graph(checkpointer=None):
    g = StateGraph(GraphState)
    g.add_node("extract_resolve", extract_resolve)
    g.add_node("complete_validate", complete_validate)
    g.add_node("clarify", clarify)
    g.add_node("price", price)

    g.add_conditional_edges(START, route_entry,
                            {"extract_resolve": "extract_resolve",
                             "complete_validate": "complete_validate"})
    g.add_edge("extract_resolve", "complete_validate")
    g.add_conditional_edges(
        "complete_validate",
        route_after_validation,               # nodes do work; edges route
        {"clarify": "clarify", "price": "price"},
    )
    g.add_edge("clarify", "complete_validate")  # corrections re-enter validation
    g.add_edge("price", END)

    # In prod on Cloud Run: Postgres checkpointer (Cloud SQL). Interrupts are
    # async and containers are stateless. MemorySaver for local demo.
    return g.compile(checkpointer=checkpointer or MemorySaver(serde=SERDE))
