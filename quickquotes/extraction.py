"""extract_resolve: the one LLM stage.

Design rules enforced here:

  1. The model emits an extraction-only schema (value + confidence + verbatim
     evidence, everything nullable). It cannot emit provenance — EXTRACTED is
     stamped by our mapping code, and RESOLVED only ever comes from lookups.
  2. Resolution is deterministic. Sender domain -> customer account and
     "like the last run" -> prior spec are master-data/order-history lookups
     performed in map_extraction_to_spec, not by the model.
  3. Gaps stay gaps. The prompt forbids guessing; the schema has no field a
     default could hide in; and downstream complete_validate re-derives
     anything derivable, so a hallucinated value would have to survive three
     independent checks plus human review to reach pricing.

Extractor selection: GeminiExtractor when GOOGLE_API_KEY / GEMINI_API_KEY or
Vertex env vars are configured, StubExtractor otherwise (offline demo, tests).
"""
from __future__ import annotations

import os
import re
from typing import Optional, Protocol

from langsmith import traceable
from pydantic import BaseModel, Field as PField

from quickquotes import fixtures as fx
from quickquotes.quote_spec import Provenance, QuoteSpec, SpecField


# ------------------------------------------------------- extraction schema
class XF(BaseModel):
    """One extracted field: what the request said, verbatim, and how sure."""
    value: Optional[str] = None
    confidence: Optional[float] = PField(default=None, ge=0, le=1)
    evidence: Optional[str] = PField(
        default=None, description="verbatim snippet from the request")


class XFNum(BaseModel):
    value: Optional[float] = None
    confidence: Optional[float] = PField(default=None, ge=0, le=1)
    evidence: Optional[str] = None


class XFInt(BaseModel):
    value: Optional[int] = None
    confidence: Optional[float] = PField(default=None, ge=0, le=1)
    evidence: Optional[str] = None


class ExtractionResult(BaseModel):
    """What the model returns. Flat, nullable, no provenance, no defaults."""
    style: XF = XF()                     # e.g. RSC, die-cut, HSC — as stated
    length_in: XFNum = XFNum()
    width_in: XFNum = XFNum()
    depth_in: XFNum = XFNum()
    dim_units: XF = XF()                 # ONLY if stated
    dim_convention: XF = XF()            # inside/outside — ONLY if stated
    strength_spec: XF = XF()             # verbatim: "32 ECT", "200# test"
    strength_basis: XF = XF()            # ect | mullen — only if derivable
    flute: XF = XF()                     # ONLY if stated
    print_colors: XFInt = XFInt()
    print_coverage: XF = XF()            # ONLY if stated
    quantity_text: XF = XF()             # verbatim: "one truckload", "5k"
    quantity_units: XFInt = XFInt()      # ONLY if a number is stated
    ship_to_text: XF = XF()              # destination as stated, if any
    prior_order_reference: XF = XF()     # "like the last run", "same as March"
    customer_name: XF = XF()


PROMPT = """You are an intake clerk for a corrugated box plant. Read the quote
request below and extract ONLY what it states. Rules:

- If a field is not stated in the request, leave it null. NEVER guess,
  NEVER apply industry defaults, NEVER infer units or conventions that are
  not written. A null is a correct answer; a guess is a defect.
- For every non-null value, include a short verbatim evidence snippet copied
  from the request, and a confidence between 0 and 1.
- style must be one of the stated box styles if named (e.g. RSC, HSC,
  die-cut); copy the request's wording into evidence.
- strength_basis: "ect" if the request uses ECT, "mullen" if it uses # / lb
  burst test wording; null otherwise.
- quantity_units only if an explicit numeric count is stated. Phrases like
  "a truckload" go in quantity_text with quantity_units left null.
- prior_order_reference: any phrase referring to previous orders or specs.

QUOTE REQUEST:
---
{request}
---
"""


# ------------------------------------------------------------- extractors
class Extractor(Protocol):
    name: str
    def extract(self, raw_request: str) -> ExtractionResult: ...


class GeminiExtractor:
    """Structured output against ExtractionResult. temperature=0 narrows
    variance; determinism is not claimed — the spec artifact is the
    deterministic boundary, not the model call."""
    name = "gemini"

    def __init__(self, model: str | None = None):
        from google import genai
        self.client = genai.Client()   # reads GOOGLE_API_KEY / Vertex env
        self.model = model or os.environ.get("QQ_GEMINI_MODEL",
                                             "gemini-2.5-flash")

    @traceable(name="gemini_extract", run_type="llm",
               metadata={"model": "gemini-2.5-flash"})
    def extract(self, raw_request: str) -> ExtractionResult:
        resp = self.client.models.generate_content(
            model=self.model,
            contents=PROMPT.format(request=raw_request),
            config={
                "response_mime_type": "application/json",
                "response_schema": ExtractionResult,
                "temperature": 0,
            },
        )
        return resp.parsed


class StubExtractor:
    """Deterministic regex extraction for offline demo and the golden test.
    Deliberately narrow: handles the patterns in realistic emails, guesses
    nothing, leaves gaps like the prompt tells the real model to."""
    name = "stub"

    def extract(self, raw_request: str) -> ExtractionResult:
        text = raw_request
        r = ExtractionResult()

        m = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)",
                      text, re.I)
        if m:
            ev = m.group(0)
            r.length_in = XFNum(value=float(m.group(1)), confidence=0.97, evidence=ev)
            r.width_in = XFNum(value=float(m.group(2)), confidence=0.97, evidence=ev)
            r.depth_in = XFNum(value=float(m.group(3)), confidence=0.97, evidence=ev)

        m = re.search(r"\b(RSC|HSC|FOL|die[- ]cut)s?\b", text, re.I)
        if m:
            r.style = XF(value=m.group(1).upper().replace(" ", "-"),
                         confidence=0.99, evidence=m.group(0))

        m = re.search(r"(\d+)\s*ECT", text, re.I)
        if m:
            r.strength_spec = XF(value=f"{m.group(1)} ECT", confidence=0.99,
                                 evidence=m.group(0))
            r.strength_basis = XF(value="ect", confidence=0.99,
                                  evidence=m.group(0))
        else:
            m = re.search(r"(\d+)\s*#(?:\s*test)?", text)
            if m:
                r.strength_spec = XF(value=f"{m.group(1)}#", confidence=0.95,
                                     evidence=m.group(0))
                r.strength_basis = XF(value="mullen", confidence=0.95,
                                      evidence=m.group(0))

        m = re.search(r"(\d+)[- ]colou?r", text, re.I)
        if m:
            r.print_colors = XFInt(value=int(m.group(1)), confidence=0.95,
                                   evidence=m.group(0))

        m = re.search(r"\b(a|one|\d+)\s+truckloads?\b", text, re.I)
        if m:
            r.quantity_text = XF(value=f"{m.group(1)} truckload".lower(),
                                 confidence=0.99, evidence=m.group(0))
        else:
            m = re.search(r"\b([\d,]{3,})\s*(?:units|boxes|pcs)\b", text, re.I)
            if m:
                n = int(m.group(1).replace(",", ""))
                r.quantity_text = XF(value=m.group(0), confidence=0.95,
                                     evidence=m.group(0))
                r.quantity_units = XFInt(value=n, confidence=0.95,
                                         evidence=m.group(0))

        m = re.search(r"(like the last run|same as [^.,\n]+|last (?:order|run))",
                      text, re.I)
        if m:
            r.prior_order_reference = XF(value=m.group(0), confidence=0.85,
                                         evidence=m.group(0))

        m = re.search(r"(?:ship|deliver)(?:\s+it)?\s+to\s+([^\n.,]+)", text, re.I)
        if m:
            r.ship_to_text = XF(value=m.group(1).strip(), confidence=0.9,
                                evidence=m.group(0))
        return r


def get_extractor() -> Extractor:
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") \
            or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
        return GeminiExtractor()
    return StubExtractor()

# Canonicalization: the model extracts VERBATIM (evidence discipline); master
# data lookups are EXACT matches. This deterministic code layer bridges the
# two. Verbatim text survives in the SpecField note; only .value is canonical.
def _canon_style(v: str) -> str:
    s = re.sub(r"[^A-Za-z]", "", v).upper()
    if s.endswith("S") and s[:-1] in fx.SUPPORTED_STYLES:
        s = s[:-1]                                    # "RSCs" -> "RSC"
    return s


def _canon_flute(v: str) -> str:
    s = re.sub(r"(?i)[\s\-]*(flutes?|double[\s\-]?wall)", "", v.strip())
    return re.sub(r"[^A-Za-z]", "", s).upper()        # "C-flute" -> "C", "BC double-wall" -> "BC"


def _canon_basis(v: str) -> str:
    return v.strip().lower()                          # "ECT" -> "ect"


# ------------------------------------------- deterministic mapping + lookups
def _sf(xf, cast=None) -> SpecField:
    """Extraction field -> SpecField with EXTRACTED provenance."""
    if xf.value is None:
        return SpecField()
    value = cast(xf.value) if cast else xf.value
    return SpecField(
        value=value,
        provenance=Provenance.EXTRACTED,
        confidence=xf.confidence,
        source="email_body",
        note=f'"{xf.evidence}"' if xf.evidence else None,
    )


def map_extraction_to_spec(x: ExtractionResult, sender: str | None) -> QuoteSpec:
    """Stamp EXTRACTED provenance; run deterministic resolution. The only
    provenances minted here are EXTRACTED (model) and RESOLVED (lookups)."""
    spec = QuoteSpec()

    # spec.style = _sf(x.style)
    spec.style = _sf(x.style, _canon_style)
    spec.dimensions.length = _sf(x.length_in)
    spec.dimensions.width = _sf(x.width_in)
    spec.dimensions.depth = _sf(x.depth_in)
    spec.dimensions.units = _sf(x.dim_units)
    spec.dimensions.convention = _sf(x.dim_convention)
    spec.board.strength_spec = _sf(x.strength_spec)
    # spec.board.strength_basis = _sf(x.strength_basis)
    spec.board.strength_basis = _sf(x.strength_basis, _canon_basis)
    # spec.board.flute = _sf(x.flute)
    spec.board.flute = _sf(x.flute, _canon_flute)
    spec.print_spec.colors = _sf(x.print_colors, int)
    spec.print_spec.coverage = _sf(x.print_coverage)
    spec.quantity.as_requested = _sf(x.quantity_text)
    spec.quantity.units = _sf(x.quantity_units, int)

    # -- resolution: sender domain -> customer account (master data lookup)
    domain = sender.split("@")[-1].lower().strip() if sender and "@" in sender else None
    account = fx.DOMAIN_TO_ACCOUNT.get(domain) if domain else None
    if account:
        spec.customer_account = SpecField(
            value=account, provenance=Provenance.RESOLVED, confidence=0.98,
            source=f"sender_domain:{domain}",
            note="matched by sender domain",
        )

    # -- resolution: ship-to text -> known ship-to for the account
    if account and x.ship_to_text.value:
        cust = fx.CUSTOMER_MASTER.get(account, {})
        needle = x.ship_to_text.value.lower()
        matches = [k for k in cust.get("ship_tos", {})
                   if k.lower() in needle or needle in k.lower()]
        if len(matches) == 1:
            spec.ship_to = SpecField(
                value=matches[0], provenance=Provenance.RESOLVED,
                confidence=0.9, source="customer_master:ship_tos",
                note=f'matched "{x.ship_to_text.value}"',
            )

    # -- resolution: "like the last run" -> most recent matching prior spec
    if account and x.prior_order_reference.value:
        history = fx.ORDER_HISTORY.get(account, [])
        if history:
            prior = history[0]   # most recent
            spec.prior_spec_ref = SpecField(
                value=prior["spec_id"], provenance=Provenance.RESOLVED,
                confidence=0.83, source=f"order_history:{prior['date']}",
                note=f'"{x.prior_order_reference.value}" -> most recent order',
            )
            if prior.get("artwork_ref") and spec.print_spec.artwork_ref.is_gap:
                spec.print_spec.artwork_ref = SpecField(
                    value=prior["artwork_ref"], provenance=Provenance.RESOLVED,
                    confidence=0.83, source=f"order_history:{prior['spec_id']}",
                )
    return spec
