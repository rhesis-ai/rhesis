"""Framework integrations for automatic observability."""

from rhesis.sdk.telemetry.integrations.autogen import get_integration as _get_autogen
from rhesis.sdk.telemetry.integrations.langchain import get_integration as _get_langchain
from rhesis.sdk.telemetry.integrations.langgraph import get_integration as _get_langgraph

# Singleton instances for direct access
langchain = _get_langchain()
langgraph = _get_langgraph()
autogen = _get_autogen()

__all__ = [
    "langchain",
    "langgraph",
    "autogen",
    "get_all_integrations",
]


def get_all_integrations():
    """
    Get all available framework integrations.

    Returns:
        Dict mapping framework name to integration instance
    """
    return {
        "langchain": langchain,
        "langgraph": langgraph,
        "autogen": autogen,
    }
