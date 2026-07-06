"""Extractor tests.

The stub extractor runs in CI; the same assertions apply to GeminiExtractor
output (run with GOOGLE_API_KEY set to exercise the live model — the golden
test is the acceptance bar for any extractor implementation).
"""
import pytest

from quickquotes import Provenance, get_field
from quickquotes.extraction import (StubExtractor, get_extractor,
                                    map_extraction_to_spec)
from quickquotes.fixtures import RAW_EMAIL, draft_spec_fixture


def extract_spec(raw=RAW_EMAIL, sender="orders@acmefoods.example"):
    return map_extraction_to_spec(StubExtractor().extract(raw), sender)


# ------------------------------------------------------------- golden test
GOLDEN_PATHS = [
    "customer_account", "style", "prior_spec_ref",
    "dimensions.length", "dimensions.width", "dimensions.depth",
    "board.strength_spec", "board.strength_basis",
    "print_spec.colors", "print_spec.artwork_ref",
]


def test_golden_extraction_matches_fixture_values():
    """The fixture is the expected output of extraction over RAW_EMAIL."""
    extracted = extract_spec()
    fixture = draft_spec_fixture()
    for path in GOLDEN_PATHS:
        e, f = get_field(extracted, path), get_field(fixture, path)
        assert e.value == f.value, f"{path}: {e.value!r} != {f.value!r}"


def test_golden_quantity_is_textual_not_numeric():
    """'a truckload' must land in as_requested; units stay a gap for the
    deterministic calculator — an extractor that emits a number here is
    guessing."""
    spec = extract_spec()
    assert "truckload" in spec.quantity.as_requested.value
    assert spec.quantity.units.is_gap


# ---------------------------------------------------------- gap discipline
def test_unstated_fields_stay_gaps():
    """Nothing in RAW_EMAIL states flute, units, convention, or coverage.
    The extractor must not fill them — defaults are complete_validate's job."""
    spec = extract_spec()
    for path in ("board.flute", "dimensions.units", "dimensions.convention",
                 "print_spec.coverage"):
        assert get_field(spec, path).is_gap, f"{path} should be a gap"


def test_no_resolution_without_master_data_match():
    """Unknown sender -> no customer account, no prior-spec resolution,
    even when the email references a prior order."""
    spec = extract_spec(sender="buyer@unknown-plant.example")
    assert spec.customer_account.is_gap
    assert spec.prior_spec_ref.is_gap


# ------------------------------------------------------ provenance minting
def test_extractor_mints_only_extracted_and_resolved():
    spec = extract_spec()
    allowed = {Provenance.EXTRACTED, Provenance.RESOLVED, None}
    for path in GOLDEN_PATHS + ["board.flute", "quantity.units",
                                "dimensions.units", "ship_to"]:
        assert get_field(spec, path).provenance in allowed


def test_extracted_values_carry_evidence_and_confidence():
    spec = extract_spec()
    for path in ("style", "board.strength_spec", "dimensions.length"):
        f = get_field(spec, path)
        assert f.provenance == Provenance.EXTRACTED
        assert f.confidence and 0 < f.confidence <= 1
        assert f.note, f"{path} missing verbatim evidence"


def test_default_extractor_without_credentials_is_stub(monkeypatch):
    for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(var, raising=False)
    assert get_extractor().name == "stub"
