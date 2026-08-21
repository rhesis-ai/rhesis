"""Framework integrations for automatic observability."""

from rhesis.sdk.telemetry.integrations.agent_framework import (
    get_integration as _get_agent_framework,
)
from rhesis.sdk.telemetry.integrations.autogen import get_integration as _get_autogen
from rhesis.sdk.telemetry.integrations.google_adk import (
    get_integration as _get_google_adk,
)
from rhesis.sdk.telemetry.integrations.langchain import get_integration as _get_langchain
from rhesis.sdk.telemetry.integrations.langgraph import get_integration as _get_langgraph
from rhesis.sdk.telemetry.integrations.pydantic_ai import get_integration as _get_pydantic_ai

# Singleton instances for direct access
langchain = _get_langchain()
langgraph = _get_langgraph()
autogen = _get_autogen()
agent_framework = _get_agent_framework()
pydantic_ai = _get_pydantic_ai()
google_adk = _get_google_adk()

__all__ = [
    "langchain",
    "langgraph",
    "autogen",
    "agent_framework",
    "pydantic_ai",
    "google_adk",
    "get_all_integrations",
]


def get_all_integrations():
    """
    Get all available framework integrations.

    Returns:
        Dict mapping framework name to integration instance.

    Aliases point at the *same instance* as their canonical name, which is what
    lets ``auto_instrument`` dedupe them by ``id()``: ``"maf"`` for
    ``"agent_framework"`` and ``"adk"`` for ``"google_adk"``.
    """
    return {
        "langchain": langchain,
        "langgraph": langgraph,
        "autogen": autogen,
        "agent_framework": agent_framework,
        "maf": agent_framework,
        "pydantic_ai": pydantic_ai,
        "google_adk": google_adk,
        "adk": google_adk,
    }
