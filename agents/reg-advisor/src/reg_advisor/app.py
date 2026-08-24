"""Reg-Advisor FastAPI application.

This is the only module that imports the Rhesis SDK; everything below it is
plain Google ADK. Tracing is additive: with no Rhesis credentials the app runs
exactly as before, just without shipping spans.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.clients import DisabledClient
from rhesis.sdk.telemetry import auto_instrument

from reg_advisor.knowledge import get_knowledge_base, validate_knowledge_base
from reg_advisor.session import default_store, get_default_agent, run_chat_turn_async
from reg_advisor.state import Phase

logger = logging.getLogger(__name__)

load_dotenv()

# Initialise the Rhesis client so ``@endpoint`` and ``auto_instrument`` have a
# tracer provider to attach to. Gate on the credentials themselves:
# ``RhesisClient.__init__`` eagerly installs OTEL providers and tries to ship
# spans, so constructing it without an API key / project id would export against
# ``project_id="unknown"`` with ``Authorization: Bearer None``. Falling back to
# ``DisabledClient`` before construction is the only way to keep telemetry off.
if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
    rhesis_client = RhesisClient.from_environment()
else:
    logger.info(
        "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; using DisabledClient. "
        "Traces will NOT be shipped to the backend."
    )
    rhesis_client = DisabledClient()

# THE line under test: turn on the SDK's Google ADK integration. It must come
# after the client, which is what installs the provider whose exporter the
# integration wraps.
auto_instrument("google_adk")

_startup_validated = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate the knowledge base and warm the agent before serving.

    A knowledge base that fails validation stops the server rather than degrading quietly: a
    dangling citation discovered mid-conversation is far worse than a failed boot. A missing API
    key does not stop the server — the knowledge base endpoints and /health still work, and
    /chat reports the real reason.
    """
    global _startup_validated
    base = validate_knowledge_base()
    logger.info(
        "Knowledge base validated: %d nodes, %d trees, verified %s",
        len(base.nodes),
        len(base.trees),
        base.verified_on,
    )
    try:
        get_default_agent()
        logger.info("Coordinator agent ready.")
    except RuntimeError as exc:
        logger.warning("Agent not built at startup: %s", exc)

    # Dial out the connector now that uvicorn's loop is running. @endpoint registered at
    # import time, which uvicorn does before asyncio.run(), so the connection was deferred
    # and the Playground would never see this app. No-op under DisabledClient.
    rhesis_client.start_connector()

    _startup_validated = True
    yield
    _startup_validated = False


app = FastAPI(
    title="Reg-Advisor",
    description="EU and US health product regulatory assistant. Not legal advice.",
    version="0.1.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    phase: Phase
    turn: int


def _chat_response_from_result(result: dict[str, Any]) -> ChatResponse:
    state = result["state"]
    return ChatResponse(
        response=result["response"],
        conversation_id=result["conversation_id"],
        phase=state.phase,
        turn=state.turn,
    )


@app.get("/")
async def root() -> dict[str, Any]:
    base = get_knowledge_base()
    return {
        "name": "Reg-Advisor",
        "description": (
            "Works out which EU and US health-product regulatory regime a product falls into. "
            "Not legal advice, and not a compliance determination."
        ),
        "knowledge_base_verified_on": base.verified_on,
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "conversations": "GET /conversations",
            "delete_conversation": "DELETE /conversations/{conversation_id}",
        },
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "healthy", "startup_validated": _startup_validated}


@app.get("/conversations")
async def list_conversations() -> dict[str, Any]:
    conversations = default_store.list_conversations()
    return {"count": len(conversations), "conversations": conversations}


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, Any]:
    if not default_store.delete(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": conversation_id}


@endpoint(
    name="reg_advisor_chat",
    description="Chat with the Reg-Advisor Google ADK multi-agent system.",
    request_mapping={
        "message": "{{ input }}",
        "conversation_id": "{{ session_id | default(none) }}",
    },
    response_mapping={
        "output": "{{ response }}",
        "session_id": "{{ conversation_id }}",
        # phase is an enum, so it is stringified before tojson sees it.
        "metadata": "{{ {'phase': phase | string, 'turn': turn} | tojson }}",
    },
)
async def chat_endpoint_traced(
    message: str,
    conversation_id: str | None = None,
) -> ChatResponse:
    """Traced entry point for one Reg-Advisor turn.

    Async so the ``/chat`` route can await it directly from the running event
    loop while still going through ``@endpoint``, which opens the Rhesis endpoint
    span the ADK spans then nest under and applies the mappings used for
    conversation grouping.
    """
    result = await run_chat_turn_async(message, conversation_id=conversation_id)
    return _chat_response_from_result(result)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not _startup_validated:
        raise HTTPException(status_code=503, detail="Service starting up")
    try:
        return await chat_endpoint_traced(
            message=request.message,
            conversation_id=request.conversation_id,
        )
    except RuntimeError as exc:
        # A missing credential is the user's problem to fix, so it travels with its real
        # message. Everything else is ours, and stays generic.
        if "API key" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        logger.error("Chat turn failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing request") from exc
    except Exception as exc:
        logger.error("Chat turn failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing request") from exc


__all__ = ["ChatRequest", "ChatResponse", "app", "chat_endpoint_traced"]
