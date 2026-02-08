"""Data extraction utilities for LangChain callback handler.

This module provides utilities for extracting information from LangChain
invocation data: agent names, model names, providers, inputs/outputs, etc.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Content truncation limit
MAX_CONTENT_LENGTH = 8000

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
    serialized: Dict | None, tags: List[str] | None, metadata: Dict | None
) -> str:
    """Extract agent name from metadata or serialized data.

    Priority order:
    1. Explicit agent_name in metadata
    2. langgraph_node in metadata (LangGraph convention)
    3. name from serialized data
    4. Last element from serialized id path
    5. "unknown" as fallback
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

    return "unknown"


def is_agent(name: str, tags: List[str] | None, metadata: Dict | None) -> bool:
    """Determine if this represents an agent based on name, tags, or metadata."""
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
                    tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                    content = f"[Tool calls: {', '.join(tool_names)}]"

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
