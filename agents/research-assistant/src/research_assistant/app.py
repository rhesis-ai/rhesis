"""
Research Assistant FastAPI Application.

A multi-agent conversational system for scientific workflows.
"""

import logging
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from research_assistant.graph import (
    create_multi_agent_coscientist,
    invoke_multi_agent,
)
from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.telemetry import auto_instrument

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Rhesis Client for tracing and remote endpoint testing
rhesis_client = RhesisClient.from_environment()

# If no project_id, default to DisabledClient
if rhesis_client and not getattr(rhesis_client, "project_id", None):
    logger.info("No project_id found, defaulting to DisabledClient")
    from rhesis.sdk.clients import DisabledClient

    rhesis_client = DisabledClient()

# Enable auto-instrumentation for LangGraph (traces LLM calls and tool invocations)
auto_instrument("langgraph")

# Store for conversation histories (in production, use a database)
conversations: dict[str, list[BaseMessage]] = {}

# Global multi-agent system
agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the multi-agent system on startup."""
    global agent

    logger.info("Initializing Research Assistant multi-agent system...")
    agent = create_multi_agent_coscientist()
    logger.info("Multi-agent system initialized with specialist agents")

    yield

    # Cleanup
    agent = None


app = FastAPI(
    title="Research Assistant",
    description="""
    Research Assistant is an advanced AI-powered multi-agent reasoning system designed to unify
    and leverage scattered knowledge, tools, methods, and models for scientific workflows.

    ## Multi-Agent Architecture

    The system uses specialized agents coordinated by an orchestrator:

    - **Orchestrator**: Routes queries to appropriate specialists (handles simple queries directly)
    - **Safety Specialist**: Safety/toxicity analysis
    - **Target Specialist**: Target biology and validation
    - **Compound Specialist**: Chemical and pharmacological analysis
    - **Literature Specialist**: Scientific literature and patents
    - **Market Specialist**: Market and competitive intelligence
    - **Synthesis Agent**: Final reports and recommendations

    The orchestrator intelligently routes queries - simple questions may only involve one
    specialist, while complex analyses will coordinate multiple specialists.

    ## Example Questions

    - "What are the known safety risks associated with target X?"
    - "Summarize the competitive landscape for biostimulants in Brazil"
    - "Rank these 10 targets based on druggability and safety profile"
    - "Generate a target dossier for gene Y, focusing on cardiovascular indications"
    - "What are the knowledge gaps for this target and what experiments would address them?"
    """,
    version="0.2.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., description="The user's message or question")
    conversation_id: str | None = Field(
        None,
        description="Optional conversation ID for multi-turn conversations",
    )


class ToolCall(BaseModel):
    """Information about a tool call."""

    tool_name: str = Field(..., description="Name of the tool called")
    tool_layer: str = Field(..., description="Layer: retrieval, analysis, synthesis, or utility")
    tool_args: dict = Field(default_factory=dict, description="Arguments passed to the tool")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str = Field(..., description="The Research Assistant's response")
    conversation_id: str = Field(..., description="Conversation ID for follow-up messages")
    tools_called: list[ToolCall] = Field(
        default_factory=list,
        description="List of tools called during this interaction",
    )
    tool_chain: str = Field(
        default="",
        description="Visual representation of tool chain flow",
    )
    agents_involved: list[str] = Field(
        default_factory=list,
        description="List of agents that participated in handling this request",
    )
    agent_workflow: str = Field(
        default="",
        description="Visual representation of agent handoff flow",
    )


class ConversationInfo(BaseModel):
    """Information about a conversation."""

    conversation_id: str
    message_count: int


@app.get("/")
async def root():
    """Root endpoint with welcome message."""
    return {
        "message": "Welcome to Research Assistant",
        "description": (
            "An AI-powered multi-agent reasoning system for scientific workflows. "
            "Use /chat to start a conversation."
        ),
        "endpoints": {
            "chat": "/chat - Chat with Research Assistant multi-agent system",
            "conversations": "/conversations - List active conversations",
            "health": "/health - Health check endpoint",
            "docs": "/docs - API documentation",
        },
        "specialists": [
            "Orchestrator - Routes queries to specialists",
            "Safety Specialist - Safety/toxicity analysis",
            "Target Specialist - Target biology and validation",
            "Compound Specialist - Chemical analysis",
            "Literature Specialist - Scientific literature and patents",
            "Market Specialist - Market intelligence",
            "Synthesis Agent - Reports and recommendations",
        ],
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_initialized": agent is not None,
    }


@endpoint(
    name="research_assistant_chat",
    description="Chat with Research Assistant multi-agent system for scientific workflows",
    request_mapping={
        "message": "{{ input }}",
        "conversation_id": "{{ session_id | default(none) }}",
    },
    response_mapping={
        "output": "{{ response }}",
        "session_id": "{{ conversation_id }}",
        "tools_called": "{{ tools_called | map(attribute='model_dump') | list | tojson }}",
        "agents_involved": "{{ agents_involved | tojson }}",
        "agent_workflow": "{{ agent_workflow }}",
        "tool_chain": "{{ tool_chain }}",
        "metadata": (
            "{{ {'tools_called': tools_called | map(attribute='model_dump') | list, "
            "'tool_chain': tool_chain, 'agents_involved': agents_involved, "
            "'agent_workflow': agent_workflow} | tojson }}"
        ),
    },
)
def chat_endpoint_traced(
    message: str,
    conversation_id: str | None = None,
) -> ChatResponse:
    """
    Traced chat endpoint for Research Assistant.

    This function is decorated with @endpoint to enable:
    - Automatic tracing of all calls
    - Remote testing from the Rhesis platform

    Args:
        message: User's message or question
        conversation_id: Optional conversation ID for multi-turn conversations

    Returns:
        ChatResponse with response, conversation_id, tools_called, agents_involved, etc.
    """
    global agent

    logger.info("=" * 80)
    logger.info("RESEARCH ASSISTANT MULTI-AGENT CHAT")
    logger.info(f"Message: {message[:100]}...")
    logger.info(f"Conversation ID: {conversation_id}")
    logger.info("=" * 80)

    if agent is None:
        raise ValueError("Agent not initialized")

    # Get or create conversation ID
    conv_id = conversation_id or str(uuid.uuid4())

    # Get existing conversation history from storage
    stored_history = conversations.get(conv_id, [])

    # Invoke the multi-agent system
    result = invoke_multi_agent(
        agent=agent,
        user_message=message,
        conversation_history=stored_history,
        conversation_id=conv_id,
    )

    # Update conversation history in storage
    conversations[conv_id] = result["messages"]

    # Format tools called as Pydantic models
    tools_called = [
        ToolCall(
            tool_name=tc["tool_name"],
            tool_layer=tc.get("tool_layer", "utility"),
            tool_args=tc.get("tool_args", {}),
        )
        for tc in result.get("tools_called", [])
    ]

    logger.info("Response generated")
    logger.info(f"Agents involved: {result.get('agents_involved', [])}")
    logger.info(f"Agent workflow: {result.get('agent_workflow', '')}")
    logger.info(f"Tool chain: {result.get('tool_chain', '')}")
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
async def chat(request: ChatRequest):
    """
    Chat with the Research Assistant multi-agent system.

    The orchestrator intelligently routes queries to the appropriate specialist(s).
    Simple queries may only involve one specialist, while complex analyses
    will coordinate multiple specialists.

    Example questions:
    - "What are the known safety risks associated with target X?"
    - "Summarize the competitive landscape for biostimulants in Brazil"
    - "What are the most cost-effective synthesis routes for compound Z?"
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent system not initialized")

    try:
        # Call the traced endpoint function
        return chat_endpoint_traced(
            message=request.message,
            conversation_id=request.conversation_id,
        )

    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}",
        )


@app.get("/conversations", response_model=list[ConversationInfo])
async def list_conversations():
    """List all active conversations."""
    return [
        ConversationInfo(conversation_id=cid, message_count=len(messages))
        for cid, messages in conversations.items()
    ]


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get the history of a specific conversation."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = conversations[conversation_id]
    history = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            history.append({"role": "assistant", "content": msg.content})

    return {
        "conversation_id": conversation_id,
        "message_count": len(messages),
        "history": history,
    }


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    del conversations[conversation_id]
    return {"message": f"Conversation {conversation_id} deleted"}


# To run the server, use: python -m research_assistant
# Or: uvicorn research_assistant.app:app --host 0.0.0.0 --port 8888 --reload
