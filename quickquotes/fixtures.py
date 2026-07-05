"""Dummy plant master data and a draft QuoteSpec fixture.

The fixture represents what `extract_resolve` would emit after reading this
(fictional) inbound email:

    From: orders@acmefoods.example
    Subject: need pricing

    Hey — can you quote us a truckload of the 12x10x8 RSCs, 32 ECT,
    2-color print like the last run. Same artwork.

Note what's messy on purpose:
  - flute never stated            -> absent (defaults pass will fill it)
  - ship-to never stated          -> gap (there are two Acme plants on file)
  - quantity is "one truckload"   -> needs the truckload calculator
  - dims stated bare              -> units/convention need normalizing defaults
"""
from quickquotes.quote_spec import (
    Board, Dimensions, PrintSpec, Provenance, Quantity, QuoteSpec, SpecField,
)

# ---------------------------------------------------------------- master data
DEFAULTS_TABLE_VERSION = "defaults_table:v12"

DEFAULTS = {
    "board.flute": "C",            # conventional default for 32 ECT RSC
    "dimensions.units": "in",
    "dimensions.convention": "inside",
    "print_spec.coverage": "light",
}

# board_code lookup: (strength_basis, strength_value, flute) -> stocked board
PLANT_BOARDS = {
    ("ect", "32", "C"): "C-32ECT-KRAFT",
    ("ect", "32", "B"): "B-32ECT-KRAFT",
    ("ect", "44", "BC"): "BC-44ECT-KRAFT",
}

SUPPORTED_STYLES = {"RSC", "HSC", "FOL"}
MIN_RUN_UNITS = 500
PLANT_MAX_PRESS_COLORS = 3

CUSTOMER_MASTER = {
    "ACME-FOODS": {
        "credit_ok": True,
        "ship_tos": {
            "ACME-PLANT-1": {"distance_mi": 38},
            "ACME-PLANT-2": {"distance_mi": 412},
        },
    }
}

# truckload calculator config (deliberately crude for the MVP)
TRAILER_CUBIC_IN = 53 * 12 * 98 * 108          # 53ft dry van interior, roughly
PALLET_STACK_EFFICIENCY = 0.60                 # bundles, voids, pallet decks


def truckload_units(l_in: float, w_in: float, d_in: float) -> tuple[int, str]:
    """Deterministic 'one truckload' -> unit count. Returns (units, basis)."""
    # knocked-down flat RSC blank, approximated: (L+W) x (W+D) x flat thickness
    blank_l = l_in + w_in
    blank_w = w_in + d_in
    flat_thickness = 0.25                      # C-flute wall x2, approx
    per_box_cubic = blank_l * blank_w * flat_thickness
    usable = TRAILER_CUBIC_IN * PALLET_STACK_EFFICIENCY
    units = int(usable // per_box_cubic)
    units = (units // 100) * 100               # round down to bundle-friendly qty
    basis = (
        f"53ft dry van @ {PALLET_STACK_EFFICIENCY:.0%} cube utilization, "
        f"KD blank {blank_l:.0f}x{blank_w:.0f}x{flat_thickness}in"
    )
    return units, basis


# ------------------------------------------------------------------- fixture
def draft_spec_fixture() -> QuoteSpec:
    """The draft QuoteSpec as emitted by extract_resolve. LLM work is done;
    everything downstream of here is deterministic."""
    E = Provenance.EXTRACTED
    R = Provenance.RESOLVED

    return QuoteSpec(
        spec_version=1,
        status="draft",
        customer_account=SpecField[str](
            value="ACME-FOODS", provenance=R, confidence=0.98,
            source="sender_domain:acmefoods.example",
            note="matched by sender domain + order history",
        ),
        # ship_to left absent: Acme has two plants, email names neither -> GAP
        prior_spec_ref=SpecField[str](
            value="SPEC-4471", provenance=R, confidence=0.83,
            source="order_history:2026-03",
            note="'like the last run' -> most recent 12x10x8 RSC order",
        ),
        style=SpecField[str](
            value="RSC", provenance=E, confidence=0.99, source="email_body:L2",
        ),
        dimensions=Dimensions(
            length=SpecField[float](value=12.0, provenance=E, confidence=0.97,
                                    source="email_body:L2"),
            width=SpecField[float](value=10.0, provenance=E, confidence=0.97,
                                   source="email_body:L2"),
            depth=SpecField[float](value=8.0, provenance=E, confidence=0.97,
                                   source="email_body:L2"),
            # units + convention not stated -> defaults pass fills them
        ),
        board=Board(
            strength_spec=SpecField[str](value="32 ECT", provenance=E,
                                         confidence=0.99, source="email_body:L2"),
            strength_basis=SpecField[str](value="ect", provenance=E,
                                          confidence=0.99, source="email_body:L2"),
            # flute not stated -> defaults pass fills it (C), needs confirmation
        ),
        print_spec=PrintSpec(
            colors=SpecField[int](value=2, provenance=E, confidence=0.95,
                                  source="email_body:L2"),
            artwork_ref=SpecField[str](value="SPEC-4471/artwork", provenance=R,
                                       confidence=0.83,
                                       source="order_history:SPEC-4471"),
        ),
        quantity=Quantity(
            as_requested=SpecField[str](value="one truckload", provenance=E,
                                        confidence=0.99, source="email_body:L2"),
            # units + calc_basis filled by the truckload calculator
        ),
    )


RAW_EMAIL = """\
From:    orders@acmefoods.example
To:      quotes@yourboxplant.example
Subject: need pricing

Hey --

Can you quote us a truckload of the 12x10x8 RSCs, 32 ECT,
2-color print like the last run. Same artwork.

Need it pretty quick, we're comparing a couple suppliers.

Thanks,
Dana
Acme Foods purchasing
"""
