"""Framework integrations for automatic observability."""

from rhesis.sdk.telemetry.integrations.autogen import get_integration as _get_autogen
from rhesis.sdk.telemetry.integrations.google_adk import get_integration as _get_google_adk
from rhesis.sdk.telemetry.integrations.langchain import get_integration as _get_langchain
from rhesis.sdk.telemetry.integrations.langgraph import get_integration as _get_langgraph

# Singleton instances for direct access
langchain = _get_langchain()
langgraph = _get_langgraph()
autogen = _get_autogen()
google_adk = _get_google_adk()

__all__ = [
    "langchain",
    "langgraph",
    "autogen",
    "google_adk",
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
        "google_adk": google_adk,
    }
