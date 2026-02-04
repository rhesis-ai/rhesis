"""
LangChain framework integration package.

This package provides OpenTelemetry-based tracing for LangChain operations including:
- LLM invocations (with token counts and costs)
- Tool executions (input/output captured)
- Agent invocations (for multi-agent systems)

Usage:
    from rhesis.sdk.telemetry import auto_instrument
    auto_instrument("langchain")

For LangGraph, use get_callback() to pass the callback explicitly:
    from rhesis.sdk.telemetry.integrations.langchain import get_callback

    callback = get_callback()
    config = {"callbacks": [callback]} if callback else {}
    result = graph.invoke(state, config=config)
"""

from rhesis.sdk.telemetry.integrations.langchain.callback import create_langchain_callback
from rhesis.sdk.telemetry.integrations.langchain.integration import (
    LangChainIntegration,
    get_callback,
    get_integration,
)

__all__ = [
    "LangChainIntegration",
    "get_integration",
    "get_callback",
    "create_langchain_callback",
]
