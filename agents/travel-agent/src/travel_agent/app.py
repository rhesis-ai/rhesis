"""Travel Agent FastAPI application.

A multi-agent Microsoft Agent Framework travel planner used to exercise the Rhesis SDK's
``auto_instrument("agent_framework")`` integration end-to-end. This is the only module
that imports the Rhesis SDK; everything below it is plain MAF.
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
from rhesis.sdk.telemetry import auto_instrument
from travel_agent.client import build_chat_client
from travel_agent.endpoint_mapping import (
    ENDPOINT_DESCRIPTION,
    ENDPOINT_NAME,
    REQUEST_MAPPING,
    RESPONSE_MAPPING,
)
from travel_agent.router import COORDINATOR_NAME
from travel_agent.runner import TurnFailedError
from travel_agent.session import default_store, run_chat_turn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

# Gate on the credentials themselves: ``RhesisClient.__init__`` eagerly installs OTEL
# providers and tries to ship spans, so constructing it without an API key / project id
# would export against ``project_id="unknown"`` with ``Authorization: Bearer None``.
# Falling back to ``DisabledClient`` before construction is the only way to keep
# telemetry genuinely off.
if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
    rhesis_client = RhesisClient.from_environment()
else:
    logger.info(
        "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; using DisabledClient. "
        "Traces will NOT be shipped to the backend."
    )
    rhesis_client = DisabledClient()

# THE line under test: turn on the SDK's MAF integration.
auto_instrument("agent_framework")

_startup_validated: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate that a chat client can be built before serving traffic."""
    global _startup_validated

    logger.info("Initialising Travel Agent...")
    # Only the client is checked here. The workflow itself is built per turn, because its
    # shape depends on the trip brief - there is no single graph to validate up front.
    build_chat_client()
    # Dial out the connector now that uvicorn's loop is running. @endpoint registered at
    # import time, which uvicorn does before asyncio.run(), so the connection was deferred
    # and the Playground would never see this app. No-op under DisabledClient.
    rhesis_client.start_connector()

    _startup_validated = True
    logger.info("Travel Agent ready: trip_coordinator + 6 research specialists")

    yield

    _startup_validated = False


app = FastAPI(
    title="Travel Agent",
    description=(
        "A Microsoft Agent Framework multi-agent travel planner for exercising the "
        "Rhesis SDK's MAF integration end-to-end.\n\n"
        "## Multi-Agent Architecture\n\n"
        "- **Trip Coordinator**: talks to the user, keeps the trip brief, routes research.\n"
        "- **Destination Finder**: picks a surprise destination.\n"
        "- **Place Resolver**: geocodes the destination and flags ambiguous names (Nominatim).\n"
        "- **Sightseeing Scout**: finds real landmarks (Wikipedia GeoSearch).\n"
        "- **Dining Scout**: finds restaurants by cuisine and diet (OpenStreetMap).\n"
        "- **Conditions Scout**: checks the weather outlook (Open-Meteo).\n"
        "- **Transit Planner**: measures travel times between sights (OSRM).\n"
        "- **Lodging Advisor**: sanity-checks the nightly budget.\n\n"
        "Which specialists exist is decided per turn from the trip brief, so a greeting "
        "reaches none of them.\n\n"
        "## Example Questions\n\n"
        "- Hi\n"
        "- I'm planning a 3-day trip to Tokyo.\n"
        "- Surprise me with a destination.\n"
        "- Show me top sights in Portland for a weekend.\n"
    ),
    version="0.2.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    """Request payload for the travel-agent endpoint."""

    message: str = Field(..., description="The user's message.")
    conversation_id: str | None = Field(
        None, description="Optional conversation id for trace/session grouping."
    )


class ToolCall(BaseModel):
    """One tool invocation captured during a chat turn."""

    tool_name: str = Field(..., description="Name of the tool that was called.")
    agent: str = Field(..., description="Agent that called the tool.")
    tool_args: dict = Field(default_factory=dict, description="Arguments passed to the tool.")


class ChatResponse(BaseModel):
    """Response payload for the travel-agent endpoint."""

    response: str = Field(..., description="The travel agent's reply.")
    conversation_id: str = Field(..., description="Conversation id for trace/session grouping.")
    phase: str = Field(..., description="Planning phase after this turn.")
    tools_called: list[ToolCall] = Field(
        default_factory=list,
        description="Domain tools invoked during this turn (handoff tools are excluded).",
    )
    tool_chain: str = Field(default="", description="One-line summary of the tool flow.")
    agents_involved: list[str] = Field(
        default_factory=list, description="Ordered list of agents that participated."
    )
    agent_workflow: str = Field(default="", description="One-line summary of the agent flow.")
    handoffs: list[str] = Field(
        default_factory=list, description="Handoff targets in the order they were routed to."
    )
    degraded_services: list[str] = Field(
        default_factory=list, description="Services that could not be reached this session."
    )
    brief: dict = Field(default_factory=dict, description="Snapshot of the trip brief.")
    agent: str = Field(default=COORDINATOR_NAME, description="Name of the replying agent.")


class ConversationInfo(BaseModel):
    """Brief information about a stored conversation."""

    conversation_id: str
    message_count: int


def _chat_response_from_result(result: dict[str, Any]) -> ChatResponse:
    tools_called = [
        ToolCall(
            tool_name=tc["tool_name"],
            agent=tc.get("agent", "travel_agent"),
            tool_args=tc.get("tool_args", {}),
        )
        for tc in result.get("tools_called", [])
    ]
    brief = result["brief"]
    return ChatResponse(
        response=result["response"],
        conversation_id=result["conversation_id"],
        phase=result["phase"],
        tools_called=tools_called,
        tool_chain=result.get("tool_chain", ""),
        agents_involved=result.get("agents_involved", []),
        agent_workflow=result.get("agent_workflow", ""),
        handoffs=result.get("handoffs", []),
        degraded_services=result.get("degraded_services", []),
        brief=brief.model_dump(exclude={"plan_text", "pending_reply"}),
    )


@app.get("/")
async def root():
    """Root endpoint with a quick orientation."""
    return {
        "message": "Welcome to Travel Agent",
        "description": (
            "A Microsoft Agent Framework multi-agent travel-planning demo for exercising "
            "the Rhesis SDK's MAF integration. Use /chat to start a conversation."
        ),
        "endpoints": {
            "chat": "/chat - Chat with the travel-agent multi-agent system",
            "conversations": "/conversations - List active conversations",
            "health": "/health - Health check endpoint",
            "docs": "/docs - API documentation",
        },
        "agents": [
            "Trip Coordinator - talks to the user and keeps the trip brief",
            "Destination Finder - surprise destinations",
            "Place Resolver - Nominatim geocoding and disambiguation",
            "Sightseeing Scout - Wikipedia GeoSearch landmarks",
            "Dining Scout - OpenStreetMap restaurants",
            "Conditions Scout - Open-Meteo weather",
            "Transit Planner - OSRM travel times",
            "Lodging Advisor - nightly budget checks",
        ],
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "startup_validated": _startup_validated}


@endpoint(
    name=ENDPOINT_NAME,
    description=ENDPOINT_DESCRIPTION,
    request_mapping=REQUEST_MAPPING,
    response_mapping=RESPONSE_MAPPING,
)
async def chat_endpoint_traced(
    message: str,
    conversation_id: str | None = None,
) -> ChatResponse:
    """Traced entry point for the MAF travel multi-agent workflow.

    Async so the FastAPI ``/chat`` route can ``await`` it directly from the running event
    loop while still going through the ``@endpoint`` decorator, which creates the Rhesis
    endpoint span and applies the mappings used for conversation grouping.
    """
    logger.info("Travel Agent turn | conversation=%s | message=%.100s", conversation_id, message)

    result = await run_chat_turn(message, conversation_id=conversation_id)

    logger.info(
        "Replied | phase=%s | agents=%s | tools=%s | degraded=%s",
        result.get("phase"),
        result.get("agents_involved", []),
        [tc["tool_name"] for tc in result.get("tools_called", [])],
        result.get("degraded_services", []),
    )
    return _chat_response_from_result(result)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the Microsoft Agent Framework travel multi-agent system."""
    if not _startup_validated:
        raise HTTPException(status_code=503, detail="Travel Agent not initialised")

    try:
        return await chat_endpoint_traced(
            message=request.message,
            conversation_id=request.conversation_id,
        )
    except TurnFailedError as exc:
        logger.error("Turn produced no reply: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Travel Agent produced no reply") from exc
    except RuntimeError as exc:
        # A missing API key is the user's to fix; anything else is ours.
        if "API_KEY" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        logger.error("Error in /chat: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing request") from exc
    except Exception as exc:
        logger.error("Error in /chat: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing request") from exc


@app.get("/conversations", response_model=list[ConversationInfo])
async def list_conversations():
    """List every active conversation."""
    return [
        ConversationInfo(conversation_id=conversation_id, message_count=message_count)
        for conversation_id, message_count in default_store.list_conversations().items()
    ]


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Return a conversation's transcript and current trip brief."""
    messages = default_store.get_messages(conversation_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    brief = default_store.get_brief(conversation_id)
    return {
        "conversation_id": conversation_id,
        "message_count": len(messages),
        "brief": brief.model_dump(exclude={"pending_reply"}) if brief else {},
        "history": [
            {"role": message.role, "author_name": message.author_name, "content": message.text}
            for message in messages
        ],
    }


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a stored conversation."""
    if not default_store.delete(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": f"Conversation {conversation_id} deleted"}


# To run the server, use: python -m travel_agent
# Or: uvicorn travel_agent.app:app --host 0.0.0.0 --port 8890 --reload
