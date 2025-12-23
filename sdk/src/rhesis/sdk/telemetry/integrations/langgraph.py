"""LangGraph framework integration."""

import logging
from typing import List

from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.langchain import LangChainIntegration

logger = logging.getLogger(__name__)


class LangGraphIntegration(BaseIntegration):
    """
    LangGraph framework integration.

    LangGraph is built on LangChain's callback system, so we reuse the LangChain
    callback handler. This means all provider-agnostic token extraction and cost
    calculation features automatically work with LangGraph.

    Auto-instrumentation is transparent - just call auto_instrument("langgraph")
    and all LangGraph operations will be automatically traced. This uses the
    tracing_v2_callback_var context variable for global callback registration
    (same approach as LangSmith).
    """

    @property
    def framework_name(self) -> str:
        """Return the name of the framework."""
        return "langgraph"

    @property
    def instrumented_libraries(self) -> List[str]:
        """Return the list of instrumented libraries."""
        return ["langgraph", "langgraph_core"]

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

        Reuses LangChain callback since LangGraph uses the same callback system.
        This provides:
        - Provider-agnostic token extraction
        - Automatic cost calculation (USD + EUR)
        - Support for all LLM providers (OpenAI, Anthropic, Google, etc.)
        """
        lc_integration = LangChainIntegration()
        return lc_integration._create_callback()

    def enable(self) -> bool:
        """
        Enable observation for LangGraph.

        Uses tracing_v2_callback_var context variable to enable global callbacks
        for both LangChain and LangGraph (transparent auto-instrumentation).

        Returns:
            True if successfully enabled, False if not installed
        """
        if self._enabled:
            logger.debug(f"{self.framework_name} observation already enabled")
            return True

        if not self.is_installed():
            logger.debug(f"{self.framework_name} not installed")
            return False

        try:
            # Create callback via LangChain integration
            lc_integration = LangChainIntegration()
            if lc_integration.enable():
                self._callback = lc_integration.callback()
            else:
                logger.warning(
                    f"⚠️  Could not enable {self.framework_name}: LangChain integration failed"
                )
                return False

            # Set up global callback for LangGraph using context variable
            # This is how LangSmith achieves transparent tracing
            try:
                from langchain_core.callbacks.manager import tracing_v2_callback_var

                # Set our callback handler directly in the context variable
                # LangGraph will pick it up via _get_trace_callbacks()
                tracing_v2_callback_var.set(self._callback)

                self._enabled = True
                logger.info(f"✅ Auto-instrumented frameworks: {self.instrumented_libraries}")
                logger.debug(
                    f"   Set global callback via tracing_v2_callback_var: "
                    f"{type(self._callback).__name__}"
                )
                return True
            except (ImportError, AttributeError) as e:
                logger.warning(
                    f"⚠️  Could not set global LangGraph callback: {e}. "
                    f"You may need to pass callbacks explicitly via config."
                )
                self._enabled = True  # Still mark as enabled, but with fallback mode
                return True
        except Exception as e:
            logger.warning(f"⚠️  Could not enable {self.framework_name} observation: {e}")
            logger.debug("   Full error:", exc_info=True)
            return False


# Singleton instance
_langgraph_integration = LangGraphIntegration()


def get_integration() -> LangGraphIntegration:
    """Get the singleton LangGraph integration instance."""
    return _langgraph_integration
