"""Dr-Rhesis FastAPI application.

Rhesis concerns — client construction, auto_instrument, @endpoint — live only here.
Nothing else under ``dr_rhesis`` imports from ``rhesis.sdk``.
"""

from __future__ import annotations

import functools
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import anyio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.clients import DisabledClient

# Must be set before any `haystack` import (pulled in transitively by
# dr_rhesis.session) so span input/output content is captured, not dropped.
# None of the imports above pull in haystack, so this is early enough.
os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")

from dr_rhesis.session import default_store, run_chat_turn  # noqa: E402
from dr_rhesis.state import Phase  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
    rhesis_client = RhesisClient.from_environment()
else:
    logger.info(
        "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; using DisabledClient. "
        "Traces will NOT be shipped to the backend."
    )
    rhesis_client = DisabledClient()

# Pending: SDK Haystack integration is not on main yet.
# auto_instrument("haystack")

_startup_validated: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_validated
    logger.info("Initialising Dr-Rhesis Haystack pipeline...")
    from dr_rhesis.session import get_default_pipeline

    # Build the shared pipeline + generator once so per-turn requests reuse it.
    get_default_pipeline()
    _startup_validated = True
    logger.info(
        "Dr-Rhesis ready: intent_router + gathering_brain + summary_writer + safety_critic"
    )
    yield
    _startup_validated = False
    # Flush any pending Haystack/Rhesis spans before the process exits.
    try:
        from haystack.tracing import tracer as haystack_tracer

        actual = getattr(haystack_tracer, "actual_tracer", None)
        if actual is not None and hasattr(actual, "flush"):
            actual.flush()
    except Exception:  # pragma: no cover - best-effort shutdown flush
        logger.debug("No Haystack tracer to flush on shutdown", exc_info=True)


app = FastAPI(
    title="Dr-Rhesis Agent",
    description=(
        "A Haystack multi-agent visit-preparation assistant. "
        "Collects structured symptom history and produces a timeline plus "
        "questions for your clinician. Does not diagnose or prescribe."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message.")
    conversation_id: str | None = Field(
        None,
        description="Optional conversation id for session grouping.",
    )


class ChatResponse(BaseModel):
    response: str = Field(..., description="The assistant reply.")
    conversation_id: str = Field(..., description="Conversation id for session grouping.")
    phase: Phase = Field(..., description="Current conversation phase.")
    turn: int = Field(..., description="Turn counter for this conversation.")


def _chat_response_from_result(result: dict[str, Any]) -> ChatResponse:
    state = result["state"]
    return ChatResponse(
        response=result["response"],
        conversation_id=result["conversation_id"],
        phase=state.phase,
        turn=state.turn,
    )


@app.get("/")
async def root():
    return {
        "message": "Welcome to Dr-Rhesis",
        "description": (
            "A Haystack visit-preparation assistant. Use /chat to start a conversation."
        ),
        "endpoints": {
            "chat": "/chat",
            "conversations": "/conversations",
            "health": "/health",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "startup_validated": _startup_validated}


@endpoint(
    name="dr_rhesis_chat",
    description="Chat with the Dr-Rhesis Haystack agent.",
    request_mapping={
        "message": "{{ input }}",
        "conversation_id": "{{ session_id | default(none) }}",
    },
    response_mapping={
        "output": "{{ response }}",
        "session_id": "{{ conversation_id }}",
        "metadata": "{{ {'phase': phase, 'turn': turn} | tojson }}",
    },
)
async def chat_endpoint_traced(
    message: str,
    conversation_id: str | None = None,
) -> ChatResponse:
    logger.info("Dr-Rhesis chat turn (conversation=%s)", conversation_id)
    # run_chat_turn drives the Haystack pipeline + Gemini calls synchronously
    # (blocking I/O). Offload to a worker thread so this async handler does not
    # block the event loop. anyio copies the current contextvars into the worker,
    # preserving the active trace/span context for the SDK @endpoint span.
    result = await anyio.to_thread.run_sync(
        functools.partial(run_chat_turn, message, conversation_id=conversation_id)
    )
    return _chat_response_from_result(result)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not _startup_validated:
        raise HTTPException(status_code=503, detail="Dr-Rhesis not initialised")
    try:
        return await chat_endpoint_traced(
            message=request.message,
            conversation_id=request.conversation_id,
        )
    except RuntimeError as exc:
        if "GOOGLE_API_KEY" in str(exc) or "GEMINI_API_KEY" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail="Error processing request") from exc
    except Exception as exc:
        logger.error("Error in /chat: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing request") from exc


@app.get("/conversations")
async def list_conversations():
    return default_store.list_conversations()


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    if not default_store.delete(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": f"Conversation {conversation_id} deleted"}
