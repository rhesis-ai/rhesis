"""Framework integrations for automatic observability."""

from rhesis.sdk.telemetry.integrations.agent_framework import (
    get_integration as _get_agent_framework,
)
from rhesis.sdk.telemetry.integrations.autogen import get_integration as _get_autogen
from rhesis.sdk.telemetry.integrations.langchain import get_integration as _get_langchain
from rhesis.sdk.telemetry.integrations.langgraph import get_integration as _get_langgraph

# Singleton instances for direct access
langchain = _get_langchain()
langgraph = _get_langgraph()
autogen = _get_autogen()
agent_framework = _get_agent_framework()

__all__ = [
    "langchain",
    "langgraph",
    "autogen",
    "agent_framework",
    "get_all_integrations",
]


def get_all_integrations():
    """
    Get all available framework integrations.

    Returns:
        Dict mapping framework name to integration instance.

    The ``"maf"`` alias points to the same instance as ``"agent_framework"``
    so users can write either ``auto_instrument("maf")`` or
    ``auto_instrument("agent_framework")``.
    """
    return {
        "langchain": langchain,
        "langgraph": langgraph,
        "autogen": autogen,
        "agent_framework": agent_framework,
        "maf": agent_framework,
    }
