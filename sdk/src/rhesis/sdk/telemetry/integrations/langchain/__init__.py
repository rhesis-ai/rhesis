"""
LangChain framework integration package.

This package provides OpenTelemetry-based tracing for LangChain operations including:
- LLM invocations (with token counts and costs)
- Tool executions (input/output captured)
- Chain and graph node transitions

Usage:
    from rhesis.sdk.telemetry import auto_instrument
    auto_instrument("langchain")

Or for manual callback access:
    from rhesis.sdk.telemetry.integrations.langchain import get_integration
    callback = get_integration().callback()
"""

from rhesis.sdk.telemetry.integrations.langchain.callback import create_langchain_callback
from rhesis.sdk.telemetry.integrations.langchain.integration import (
    LangChainIntegration,
    get_integration,
)

__all__ = [
    "LangChainIntegration",
    "get_integration",
    "create_langchain_callback",
]
