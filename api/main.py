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
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from quickquotes import build_graph
from quickquotes.fixtures import RAW_EMAIL

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


class StartBody(BaseModel):
    email: str | None = None
    sender: str | None = None


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
        "extractor": state.values.get("extractor_name"),
        "spec": spec.model_dump(mode="json"),
        "quote": quote,
        "pending": pending,
        "status": "priced" if quote else ("needs_review" if pending else "running"),
    }


DEMO_SENDER = "orders@acmefoods.example"


def _sender_from_email(text: str) -> str | None:
    for line in text.splitlines():
        if line.lower().startswith("from:"):
            return line.split(":", 1)[1].strip().strip("<>")
    return None


@app.post("/api/quotes")
def start_quote(body: StartBody | None = None) -> dict:
    """Start a quote thread from a raw email. The graph runs
    extract_resolve -> complete_validate and pauses at the first review.
    No body -> the demo fixture email."""
    raw = (body.email if body and body.email else RAW_EMAIL)
    sender = (body.sender if body and body.sender else None)         or _sender_from_email(raw) or DEMO_SENDER

    thread_id = f"q-{uuid.uuid4().hex[:8]}"
    RAW_BY_THREAD[thread_id] = raw
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "run_name": "quote_request",
        "tags": ["quickquotes", "gemini"],
        "metadata": {"sender": sender or "unknown"},
    }
    graph.invoke({"raw_request": raw, "sender": sender,
                  "spec": None, "quote": None}, config)
    return snapshot(thread_id)


@app.get("/api/quotes/{thread_id}")
def get_quote(thread_id: str) -> dict:
    return snapshot(thread_id)


@app.post("/api/quotes/{thread_id}/resume")
def resume_quote(thread_id: str, body: ResumeBody) -> dict:
    config: RunnableConfig = {"configurable": {"thread_id": thread_id},
                          "run_name": "quote_resume",
                          "tags": ["quickquotes"]}
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
