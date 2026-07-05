from enum import Enum
from typing import Generic, TypeVar, Optional, Literal
from pydantic import BaseModel

T = TypeVar("T")

class Provenance(str, Enum):
    # TODO: justify
    EXTRACTED = "extracted"          # stated in the request
    RESOLVED = "resolved"            # matched from history/master data
    DEFAULTED = "defaulted"          # rules-table default
    INFERRED = "inferred"            # LLM judgment call (rare, always gated)
    CALCULATED = "calculated"        # deterministic derivation (truckload calc)
    HUMAN_CONFIRMED = "human_confirmed"

class Field(BaseModel, Generic[T]):
    value: Optional[T] = None
    provenance: Optional[Provenance] = None
    confidence: Optional[float] = None       # only meaningful for extracted/inferred
    source: Optional[str] = None             # "email_body:L4", "attachment:quote.pdf:p2",
                                             # "order_history:SPEC-4471", "defaults_table:v12"
    note: Optional[str] = None               # human-readable justification

    @property
    def is_gap(self) -> bool:
        return self.value is None

class Dimensions(BaseModel):
    length: Field[float]
    width: Field[float]
    depth: Field[float]
    units: Field[Literal["in", "mm"]]
    convention: Field[Literal["inside", "outside"]]   # corrugated default: inside

class Board(BaseModel):
    strength_spec: Field[str]        # as stated: "32 ECT", "200#"
    strength_basis: Field[Literal["ect", "mullen"]]
    flute: Field[str]                # validated against plant enum: B, C, E, BC...
    board_code: Field[str]           # RESOLVED against plant master data — the
                                     # plant-language value CoreERP actually wants

class PrintSpec(BaseModel):
    colors: Field[int]
    coverage: Field[Literal["none", "light", "medium", "heavy"]]
    artwork_ref: Field[str]

class Quantity(BaseModel):
    as_requested: Field[str]         # "one truckload", "5k", "same as usual"
    units: Field[int]                # CALCULATED or EXTRACTED
    calc_basis: Field[str]           # "53ft dry van, 40x48 pallets, 47 units/pallet"

class QuoteSpec(BaseModel):
    spec_version: int
    status: Literal["draft", "validated", "frozen"]
    customer_account: Field[str]     # RESOLVED — highest-stakes field in the spec
    ship_to: Field[str]
    prior_spec_ref: Field[str]       # populated on "same as last time" requests
    style: Field[str]                # RSC, die-cut... validated against plant enum
    dimensions: Dimensions
    board: Board
    print: PrintSpec
    quantity: Quantity
    gaps: list[str]                  # dotted paths: "board.flute", "quantity.units"
    validation_flags: list[str]      # "die_required_no_tooling", "below_min_run",
                                     # "ship_to_distance_412mi", "credit_hold"

