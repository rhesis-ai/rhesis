"""Builds the Visit-Prep FastAPI app for a given tracing integration.

Rhesis concerns — client construction, ``RhesisTracing``, ``@endpoint`` — live only in this module
and the two thin wrappers that call it (``app.py`` for the native integration, ``app_upstream.py``
for deepset's). Nothing else under ``visit_prep`` imports from ``rhesis.sdk``.

``HAYSTACK_CONTENT_TRACING_ENABLED`` is set by those wrappers before they import their integration,
because Haystack reads it once at import time.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Protocol

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.clients import DisabledClient
from visit_prep.session import default_store, run_chat_turn_async
from visit_prep.state import Phase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TracingFactory(Protocol):
    """The slice of ``RhesisTracing`` this app needs. Both integrations satisfy it."""

    def __call__(self, name: str, *, enabled: bool = ...) -> Any: ...


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


def create_app(tracing_cls: TracingFactory) -> FastAPI:
    """Build the Visit-Prep app, traced through ``tracing_cls``.

    :param tracing_cls: The ``RhesisTracing`` class of the integration to trace through.
    """
    load_dotenv()

    # Initialise the Rhesis client so ``@endpoint`` has a registered default client to attach
    # traces to. ``RhesisClient.__init__`` calls ``_register_default_client`` as a side effect —
    # the local variable is never passed anywhere; ``@endpoint`` resolves it via
    # ``get_default_client()`` at decorate time. Gate on both credentials: ``RhesisClient``
    # eagerly installs OTEL providers and would export against an unknown project scope without
    # ``RHESIS_PROJECT_ID``. ``DisabledClient`` keeps telemetry off when either is missing.
    #
    # This must precede ``tracing_cls(...)``: the native integration reuses the provider the
    # client installs, which is what makes Haystack spans nest under the ``@endpoint`` span and
    # flush with it.
    tracing_configured = bool(os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"))
    if tracing_configured:
        RhesisClient.from_environment()
    else:
        logger.info(
            "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; using DisabledClient. "
            "Traces will NOT be shipped to the backend."
        )
        DisabledClient()

    # The served path never opens a turn span: @endpoint already owns the conversation turn root.
    # This is here to enable Haystack tracing and to carry the conversation id onto its spans.
    tracing = tracing_cls("Visit-Prep", enabled=tracing_configured)

    state: dict[str, bool] = {"startup_validated": False}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logger.info("Initialising Visit-Prep Haystack pipeline...")
        from visit_prep.session import get_default_pipeline

        # Build the shared pipeline + generator once so per-turn requests reuse it.
        get_default_pipeline()
        state["startup_validated"] = True
        logger.info("Visit-Prep ready: coordinator + history + summary + critic specialists")
        yield
        state["startup_validated"] = False
        tracing.flush()

    app = FastAPI(
        title="Visit-Prep Agent",
        description=(
            "A Haystack multi-agent visit-preparation assistant. "
            "Collects structured symptom history and produces a timeline plus "
            "questions for your clinician. Does not diagnose or prescribe."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/")
    async def root():
        return {
            "message": "Welcome to Visit-Prep",
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
        return {"status": "healthy", "startup_validated": state["startup_validated"]}

    @endpoint(
        name="visit_prep_chat",
        description="Chat with the Visit-Prep Haystack agent.",
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
        # Resolve the conversation id up front (instead of letting run_chat_turn mint one) so we
        # can group this turn's Haystack spans under the same session. The SDK @endpoint sets
        # ai.session.id on its own span, but the Haystack tracer reads it from the invocation
        # context, which start_conversation populates.
        conv_id = conversation_id or str(uuid.uuid4())
        tracing.start_conversation(conv_id)
        logger.info("Visit-Prep chat turn (conversation=%s)", conv_id)
        result = await run_chat_turn_async(message, conversation_id=conv_id)
        return _chat_response_from_result(result)

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        if not state["startup_validated"]:
            raise HTTPException(status_code=503, detail="Visit-Prep not initialised")
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

    # Exposed so tests can drive the traced endpoint directly, without a running server. It is a
    # closure over ``tracing``, so there is no module-level name to reach for.
    app.state.chat_endpoint_traced = chat_endpoint_traced
    app.state.tracing = tracing

    @app.get("/conversations")
    async def list_conversations():
        return default_store.list_conversations()

    @app.delete("/conversations/{conversation_id}")
    async def delete_conversation(conversation_id: str):
        if not default_store.delete(conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"message": f"Conversation {conversation_id} deleted"}

    return app
