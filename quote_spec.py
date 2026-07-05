"""QuoteSpec: the typed, provenance-carrying artifact at the center of Quick Quotes.

Design principle: the LLM proposes, deterministic code disposes. Every field
records where its value came from; routing decisions are predicates over
provenance + gaps, never vibes.
"""
from __future__ import annotations

from enum import Enum
from typing import Generic, Literal, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Provenance(str, Enum):
    EXTRACTED = "extracted"            # stated in the request
    RESOLVED = "resolved"              # matched from history / master data
    DEFAULTED = "defaulted"            # rules-table default
    INFERRED = "inferred"              # LLM judgment call (rare, always gated)
    CALCULATED = "calculated"          # deterministic derivation
    HUMAN_CONFIRMED = "human_confirmed"


class SpecField(BaseModel, Generic[T]):
    """A value plus its epistemic paper trail."""
    value: Optional[T] = None
    provenance: Optional[Provenance] = None
    confidence: Optional[float] = None   # meaningful for EXTRACTED / INFERRED only
    source: Optional[str] = None         # e.g. "email_body:L4", "defaults_table:v12"
    note: Optional[str] = None

    @property
    def is_gap(self) -> bool:
        return self.value is None

    def confirmed(self, value: T, note: str = "") -> "SpecField[T]":
        """Return a copy overwritten by a human. Humans always win."""
        return SpecField[T](
            value=value,
            provenance=Provenance.HUMAN_CONFIRMED,
            confidence=1.0,
            source="estimator_review",
            note=note or self.note,
        )


class Dimensions(BaseModel):
    length: SpecField[float] = SpecField[float]()
    width: SpecField[float] = SpecField[float]()
    depth: SpecField[float] = SpecField[float]()
    units: SpecField[str] = SpecField[str]()        # "in" | "mm"
    convention: SpecField[str] = SpecField[str]()   # "inside" | "outside"


class Board(BaseModel):
    strength_spec: SpecField[str] = SpecField[str]()   # verbatim: "32 ECT", "200#"
    strength_basis: SpecField[str] = SpecField[str]()  # "ect" | "mullen"
    flute: SpecField[str] = SpecField[str]()           # B, C, E, BC ...
    board_code: SpecField[str] = SpecField[str]()      # plant-language, RESOLVED


class PrintSpec(BaseModel):
    colors: SpecField[int] = SpecField[int]()
    coverage: SpecField[str] = SpecField[str]()        # none|light|medium|heavy
    artwork_ref: SpecField[str] = SpecField[str]()


class Quantity(BaseModel):
    as_requested: SpecField[str] = SpecField[str]()    # "one truckload", "5k"
    units: SpecField[int] = SpecField[int]()           # CALCULATED or EXTRACTED
    calc_basis: SpecField[str] = SpecField[str]()


class QuoteSpec(BaseModel):
    spec_version: int = 1
    status: Literal["draft", "validated", "frozen"] = "draft"

    customer_account: SpecField[str] = SpecField[str]()
    ship_to: SpecField[str] = SpecField[str]()
    prior_spec_ref: SpecField[str] = SpecField[str]()

    style: SpecField[str] = SpecField[str]()           # RSC, die-cut, HSC ...
    dimensions: Dimensions = Dimensions()
    board: Board = Board()
    print_spec: PrintSpec = PrintSpec()
    quantity: Quantity = Quantity()

    gaps: list[str] = []                # dotted paths of missing required fields
    needs_confirmation: list[str] = []  # DEFAULTED/INFERRED price-affecting fields
    validation_flags: list[str] = []    # e.g. "ship_to_distance_412mi"


# Price-affecting fields that must not be None when we freeze.
REQUIRED_PATHS = [
    "customer_account",
    "ship_to",
    "style",
    "dimensions.length",
    "dimensions.width",
    "dimensions.depth",
    "board.board_code",
    "quantity.units",
]

# Price-affecting fields where a machine-supplied default/inference must be
# confirmed by a human before pricing.
CONFIRMATION_REQUIRED_PROVENANCE = {Provenance.DEFAULTED, Provenance.INFERRED}

BLOCKING_FLAGS = {"credit_hold", "style_unsupported", "board_unavailable"}


def get_field(spec: QuoteSpec, dotted: str) -> SpecField:
    obj = spec
    for part in dotted.split("."):
        obj = getattr(obj, part)
    return obj


def set_field(spec: QuoteSpec, dotted: str, field: SpecField) -> None:
    parts = dotted.split(".")
    obj = spec
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], field)
