"""Data extraction utilities for LangChain callback handler.

This module provides utilities for extracting information from LangChain
invocation data: agent names, model names, providers, inputs/outputs, etc.
"""

import logging
from typing import Any, Dict, List, Optional

# Re-exported for backwards compatibility; canonical home is attributes.py
from rhesis.telemetry.attributes import MAX_CONTENT_LENGTH

logger = logging.getLogger(__name__)

# Provider patterns for LangChain module paths
PROVIDER_PATTERNS = {
    "openai": ["openai", "langchain_openai"],
    "anthropic": ["anthropic", "langchain_anthropic"],
    "google": ["google", "langchain_google"],
    "cohere": ["cohere", "langchain_cohere"],
    "huggingface": ["huggingface", "langchain_huggingface"],
    "aws": ["aws", "bedrock", "langchain_aws"],
    "azure": ["azure"],
    "mistralai": ["mistral", "langchain_mistralai"],
}


# =============================================================================
# Agent Extraction
# =============================================================================


def extract_agent_name(
    serialized: Dict | None,
    tags: List[str] | None,
    metadata: Dict | None,
    kwargs: Dict | None = None,
) -> str:
    """Extract agent name from metadata, serialized data, or callback kwargs.

    Priority order:
    1. Explicit agent_name in metadata
    2. langgraph_node in metadata (LangGraph convention)
    3. name from serialized data
    4. Last element from serialized id path
    5. name from the callback kwargs (how LangGraph passes the graph name)
    6. "unknown" as fallback
    """
    # Priority 1: Explicit agent name in metadata
    if metadata:
        if agent_name := metadata.get("agent_name"):
            return agent_name
        # LangGraph uses langgraph_node for node names
        if agent_name := metadata.get("langgraph_node"):
            return agent_name

    # Priority 2: Name from serialized (may be None for LangGraph)
    if serialized:
        if name := serialized.get("name"):
            return name

        # Priority 3: Extract from id path
        if "id" in serialized and isinstance(serialized["id"], list):
            return serialized["id"][-1] if serialized["id"] else "unknown"

    # Priority 4: LangGraph passes the compiled graph's name here, not in
    # ``serialized`` (which is None for graph runs).
    if kwargs and (name := kwargs.get("name")):
        return name

    return "unknown"


def is_langgraph_run(metadata: Dict | None) -> bool:
    """True if this run originated inside a LangGraph graph.

    LangGraph stamps ``ls_integration`` on every run it dispatches - both the
    graph root and each node - which is what separates a graph node from an
    anonymous LCEL step.
    """
    return bool(metadata) and metadata.get("ls_integration") == "langgraph"


def is_langgraph_node(metadata: Dict | None) -> bool:
    """True if this run carries a LangGraph node identity.

    Note this is also true for runs *nested inside* a node (a routing function,
    an LCEL step), which inherit the node's metadata verbatim - use
    :func:`is_inner_sequence_step` to tell them apart.
    """
    return bool(metadata) and metadata.get("langgraph_node") is not None


def is_langgraph_root(metadata: Dict | None) -> bool:
    """True if this run is the graph itself rather than one of its nodes."""
    return is_langgraph_run(metadata) and not is_langgraph_node(metadata)


def extract_conversation_id(metadata: Dict | None) -> Optional[str]:
    """Resolve the conversation this run belongs to.

    An id bound by the caller wins. Failing that, fall back to LangGraph's own
    ``thread_id`` - the key it checkpoints multi-turn state under, so it is the
    identity the app already treats as the conversation.
    """
    from rhesis.telemetry.context import get_conversation_id

    if conversation_id := get_conversation_id():
        return str(conversation_id)

    if metadata and (thread_id := metadata.get("thread_id")):
        return str(thread_id)

    return None


def is_inner_sequence_step(tags: List[str] | None) -> bool:
    """True if this run is a step inside an LCEL sequence rather than a unit of work.

    LangChain tags sequence steps ``seq:step:N``. Inside a LangGraph node this
    marks the pieces the node is built from - notably the routing function of a
    conditional edge, which inherits the node's metadata exactly and would
    otherwise be traced as a second copy of the node.
    """
    return bool(tags) and any(t.startswith("seq:step:") for t in tags)


def is_agent(name: str, tags: List[str] | None, metadata: Dict | None) -> bool:
    """Whether this run should be *labelled* an agent.

    This is a naming hint only. It must not be used to decide whether a run is
    traced at all - see :func:`should_trace_chain`.
    """
    # Check for agent-related patterns in name
    agent_patterns = [
        "agent",
        "specialist",
        "orchestrator",
        "coordinator",
        "supervisor",
    ]
    name_lower = name.lower()
    if any(p in name_lower for p in agent_patterns):
        return True

    # Check tags for agent markers
    if tags:
        for tag in tags:
            if any(p in tag.lower() for p in agent_patterns):
                return True

    # Check metadata for agent indicators
    if metadata:
        if metadata.get("is_agent") or metadata.get("agent_name"):
            return True

    return False


def should_trace_chain(name: str, tags: List[str] | None, metadata: Dict | None) -> bool:
    """Whether a chain run deserves its own span.

    Every LangGraph run is traced: the nodes and the graph root are the units
    users reason about, and their names carry no reliable marker (a node called
    ``summarizer`` or ``model`` is as much a step as one called ``orchestrator``).

    Anonymous LCEL sub-chains are not traced - a three-step
    ``prompt | llm | parser`` fires three chain runs and none is meaningful on
    its own. Skipping them keeps traces readable; they are still tracked for
    parenting so nothing below them is orphaned.
    """
    if is_langgraph_run(metadata):
        # The graph root and each node body, but not the LCEL steps within a
        # node - those repeat the node's own metadata.
        return not is_inner_sequence_step(tags)

    # Explicit opt-in from the caller.
    if metadata and (metadata.get("is_agent") or metadata.get("agent_name")):
        return True

    # Frameworks outside LangGraph (AgentExecutor and friends) still only
    # announce themselves through naming.
    return is_agent(name, tags, metadata)


def tool_call_names(tool_calls: Any) -> List[str]:
    """Name each tool call, whether the provider returns dicts or objects.

    Assuming dicts raises ``AttributeError`` inside the callback, and LangChain
    swallows handler exceptions - so the visible symptom is a span that never
    ends rather than an error.
    """
    names = []
    for call in tool_calls or ():
        if isinstance(call, dict):
            names.append(str(call.get("name", "unknown")))
        else:
            names.append(str(getattr(call, "name", "unknown")))
    return names


def extract_agent_input(inputs: Dict[str, Any]) -> str:
    """Extract human-readable input from agent inputs.

    Handles LangGraph message formats and falls back to JSON serialization.
    """
    if not inputs:
        return ""

    # LangGraph typically passes messages in the inputs
    if "messages" in inputs:
        messages = inputs["messages"]
        if messages and len(messages) > 0:
            # Get the last human message (typically the user's input)
            for msg in reversed(messages):
                if isinstance(msg, dict):
                    msg_type = msg.get("type", "")
                else:
                    msg_type = getattr(msg, "type", None) or ""
                if msg_type == "human":
                    if isinstance(msg, dict):
                        content = msg.get("content")
                    else:
                        content = getattr(msg, "content", None)
                    if content:
                        return str(content)[:MAX_CONTENT_LENGTH]
            # Fallback to last message
            last_msg = messages[-1]
            if hasattr(last_msg, "content") and last_msg.content:
                return str(last_msg.content)[:MAX_CONTENT_LENGTH]
            if isinstance(last_msg, dict) and last_msg.get("content"):
                return str(last_msg.get("content"))[:MAX_CONTENT_LENGTH]

    # Fallback: try to serialize the whole input
    try:
        import json

        return json.dumps(inputs, default=str)[:MAX_CONTENT_LENGTH]
    except Exception:
        return str(inputs)[:MAX_CONTENT_LENGTH]


def extract_agent_output(outputs: Dict[str, Any]) -> str:
    """Extract human-readable output from agent outputs.

    Handles LangGraph message formats, tool calls, and falls back to JSON.
    """
    if not outputs:
        return ""

    # LangGraph typically returns messages in the outputs
    if "messages" in outputs:
        messages = outputs["messages"]
        if messages and len(messages) > 0:
            # Get the last AI message
            last_msg = messages[-1]
            content = ""

            # Extract content
            if hasattr(last_msg, "content") and last_msg.content:
                content = str(last_msg.content)
            elif isinstance(last_msg, dict) and last_msg.get("content"):
                content = str(last_msg.get("content"))

            # If content is empty, check for tool calls
            if not content:
                tool_calls = getattr(last_msg, "tool_calls", None)
                if tool_calls:
                    content = f"[Tool calls: {', '.join(tool_call_names(tool_calls))}]"

            if content:
                return content[:MAX_CONTENT_LENGTH]

    # Check for direct output key
    if "output" in outputs:
        return str(outputs["output"])[:MAX_CONTENT_LENGTH]

    # Fallback: try to serialize the whole output
    try:
        import json

        return json.dumps(outputs, default=str)[:MAX_CONTENT_LENGTH]
    except Exception:
        return str(outputs)[:MAX_CONTENT_LENGTH]


# =============================================================================
# Tool Extraction
# =============================================================================


def extract_tool_output(output: Any) -> str:
    """Extract string content from tool output."""
    if isinstance(output, str):
        return output
    if hasattr(output, "content"):
        content = output.content
        return str(content) if isinstance(content, (str, list)) else str(output)
    if isinstance(output, dict):
        return str(output.get("content", output))
    return str(output)


# =============================================================================
# Retriever Extraction
# =============================================================================

# Per-document preview budget, so one long document cannot crowd out the rest.
_DOCUMENT_PREVIEW_LENGTH = 200


def extract_retriever_backend(
    serialized: Dict | None,
    metadata: Dict | None = None,
    kwargs: Dict | None = None,
) -> str:
    """Name the retriever/vector store behind a retrieval call.

    ``serialized`` is None for retrievers; LangChain reports the name through
    metadata and the callback kwargs instead.
    """
    if metadata and (name := metadata.get("ls_retriever_name")):
        return str(name)

    if serialized:
        if name := serialized.get("name"):
            return str(name)
        if isinstance(serialized.get("id"), list) and serialized["id"]:
            return str(serialized["id"][-1])

    if kwargs and (name := kwargs.get("name")):
        return str(name)

    return "unknown"


def summarize_documents(documents: Any) -> str:
    """Summarize retrieved documents for the results event.

    Keeps a short preview per document rather than full text: retrieved
    context is often far larger than the content cap.
    """
    if not documents:
        return "[no documents]"

    previews = []
    for i, doc in enumerate(documents):
        content = getattr(doc, "page_content", None)
        if content is None and isinstance(doc, dict):
            content = doc.get("page_content")
        previews.append(f"[{i}] {str(content or doc)[:_DOCUMENT_PREVIEW_LENGTH]}")

    return "\n".join(previews)[:MAX_CONTENT_LENGTH]


# =============================================================================
# LLM/Model Extraction
# =============================================================================


def extract_model_name(serialized: Dict, kwargs: Dict) -> str:
    """Extract model name from LangChain invocation data."""
    if "model" in kwargs:
        return str(kwargs["model"])
    if "kwargs" in serialized and isinstance(serialized["kwargs"], dict):
        for key in ["model", "model_name"]:
            if key in serialized["kwargs"]:
                return str(serialized["kwargs"][key])
    return serialized.get("name", "unknown")


def extract_provider(serialized: Dict, kwargs: Dict) -> Optional[str]:
    """Extract provider from model/invocation info.

    Checks module path, class name, and model name to identify the provider.
    """
    from rhesis.sdk.telemetry.utils import (
        identify_provider_from_class_name,
        identify_provider_from_model_name,
    )

    # Check module path
    module_path = ""
    if "id" in serialized and isinstance(serialized["id"], list):
        module_path = ".".join(serialized["id"]).lower()
    elif "kwargs" in serialized and "_type" in serialized["kwargs"]:
        module_path = serialized["kwargs"]["_type"].lower()

    for provider, patterns in PROVIDER_PATTERNS.items():
        if any(p in module_path for p in patterns):
            return provider

    # Try class name
    if class_name := serialized.get("name", ""):
        if provider := identify_provider_from_class_name(class_name):
            return provider

    # Try model name
    if "model" in kwargs:
        if provider := identify_provider_from_model_name(str(kwargs["model"])):
            return provider

    return "unknown"
