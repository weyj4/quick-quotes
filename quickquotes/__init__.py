"""Quick Quotes agent — the graph, its artifact, and its fixtures.

Public surface (import from here; everything else is internals):

    from quickquotes import QuoteSpec, SpecField, Provenance, build_graph
"""
from quickquotes.graph import build_graph
from quickquotes.quote_spec import (
    Provenance,
    QuoteSpec,
    SpecField,
    get_field,
    set_field,
)

__all__ = [
    "build_graph",
    "Provenance",
    "QuoteSpec",
    "SpecField",
    "get_field",
    "set_field",
]
