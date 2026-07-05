"""Wire the graph and run the loop end to end:

    complete_validate --(gaps/confirmations)--> clarify --loop--> complete_validate
                      --(clean)--> price

Run:  python run_demo.py
"""
from __future__ import annotations

import json

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from fixtures import draft_spec_fixture
from nodes import (GraphState, clarify, complete_validate, price,
                   route_after_validation)


def build_graph():
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

    # In prod on Cloud Run this is a Postgres checkpointer (Cloud SQL) —
    # approval is async and containers are stateless. MemorySaver for the demo.
    return g.compile(checkpointer=MemorySaver())


def show_spec(spec, title):
    print(f"\n=== {title} ===")
    print(f"status: {spec.status}   gaps: {spec.gaps}")
    print(f"needs_confirmation: {spec.needs_confirmation}")
    print(f"flags: {spec.validation_flags}")
    for path in ("board.flute", "board.board_code", "quantity.units",
                 "quantity.calc_basis", "ship_to"):
        from quote_spec import get_field
        f = get_field(spec, path)
        prov = f.provenance.value if f.provenance else "—"
        print(f"  {path:22} = {str(f.value):42.42} [{prov}]")


def main():
    graph = build_graph()
    config = {"configurable": {"thread_id": "quote-demo-001"}}

    # ---- turn 1: run until the graph interrupts for clarification ----------
    result = graph.invoke(
        {"spec": draft_spec_fixture(), "quote": None}, config)

    show_spec(result["spec"], "after complete_validate (pre-interrupt)")

    assert "__interrupt__" in result, "expected a clarify interrupt"
    payload = result["__interrupt__"][0].value
    print("\n=== clarify interrupt payload (the estimator's review screen) ===")
    print(json.dumps(payload, indent=2, default=str))

    # ---- turn 2: estimator answers PARTIALLY (forgets one confirmation) ----
    partial = {
        "ship_to": "ACME-PLANT-1",   # fills the gap
        "board.flute": "C",          # confirms the default
    }
    print(f"\n>>> resuming with PARTIAL answers: {partial}")
    result = graph.invoke(Command(resume=partial), config)

    # The loop revalidates and interrupts again: dimensions.convention is
    # still an unconfirmed default. Pricing is unreachable until clean.
    assert "__interrupt__" in result, "expected a second interrupt"
    print("\n>>> graph re-interrupted (loop refuses to price an unclean spec):")
    print(json.dumps(result["__interrupt__"][0].value["confirmations"],
                     indent=2, default=str))

    # ---- turn 3: the remaining confirmation ------------------------------
    answers = {"dimensions.convention": "inside"}
    print(f"\n>>> resuming with remaining answer: {answers}")
    result = graph.invoke(Command(resume=answers), config)

    show_spec(result["spec"], "after clarify loop -> revalidation -> price")

    print("\n=== quote (CoreERP stub, pure function of the frozen spec) ===")
    print(json.dumps(result["quote"], indent=2))


if __name__ == "__main__":
    main()
