"""Nodes and routing for the complete_validate -> clarify loop.

Nodes do work; edges make routing decisions. complete_validate is a pipeline
of deterministic QuoteSpec -> QuoteSpec passes (no LLM anywhere downstream of
the draft). clarify is an interrupt whose payload is the review screen and
whose resume value is the estimator's answers.

Invariants (property-test material):
  - passes never overwrite EXTRACTED or HUMAN_CONFIRMED values (idempotence)
  - the deterministic pipeline never calls back into an LLM
  - only frozen specs reach pricing
"""
from __future__ import annotations

import hashlib
from typing import TypedDict

from langgraph.types import interrupt

from quickquotes import fixtures as fx
from quickquotes.quote_spec import (
    BLOCKING_FLAGS, CONFIRMATION_REQUIRED_PROVENANCE, REQUIRED_PATHS,
    Provenance, QuoteSpec, SpecField, get_field, set_field,
)


class GraphState(TypedDict, total=False):
    raw_request: str
    sender: str | None
    spec: QuoteSpec | None
    quote: dict | None
    extractor_name: str


# ------------------------------------------------------ deterministic passes
def apply_defaults(spec: QuoteSpec) -> QuoteSpec:
    """Fill absent fields from the rules table. DEFAULTED provenance; never
    touches a field that already has a value (human or otherwise)."""
    for path, default in fx.DEFAULTS.items():
        f = get_field(spec, path)
        if f.is_gap:
            set_field(spec, path, SpecField(
                value=default,
                provenance=Provenance.DEFAULTED,
                source=fx.DEFAULTS_TABLE_VERSION,
                note=f"rules-table default for {path}",
            ))
    return spec


def derive_quantities(spec: QuoteSpec) -> QuoteSpec:
    """'one truckload' -> unit count via the deterministic calculator.
    Recomputes CALCULATED values on every pass (inputs may have changed);
    never touches EXTRACTED/HUMAN_CONFIRMED units."""
    q = spec.quantity
    if q.units.provenance in (Provenance.EXTRACTED, Provenance.HUMAN_CONFIRMED):
        return spec
    if q.as_requested.value and "truckload" in q.as_requested.value.lower():
        d = spec.dimensions
        if not (d.length.is_gap or d.width.is_gap or d.depth.is_gap):
            units, basis = fx.truckload_units(
                d.length.value, d.width.value, d.depth.value)
            q.units = SpecField[int](
                value=units, provenance=Provenance.CALCULATED,
                source="truckload_calc:v1")
            q.calc_basis = SpecField[str](
                value=basis, provenance=Provenance.CALCULATED,
                source="truckload_calc:v1")
    return spec


def resolve_master_data(spec: QuoteSpec) -> QuoteSpec:
    """Exact lookups against plant master data. No match -> flag, never a guess."""
    b = spec.board
    if b.board_code.provenance == Provenance.HUMAN_CONFIRMED:
        return spec
    if not (b.strength_basis.is_gap or b.strength_spec.is_gap or b.flute.is_gap):
        strength_value = "".join(c for c in b.strength_spec.value if c.isdigit())
        key = (b.strength_basis.value, strength_value, b.flute.value)
        code = fx.PLANT_BOARDS.get(key)
        if code:
            b.board_code = SpecField[str](
                value=code, provenance=Provenance.RESOLVED,
                source="plant_master:boards",
                note=f"{b.strength_spec.value} {b.flute.value}-flute -> stocked board",
            )
        else:
            spec.validation_flags.append("board_unavailable")
    return spec


def run_checks(spec: QuoteSpec) -> QuoteSpec:
    """Manufacturability + business checks -> validation_flags."""
    flags = set()

    if spec.style.value and spec.style.value not in fx.SUPPORTED_STYLES:
        flags.add("style_unsupported")

    if spec.print_spec.colors.value and \
            spec.print_spec.colors.value > fx.PLANT_MAX_PRESS_COLORS:
        flags.add("press_color_capacity_exceeded")

    if spec.quantity.units.value and spec.quantity.units.value < fx.MIN_RUN_UNITS:
        flags.add("below_min_run")

    cust = fx.CUSTOMER_MASTER.get(spec.customer_account.value or "", {})
    if cust and not cust.get("credit_ok", True):
        flags.add("credit_hold")
    if cust and spec.ship_to.value:
        dest = cust["ship_tos"].get(spec.ship_to.value)
        if dest and dest["distance_mi"] > 250:
            flags.add(f"ship_to_distance_{dest['distance_mi']}mi")  # triage signal

    spec.validation_flags = sorted(set(spec.validation_flags) | flags)
    return spec


def finalize_gap_report(spec: QuoteSpec) -> QuoteSpec:
    spec.gaps = [p for p in REQUIRED_PATHS if get_field(spec, p).is_gap]
    spec.needs_confirmation = [
        p for p in REQUIRED_PATHS + ["board.flute", "dimensions.convention"]
        if get_field(spec, p).provenance in CONFIRMATION_REQUIRED_PROVENANCE
    ]
    blocked = set(spec.validation_flags) & BLOCKING_FLAGS
    spec.status = "validated" if not (spec.gaps or spec.needs_confirmation
                                      or blocked) else "draft"
    return spec


# ------------------------------------------------------------------- nodes
def extract_resolve(state: GraphState) -> GraphState:
    """The one LLM stage: raw request -> draft QuoteSpec, then deterministic
    resolution against master data / order history. Everything downstream of
    the returned draft is deterministic."""
    from quickquotes.extraction import get_extractor, map_extraction_to_spec

    extractor = get_extractor()
    extraction = extractor.extract(state["raw_request"])
    spec = map_extraction_to_spec(extraction, state.get("sender"))
    return {"spec": spec, "extractor_name": extractor.name}


def complete_validate(state: GraphState) -> GraphState:
    spec = state["spec"].model_copy(deep=True)
    spec.validation_flags = []
    for step in (apply_defaults, derive_quantities,
                 resolve_master_data, run_checks, finalize_gap_report):
        spec = step(spec)
    return {"spec": spec, "quote": state.get("quote")}


def clarify(state: GraphState) -> GraphState:
    """Interrupt: surface the review payload, apply the estimator's answers
    as HUMAN_CONFIRMED, loop back to validation."""
    spec = state["spec"].model_copy(deep=True)

    payload = {
        "gaps": {
            p: {"prompt": f"Missing required field: {p}"} for p in spec.gaps
        },
        "confirmations": {
            p: {
                "proposed": get_field(spec, p).value,
                "why": get_field(spec, p).note,
                "source": get_field(spec, p).source,
            }
            for p in spec.needs_confirmation
        },
        "flags": spec.validation_flags,
    }

    # Execution pauses here; resumes with the estimator's answers:
    #   {"board.flute": "C", "ship_to": "ACME-PLANT-1", ...}
    answers: dict = interrupt(payload)

    for path, value in answers.items():
        current = get_field(spec, path)
        set_field(spec, path, current.confirmed(value))

    return {"spec": spec, "quote": state.get("quote")}


def price(state: GraphState) -> GraphState:
    """Freeze the spec, then call CoreERP costing (stubbed). No LLM here."""
    spec = state["spec"].model_copy(deep=True)
    spec.status = "frozen"
    spec_hash = hashlib.sha256(
        spec.model_dump_json(exclude={"gaps", "needs_confirmation"})
            .encode()).hexdigest()[:12]

    # ---- CoreERP costing API stand-in: pure function of the frozen spec ----
    units = spec.quantity.units.value
    unit_cost = 0.83                       # pretend CoreERP returned this
    margin_pct = 0.18                      # v1: standard margin from policy table
    quote = {
        "spec_version": spec.spec_version,
        "spec_hash": spec_hash,
        "units": units,
        "unit_price": round(unit_cost * (1 + margin_pct), 4),
        "extended": round(units * unit_cost * (1 + margin_pct), 2),
        "margin_source": "margin_policy:standard_18",
    }
    return {"spec": spec, "quote": quote}


# ------------------------------------------------------------------ routing
def route_after_validation(state: GraphState) -> str:
    """Pure predicate over the artifact. No side effects, trivially testable."""
    spec = state["spec"]
    if set(spec.validation_flags) & BLOCKING_FLAGS:
        return "clarify"
    if spec.gaps or spec.needs_confirmation:
        return "clarify"
    return "price"
