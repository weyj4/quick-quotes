"""Quick Quotes API — thin HTTP wrapper around the LangGraph graph.

Endpoints (this is the whole surface; it falls directly out of the graph):

    POST /api/quotes                    start a quote thread (demo: fixture email)
    GET  /api/quotes/{thread_id}        current state + pending review, if any
    POST /api/quotes/{thread_id}/resume estimator answers -> Command(resume=...)

Run:  uvicorn api.main:app --reload --port 8000
If ui/dist exists (npm run build), it is served at /.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel

from quickquotes import build_graph
from quickquotes.fixtures import RAW_EMAIL, draft_spec_fixture

app = FastAPI(title="Quick Quotes")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

# Single in-process graph with MemorySaver: fine for the demo.
# Cloud Run: build_graph(PostgresSaver(...)) and threads survive restarts.
graph = build_graph()

# demo bookkeeping: raw request per thread (in prod this lives in the DB/state)
RAW_BY_THREAD: dict[str, str] = {}


class ResumeBody(BaseModel):
    answers: dict[str, object]


def snapshot(thread_id: str) -> dict:
    """Serialize current graph state for the UI."""
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    if not state.values:
        raise HTTPException(404, f"no quote thread {thread_id}")

    pending = None
    for task in state.tasks:
        for intr in getattr(task, "interrupts", ()):
            pending = intr.value

    spec = state.values["spec"]
    quote = state.values.get("quote")
    return {
        "thread_id": thread_id,
        "raw_request": RAW_BY_THREAD.get(thread_id, ""),
        "spec": spec.model_dump(mode="json"),
        "quote": quote,
        "pending": pending,
        "status": "priced" if quote else ("needs_review" if pending else "running"),
    }


@app.post("/api/quotes")
def start_quote() -> dict:
    """Start a new quote thread. Demo: the fixture email's draft spec stands in
    for extract_resolve output; in the full build this endpoint accepts the raw
    email/attachments and the graph runs intake -> extract_resolve first."""
    thread_id = f"q-{uuid.uuid4().hex[:8]}"
    RAW_BY_THREAD[thread_id] = RAW_EMAIL
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke({"spec": draft_spec_fixture(), "quote": None}, config)
    return snapshot(thread_id)


@app.get("/api/quotes/{thread_id}")
def get_quote(thread_id: str) -> dict:
    return snapshot(thread_id)


@app.post("/api/quotes/{thread_id}/resume")
def resume_quote(thread_id: str, body: ResumeBody) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    if not state.values:
        raise HTTPException(404, f"no quote thread {thread_id}")
    if not any(getattr(t, "interrupts", ()) for t in state.tasks):
        raise HTTPException(409, "no pending review on this quote")
    if not body.answers:
        raise HTTPException(422, "answers must not be empty")

    graph.invoke(Command(resume=body.answers), config)
    return snapshot(thread_id)


# Serve the built UI if present (single-container Cloud Run story).
ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "ui" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")
