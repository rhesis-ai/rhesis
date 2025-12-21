"""LangGraph framework integration."""

from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.langchain import LangChainIntegration


class LangGraphIntegration(BaseIntegration):
    """
    LangGraph framework integration.

    LangGraph is built on LangChain's callback system,
    so we reuse the LangChain callback.
    """

    @property
    def framework_name(self) -> str:
        return "langgraph"

    def is_installed(self) -> bool:
        """Check if LangGraph is installed."""
        try:
            import langgraph  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self):
        """
        Create LangGraph callback handler.

        Reuses LangChain callback since LangGraph uses same system.
        """
        lc_integration = LangChainIntegration()
        return lc_integration._create_callback()


# Singleton instance
_langgraph_integration = LangGraphIntegration()


def get_integration() -> LangGraphIntegration:
    """Get the singleton LangGraph integration instance."""
    return _langgraph_integration
