"""Travel Agent FastAPI application.

A multi-agent Microsoft Agent Framework travel planner used to exercise the
Rhesis SDK's ``auto_instrument("agent_framework")`` integration end-to-end.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager

from agent_framework import Message
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from opentelemetry import trace as otel_trace
from pydantic import BaseModel, Field
from rhesis.telemetry.constants import ConversationContext

from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.clients import DisabledClient
from rhesis.sdk.telemetry import auto_instrument
from travel_agent.workflow import build_travel_workflow, invoke_travel_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialise the Rhesis client so ``@endpoint`` and ``auto_instrument`` have a
# tracer provider to attach to. We gate construction on the credentials
# themselves: ``RhesisClient.__init__`` eagerly installs OTEL providers and
# tries to ship spans, so instantiating it without an API key / project id
# would attempt outbound exports against ``project_id="unknown"`` with
# ``Authorization: Bearer None``. Falling back to ``DisabledClient`` before
# construction is the only way to actually keep telemetry off.
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

# Per-conversation message history. Production deployments would persist this
# in a database; in-memory is fine for a trace-generation demo.
conversations: dict[str, list[Message]] = {}

_startup_validated: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate travel workflow construction once at startup."""
    global _startup_validated

    logger.info("Validating Travel Agent multi-agent workflow construction (MAF)...")
    build_travel_workflow()
    _startup_validated = True
    logger.info(
        "Travel Agent workflow construction validated: trip_coordinator + "
        "destination_finder + sightseeing_scout + logistics_planner"
    )

    yield

    _startup_validated = False


app = FastAPI(
    title="Travel Agent",
    description=(
        "A Microsoft Agent Framework multi-agent travel planner for "
        "exercising the Rhesis SDK's MAF integration end-to-end.\n\n"
        "## Multi-Agent Architecture\n\n"
        "- **Trip Coordinator**: routes the request and synthesises the final plan.\n"
        "- **Destination Finder**: uses `get_random_destination` for surprise trips.\n"
        "- **Sightseeing Scout**: uses `find_sightseeing` when the user did not "
        "already name sights.\n"
        "- **Logistics Planner**: uses `estimate_travel` to add relative travel times.\n\n"
        "## Example Questions\n\n"
        "- Plan me a day trip.\n"
        "- Plan a family-friendly day trip at a random destination with local food.\n"
        "- Plan a day trip to Barcelona visiting Sagrada Familia and Park Guell.\n"
    ),
    version="0.1.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    """Request payload for the travel-agent endpoint."""

    message: str = Field(..., description="The user's travel-planning request.")
    conversation_id: str | None = Field(
        None,
        description="Optional conversation id for trace/session grouping.",
    )


class ToolCall(BaseModel):
    """One tool invocation captured during a chat turn."""

    tool_name: str = Field(..., description="Name of the tool that was called.")
    agent: str = Field(..., description="Agent that called the tool.")
    tool_args: dict = Field(default_factory=dict, description="Arguments passed to the tool.")


class ChatResponse(BaseModel):
    """Response payload for the travel-agent endpoint."""

    response: str = Field(..., description="The travel agent's final answer.")
    conversation_id: str = Field(..., description="Conversation id for trace/session grouping.")
    tools_called: list[ToolCall] = Field(
        default_factory=list,
        description="Domain tools invoked during this turn (handoff tools are excluded).",
    )
    tool_chain: str = Field(default="", description="One-line summary of the tool flow.")
    agents_involved: list[str] = Field(
        default_factory=list,
        description="Ordered list of agents that participated in this turn.",
    )
    agent_workflow: str = Field(default="", description="One-line summary of the agent flow.")
    agent: str = Field(default="trip_coordinator", description="Name of the final agent.")


class ConversationInfo(BaseModel):
    """Brief information about a stored conversation."""

    conversation_id: str
    message_count: int


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
            "Trip Coordinator - Routes requests and synthesises the final plan",
            "Destination Finder - get_random_destination",
            "Sightseeing Scout - find_sightseeing",
            "Logistics Planner - estimate_travel",
        ],
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "startup_validated": _startup_validated,
    }


@endpoint(
    name="travel_agent_chat",
    description="Chat with the Travel Agent MAF multi-agent system.",
    request_mapping={
        "message": "{{ input }}",
        "conversation_id": "{{ session_id | default(none) }}",
    },
    response_mapping={
        "output": "{{ response }}",
        "session_id": "{{ conversation_id }}",
        "tool_calls": "{{ tools_called | tojson }}",
        "agents_involved": "{{ agents_involved | tojson }}",
        "agent_workflow": "{{ agent_workflow }}",
        "tool_chain": "{{ tool_chain }}",
        "metadata": (
            "{{ {'agent': agent, 'tools_called': tools_called, "
            "'tool_chain': tool_chain, 'agents_involved': agents_involved, "
            "'agent_workflow': agent_workflow} | tojson }}"
        ),
    },
)
def chat_endpoint_traced(
    message: str,
    conversation_id: str | None = None,
) -> ChatResponse:
    """Traced entry point for the MAF travel multi-agent workflow."""
    logger.info("=" * 80)
    logger.info("TRAVEL AGENT MULTI-AGENT CHAT")
    logger.info("Message: %s...", message[:100])
    logger.info("Conversation ID: %s", conversation_id)
    logger.info("=" * 80)

    conv_id = conversation_id or str(uuid.uuid4())

    # Stamp the conversation attributes on the active @endpoint span (the
    # turn root). On the first turn the playground sends no conversation_id,
    # so the SDK/backend cannot inject one before the span is created.
    conv_attr = ConversationContext.SpanAttributes
    max_io = ConversationContext.MAX_IO_LENGTH
    span = otel_trace.get_current_span()
    span.set_attribute(conv_attr.IS_TURN_ROOT, True)
    span.set_attribute(conv_attr.CONVERSATION_ID, conv_id)
    span.set_attribute(conv_attr.CONVERSATION_INPUT, message[:max_io])

    # Replay prior turns so the workflow actually remembers the conversation.
    history = conversations.get(conv_id, [])
    workflow = build_travel_workflow()
    result = invoke_travel_workflow(
        workflow,
        message,
        conversation_history=history,
        conversation_id=conv_id,
    )
    conversations[conv_id] = result["messages"]

    span.set_attribute(conv_attr.CONVERSATION_OUTPUT, (result["response"] or "")[:max_io])

    tools_called = [
        ToolCall(
            tool_name=tc["tool_name"],
            agent=tc.get("agent", "travel_agent"),
            tool_args=tc.get("tool_args", {}),
        )
        for tc in result.get("tools_called", [])
    ]

    logger.info("Travel response generated")
    logger.info("Agents involved: %s", result.get("agents_involved", []))
    logger.info("Tools called: %s", [tc.tool_name for tc in tools_called])
    logger.info("=" * 80)

    return ChatResponse(
        response=result["response"],
        conversation_id=conv_id,
        tools_called=tools_called,
        tool_chain=result.get("tool_chain", ""),
        agents_involved=result.get("agents_involved", []),
        agent_workflow=result.get("agent_workflow", ""),
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Chat with the Microsoft Agent Framework travel multi-agent system."""
    if not _startup_validated:
        raise HTTPException(status_code=503, detail="Travel Agent not initialised")

    try:
        return chat_endpoint_traced(
            message=request.message,
            conversation_id=request.conversation_id,
        )
    except Exception as exc:
        logger.error("Error in /chat: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing request")


@app.get("/conversations", response_model=list[ConversationInfo])
async def list_conversations():
    """List every active conversation."""
    return [
        ConversationInfo(conversation_id=cid, message_count=len(messages))
        for cid, messages in conversations.items()
    ]


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Return a conversation's flat message history."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = conversations[conversation_id]
    history = [
        {
            "role": message.role,
            "author_name": message.author_name,
            "content": message.text,
        }
        for message in messages
    ]
    return {
        "conversation_id": conversation_id,
        "message_count": len(messages),
        "history": history,
    }


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a stored conversation."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    del conversations[conversation_id]
    return {"message": f"Conversation {conversation_id} deleted"}


# To run the server, use: python -m travel_agent
# Or: uvicorn travel_agent.app:app --host 0.0.0.0 --port 8890 --reload
