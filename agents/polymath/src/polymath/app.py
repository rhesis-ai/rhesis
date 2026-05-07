"""Polymath FastAPI application.

A multi-agent conversational system built on Microsoft Agent Framework that
exists to exercise the Rhesis SDK's ``auto_instrument("agent_framework")``
end-to-end. Mirrors the public surface of ``agents/research-assistant`` so
both demo agents look familiar.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from agent_framework import Message
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from polymath.workflow import build_workflow, invoke_polymath
from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.telemetry import auto_instrument

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialise the Rhesis client so ``@endpoint`` and ``auto_instrument`` have a
# tracer provider to attach to. If no project_id is configured we fall back to
# the disabled client (mirrors the research-assistant behaviour).
rhesis_client = RhesisClient.from_environment()

if rhesis_client and not getattr(rhesis_client, "project_id", None):
    logger.info("No project_id found, defaulting to DisabledClient")
    from rhesis.sdk.clients import DisabledClient

    rhesis_client = DisabledClient()

# THE line under test: turn on the SDK's MAF integration.
auto_instrument("agent_framework")

# Per-conversation message history. Production deployments would persist this
# in a database; in-memory is fine for a trace-generation demo.
conversations: dict[str, list[Message]] = {}

# Set to ``True`` after :func:`build_workflow` succeeds at startup. Used by
# ``/health`` to surface configuration problems (missing ``GOOGLE_API_KEY``,
# missing dependencies, etc.) without keeping a live ``Workflow`` instance
# around -- we build a fresh one per request so concurrent ``/chat`` calls
# don't trip MAF's "Workflow is already running" guard.
_startup_validated: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate workflow construction once at startup.

    MAF's ``HandoffBuilder`` workflow is single-run: two overlapping
    ``workflow.run(...)`` calls on the same instance raise
    ``RuntimeError: Workflow is already running``. We therefore build a fresh
    workflow per request inside :func:`chat_endpoint_traced`. Construction is
    cheap (one chat client + three agents + one ``HandoffBuilder.build()``,
    no network), so this is just a config canary -- a missing
    ``GOOGLE_API_KEY`` or broken import surfaces here at boot rather than on
    the first ``/chat`` call.
    """
    global _startup_validated

    logger.info("Validating Polymath multi-agent workflow construction (MAF HandoffBuilder)...")
    build_workflow()
    _startup_validated = True
    logger.info(
        "Polymath workflow construction validated: coordinator + math_specialist + "
        "info_specialist (a fresh workflow is built per request)"
    )

    yield

    _startup_validated = False


app = FastAPI(
    title="Polymath",
    description=(
        "Polymath is a small Microsoft Agent Framework multi-agent demo for "
        "exercising the Rhesis SDK's MAF integration end-to-end.\n\n"
        "## Multi-Agent Architecture\n\n"
        "- **Coordinator**: routes the request to the right specialist and synthesises "
        "the final answer.\n"
        "- **Math Specialist**: performs arithmetic via local Python tools "
        "(`add`, `multiply`, `power`, `square_root`).\n"
        "- **Info Specialist**: fetches live data over HTTP "
        "(`get_current_time`, `wikipedia_summary`).\n\n"
        "## Example Questions\n\n"
        "- Compute (3 + 5) * 2^4 and then take the square root.\n"
        "- What time is it in Tokyo, and give me a one-sentence summary of Tokyo.\n"
        "- What is 17 squared, and what's the current UTC minute right now?\n"
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request payload for the ``/chat`` endpoint."""

    message: str = Field(..., description="The user's message or question.")
    conversation_id: str | None = Field(
        None,
        description="Optional conversation id for multi-turn conversations.",
    )


class ToolCall(BaseModel):
    """One tool invocation captured during a chat turn."""

    tool_name: str = Field(..., description="Name of the tool that was called.")
    agent: str = Field(..., description="Agent that called the tool.")
    tool_args: dict = Field(default_factory=dict, description="Arguments passed to the tool.")


class ChatResponse(BaseModel):
    """Response payload for the ``/chat`` endpoint."""

    response: str = Field(..., description="Polymath's final answer.")
    conversation_id: str = Field(..., description="Conversation id for follow-up messages.")
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


class ConversationInfo(BaseModel):
    """Brief information about a stored conversation."""

    conversation_id: str
    message_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    """Root endpoint with a quick orientation."""
    return {
        "message": "Welcome to Polymath",
        "description": (
            "A Microsoft Agent Framework multi-agent demo for exercising the "
            "Rhesis SDK's MAF integration. Use /chat to start a conversation."
        ),
        "endpoints": {
            "chat": "/chat - Chat with the polymath multi-agent system",
            "conversations": "/conversations - List active conversations",
            "health": "/health - Health check endpoint",
            "docs": "/docs - API documentation",
        },
        "agents": [
            "Coordinator - Routes requests and synthesises the answer",
            "Math Specialist - add / multiply / power / square_root",
            "Info Specialist - get_current_time / wikipedia_summary",
        ],
    }


@app.get("/health")
async def health():
    """Health check endpoint.

    ``startup_validated`` mirrors the result of the lifespan canary: if
    :func:`polymath.workflow.build_workflow` succeeded at boot, we know the
    Gemini API key, the agent definitions, and ``HandoffBuilder.build()``
    all work, and per-request construction will succeed too.
    """
    return {
        "status": "healthy",
        "startup_validated": _startup_validated,
    }


@endpoint(
    name="polymath_chat",
    description="Chat with the Polymath MAF multi-agent system (math + info specialists).",
    request_mapping={
        "message": "{{ input }}",
        "conversation_id": "{{ session_id | default(none) }}",
    },
    response_mapping={
        "output": "{{ response }}",
        "session_id": "{{ conversation_id }}",
        # ``tools_called`` is a ``list[ToolCall]`` Pydantic model on the wire,
        # but the SDK's ``TypeSerializer`` recursively ``model_dump()``-s the
        # ``ChatResponse`` to plain dicts before this template runs. So at
        # render time the value is already ``list[dict]`` and we can JSON
        # encode it directly. The previous ``map(attribute='model_dump')``
        # construct fell off a cliff because dicts don't carry that key, so
        # every entry rendered as ``Undefined`` -> ``null``.
        "tools_called": "{{ tools_called | tojson }}",
        "agents_involved": "{{ agents_involved | tojson }}",
        "agent_workflow": "{{ agent_workflow }}",
        "tool_chain": "{{ tool_chain }}",
        "metadata": (
            "{{ {'tools_called': tools_called, "
            "'tool_chain': tool_chain, 'agents_involved': agents_involved, "
            "'agent_workflow': agent_workflow} | tojson }}"
        ),
    },
)
def chat_endpoint_traced(
    message: str,
    conversation_id: str | None = None,
) -> ChatResponse:
    """Traced chat entry point invoked by the public ``/chat`` route.

    The ``@endpoint`` decorator wires this function into the Rhesis platform
    for remote testing and emits the corresponding ``ai.endpoint.invoke`` span.
    """
    logger.info("=" * 80)
    logger.info("POLYMATH CHAT")
    logger.info("Message: %s...", message[:100])
    logger.info("Conversation ID: %s", conversation_id)
    logger.info("=" * 80)

    conv_id = conversation_id or str(uuid.uuid4())
    history = conversations.get(conv_id, [])

    # Build a fresh workflow per request. MAF's ``HandoffBuilder`` workflow
    # is single-run -- sharing one instance across requests raises
    # ``RuntimeError: Workflow is already running`` whenever two ``/chat``
    # calls overlap (which happens routinely because the connector's
    # auto-validation handshake also invokes this endpoint at boot).
    workflow = build_workflow()

    result = invoke_polymath(
        workflow,
        message,
        conversation_history=history,
        conversation_id=conv_id,
    )

    conversations[conv_id] = result["messages"]

    tools_called = [
        ToolCall(
            tool_name=tc["tool_name"],
            agent=tc.get("agent", "unknown"),
            tool_args=tc.get("tool_args", {}),
        )
        for tc in result.get("tools_called", [])
    ]

    logger.info("Response generated")
    logger.info("Agents involved: %s", result.get("agents_involved", []))
    logger.info("Agent workflow: %s", result.get("agent_workflow", ""))
    logger.info("Tool chain: %s", result.get("tool_chain", ""))
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
    """Chat with Polymath.

    The coordinator routes the request to the math and/or info specialist(s),
    then synthesises a final answer.

    Defined as a sync function so FastAPI executes it in its threadpool. This
    matches the contract documented in :func:`polymath.workflow.invoke_polymath`,
    which uses :func:`asyncio.run` internally and therefore must run on a
    thread that does not already have a running event loop. Declaring this
    handler ``async`` would put us back on the FastAPI event loop and cause
    ``asyncio.run() cannot be called from a running event loop`` at request
    time.
    """
    if not _startup_validated:
        raise HTTPException(status_code=503, detail="Polymath workflow not initialised")

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


# To run the server, use: python -m polymath
# Or: uvicorn polymath.app:app --host 0.0.0.0 --port 8889 --reload
