"""Reg-Advisor FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from reg_advisor.knowledge import get_knowledge_base, validate_knowledge_base
from reg_advisor.session import default_store, get_default_agent, run_chat_turn_async
from reg_advisor.state import Phase

logger = logging.getLogger(__name__)

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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not _startup_validated:
        raise HTTPException(status_code=503, detail="Service starting up")
    try:
        result = await run_chat_turn_async(request.message, conversation_id=request.conversation_id)
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
    return _chat_response_from_result(result)


__all__ = ["ChatRequest", "ChatResponse", "app"]
