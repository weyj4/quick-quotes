"""The design invariants from the README, enforced.

These cover the deterministic core. There are deliberately no tests of LLM
behavior here — when extract_resolve lands, fixtures.draft_spec_fixture()
becomes its golden expected-output test.
"""
from langgraph.types import Command

from quickquotes import Provenance, build_graph, get_field
from quickquotes.fixtures import draft_spec_fixture
from quickquotes.nodes import complete_validate, route_after_validation


def validated(spec=None):
    state = {"spec": spec or draft_spec_fixture(), "quote": None}
    return complete_validate(state)["spec"]


def test_validation_is_idempotent():
    once = validated()
    twice = validated(once)
    assert once.model_dump() == twice.model_dump()


def test_passes_never_overwrite_extracted_values():
    before = draft_spec_fixture()
    after = validated(before)
    for path in ("style", "dimensions.length", "board.strength_spec",
                 "quantity.as_requested"):
        b, a = get_field(before, path), get_field(after, path)
        assert b.provenance == Provenance.EXTRACTED
        assert a.value == b.value and a.provenance == b.provenance


def test_gaps_and_defaults_route_to_clarify():
    spec = validated()
    assert "ship_to" in spec.gaps
    assert "board.flute" in spec.needs_confirmation
    assert route_after_validation({"spec": spec, "quote": None}) == "clarify"


def test_defaults_carry_provenance_and_source():
    spec = validated()
    flute = get_field(spec, "board.flute")
    assert flute.provenance == Provenance.DEFAULTED
    assert flute.source and "defaults_table" in flute.source


def test_truckload_is_calculated_with_basis():
    spec = validated()
    assert get_field(spec, "quantity.units").provenance == Provenance.CALCULATED
    assert get_field(spec, "quantity.calc_basis").value


def test_partial_answers_reinterrupt_and_full_answers_price():
    graph = build_graph()
    cfg = {"configurable": {"thread_id": "t-test"}}
    result = graph.invoke({"spec": draft_spec_fixture(), "quote": None}, cfg)
    assert "__interrupt__" in result

    result = graph.invoke(
        Command(resume={"ship_to": "ACME-PLANT-1", "board.flute": "C"}), cfg)
    assert "__interrupt__" in result          # convention still unconfirmed

    result = graph.invoke(
        Command(resume={"dimensions.convention": "inside"}), cfg)
    assert result["quote"] is not None
    assert result["spec"].status == "frozen"
    # humans always win
    assert get_field(result["spec"], "ship_to").provenance \
        == Provenance.HUMAN_CONFIRMED


def test_quote_is_reproducible_from_frozen_spec():
    def run():
        graph = build_graph()
        cfg = {"configurable": {"thread_id": "t-repro"}}
        graph.invoke({"spec": draft_spec_fixture(), "quote": None}, cfg)
        graph.invoke(Command(resume={
            "ship_to": "ACME-PLANT-1", "board.flute": "C",
            "dimensions.convention": "inside"}), cfg)
        return graph.get_state(cfg).values["quote"]

    assert run() == run()
