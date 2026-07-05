# Quick Quotes — `complete_validate → clarify` loop (MVP skeleton)

A minimal, runnable LangGraph slice of the Quick Quotes agent:

```
START → complete_validate ──(gaps / unconfirmed defaults / blocking flags)──→ clarify
              ↑                                                                  │
              └────────────── corrections re-enter as HUMAN_CONFIRMED ───────────┘
        complete_validate ──(clean)──→ price (freeze + CoreERP stub) → END
```

## Run

```bash
pip install langgraph pydantic
python run_demo.py
```

The demo deliberately resumes the first interrupt with *partial* answers to
show the loop re-interrupting — pricing is unreachable until the artifact is
clean.

## Files

- `quote_spec.py` — `QuoteSpec` with provenance-carrying `SpecField[T]`
  (extracted / resolved / defaulted / inferred / calculated / human_confirmed)
- `fixtures.py` — plant master data + a draft spec as `extract_resolve` would
  emit it from a messy email ("truckload of 12x10x8 RSCs, 32 ECT, like last run")
- `nodes.py` — deterministic validation passes, `clarify` interrupt, `price`
  stub, and the pure routing predicate
- `run_demo.py` — graph assembly + two-interrupt demo run

## Design invariants (property-test targets)

1. Passes never overwrite `EXTRACTED` or `HUMAN_CONFIRMED` values →
   the clarify loop is idempotent and safe to re-run.
2. No LLM downstream of the draft spec. Deterministic passes resolve, default,
   calculate, or flag — they never guess.
3. Only `frozen` specs reach pricing; every quote logs `(spec_version,
   spec_hash)` for reproducibility.
4. Routing is a pure predicate over the artifact (`route_after_validation`),
   attached as a conditional edge — nodes do work, edges route.

## Known demo shortcuts

- `MemorySaver` checkpointer — production on Cloud Run needs the Postgres
  checkpointer (Cloud SQL); interrupts are async and containers are stateless.
- Custom Pydantic types in checkpoint state emit a msgpack deserialization
  warning on recent LangGraph; register them via `allowed_msgpack_modules`
  or store `spec` as a dict at the state boundary.
- The truckload calculator's constants are placeholders (real cube math per
  box style/pallet pattern belongs in a config table, same provenance idea).
- `price` stubs CoreERP: unit cost is hardcoded; margin comes from a
  pretend policy table. The point is the *shape* — pure function of the
  frozen spec, LLM nowhere in it.
