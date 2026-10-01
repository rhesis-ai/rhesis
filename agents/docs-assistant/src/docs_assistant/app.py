"""Docs Assistant FastAPI application.

With the tracing bridge, the only module that imports the Rhesis SDK. Tracing is additive:
without Rhesis credentials the app runs the same, just without shipping spans or registering
the endpoint.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.clients import DisabledClient

from docs_assistant import tracing
from docs_assistant.config import get_settings
from docs_assistant.corpus.cache import CorpusCache, DocsUnavailable
from docs_assistant.corpus.fetcher import DocsFetcher
from docs_assistant.models import build_model
from docs_assistant.runner import run_turn
from docs_assistant.schemas import TurnResponse
from docs_assistant.session import ConversationStore

logger = logging.getLogger(__name__)

load_dotenv()

# Gate on the credentials themselves: RhesisClient installs OTel providers and starts shipping
# spans as soon as it is built, so without a key it would export against an unknown project.
if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
    rhesis_client = RhesisClient.from_environment()
    tracing.install()
else:
    logger.info("RHESIS_API_KEY/RHESIS_PROJECT_ID not set; traces will NOT be shipped.")
    rhesis_client = DisabledClient()

# What the Rhesis platform sends and reads back when it tests this app as an endpoint.
REQUEST_MAPPING = {
    "message": "{{ input }}",
    "conversation_id": "{{ session_id | default(none) }}",
}
RESPONSE_MAPPING = {
    "output": "{{ response }}",
    "session_id": "{{ conversation_id }}",
    "metadata": (
        "{{ {'route': route, 'turn': turn, "
        "'citations': citations | map(attribute='url') | list, "
        "'docs_as_of': docs_as_of | string, 'docs_stale': docs_stale, "
        "'limits_hit': limits_hit} | tojson }}"
    ),
}


class _State:
    cache: CorpusCache | None = None
    store: ConversationStore | None = None
    started = False
    model_ready = False


state = _State()


def make_store() -> ConversationStore:
    return ConversationStore(idle_ttl=get_settings().session_ttl)


def make_cache() -> CorpusCache:
    settings = get_settings()
    fetcher = DocsFetcher(settings.docs_base_url, timeout=settings.fetch_timeout)
    return CorpusCache(fetcher, ttl=settings.cache_ttl)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load the docs before serving. A failed load or a missing key doesn't stop the server:
    /health reports it, and /chat answers 503 with the reason."""
    state.cache = state.cache or make_cache()
    state.store = state.store or make_store()
    try:
        snapshot = await state.cache.get()
        logger.info("Docs loaded: %d pages", len(snapshot.pages))
    except DocsUnavailable as exc:
        logger.warning("Docs not loaded at startup: %s", exc)
    try:
        build_model("answer")
        state.model_ready = True
    except RuntimeError as exc:
        logger.warning("Model not ready: %s", exc)
    # Dial out the connector now that uvicorn's loop runs; @endpoint registered at import time,
    # before the loop existed. A no-op under DisabledClient.
    rhesis_client.start_connector()
    state.started = True
    yield
    state.started = False


app = FastAPI(
    title="Docs Assistant",
    description="Answers Rhesis questions from the live docs at docs.rhesis.ai, with citations.",
    version="0.1.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "Docs Assistant",
        "description": "Answers Rhesis questions from https://docs.rhesis.ai, with citations.",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "conversations": "GET /conversations",
            "delete_conversation": "DELETE /conversations/{conversation_id}",
        },
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    cache = state.cache
    snapshot = cache.snapshot if cache else None
    return {
        "status": "healthy",
        "docs": cache.status() if cache else "unavailable",
        "docs_as_of": snapshot.fetched_at.isoformat() if snapshot else None,
        "pages": len(snapshot.pages) if snapshot else 0,
        "model_ready": state.model_ready,
    }


@endpoint(
    name="docs_assistant_chat",
    description="Answers Rhesis questions from the live docs at docs.rhesis.ai, with citations.",
    request_mapping=REQUEST_MAPPING,
    response_mapping=RESPONSE_MAPPING,
)
async def chat_endpoint_traced(message: str, conversation_id: str | None = None) -> dict:
    """One turn through @endpoint, which opens the Rhesis turn root and registers the endpoint.

    Returns the turn as JSON-ready data: the SDK's tracer json-dumps the result, and a raw
    model dump would fail on the datetime in docs_as_of."""
    response = await run_turn(
        message, cache=state.cache, store=state.store, conversation_id=conversation_id
    )
    return response.model_dump(mode="json")


@app.post("/chat", response_model=TurnResponse)
async def chat(request: ChatRequest) -> TurnResponse:
    if not state.started or state.cache is None:
        raise HTTPException(status_code=503, detail="Service starting up")
    try:
        result = await chat_endpoint_traced(
            message=request.message, conversation_id=request.conversation_id
        )
        return TurnResponse.model_validate(result)
    except DocsUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="docs_unavailable: the docs site can't be reached"
        ) from exc
    except RuntimeError as exc:
        # A missing key is the operator's to fix, so its message travels; anything else stays ours.
        if "API key" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        logger.error("Chat turn failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing request") from exc
    except Exception as exc:
        logger.error("Chat turn failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing request") from exc


@app.get("/conversations")
async def list_conversations() -> dict[str, Any]:
    """Conversation ids held in memory, with their turn counts."""
    conversations = state.store.list() if state.store else {}
    return {"conversations": conversations, "count": len(conversations)}


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, str]:
    if state.store is None or not state.store.delete(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": conversation_id}


__all__ = ["ChatRequest", "app", "chat_endpoint_traced"]
