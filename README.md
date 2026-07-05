# Quick Quotes — `complete_validate → clarify` loop (MVP skeleton)

A minimal, runnable LangGraph slice of the Quick Quotes agent:

```
START → complete_validate ──(gaps / unconfirmed defaults / blocking flags)──→ clarify
              ↑                                                                  │
              └────────────── corrections re-enter as HUMAN_CONFIRMED ───────────┘
        complete_validate ──(clean)──→ price (freeze + CoreERP stub) → END
```

## Layout

```
quickquotes/   the agent: spec, nodes, graph, fixtures (importable package)
api/           FastAPI delivery mechanism (one of several possible)
ui/            Vite + React + TS estimator workbench (own toolchain)
tests/         invariants on the deterministic core; no LLM tests by design
run_demo.py    CLI walkthrough of the interrupt/resume loop
```

## Run the CLI demo

```bash
uv sync --extra api --extra dev     # or: pip install -e ".[api,dev]"
uv run run_demo.py                  # or: python run_demo.py
uv run pytest                       # 7 invariant tests on the deterministic core
```

The demo deliberately resumes the first interrupt with *partial* answers to
show the loop re-interrupting — pricing is unreachable until the artifact is
clean.

## Run the workbench (API + UI)

```bash
cd ui && npm install && npm run build && cd ..
uv run uvicorn api.main:app --port 8000
# open http://localhost:8000
```

Dev mode with hot reload: `uvicorn api.main:app --reload --port 8000` in one
terminal, `cd ui && npm run dev` in another (Vite proxies `/api` to :8000).

Flow in the UI: **Load quote request** → draft spec renders with provenance
badges (hover a badge for its source), one red gap input (ship-to), amber
Confirm buttons for the defaults → **Apply answers & revalidate** → partial
answers re-interrupt, full answers freeze the spec and render the quote card
with its `spec_hash`.

## Files

- `quickquotes/quote_spec.py` — `QuoteSpec` with provenance-carrying
  `SpecField[T]` (extracted / resolved / defaulted / inferred / calculated /
  human_confirmed)
- `quickquotes/fixtures.py` — plant master data + a draft spec as
  `extract_resolve` would emit it from a messy email
- `quickquotes/nodes.py` — deterministic validation passes, `clarify`
  interrupt, `price` stub, and the pure routing predicate
- `quickquotes/graph.py` — graph assembly (shared by CLI demo and API)
- `quickquotes/__init__.py` — the public surface: `QuoteSpec`, `SpecField`,
  `Provenance`, `build_graph`, `get_field`, `set_field`
- `api/main.py` — `POST /api/quotes`, `GET /api/quotes/{id}`,
  `POST /api/quotes/{id}/resume`; serves `ui/dist` when built
- `ui/` — provenance badges, gap inputs, confirm chips, quote card. Tokens
  at the top of `ui/src/styles.css` — restyling is a five-minute job.

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
