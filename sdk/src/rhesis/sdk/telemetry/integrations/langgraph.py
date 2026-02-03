"""LangGraph framework integration."""

import logging
from typing import List

from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.langchain import (
    get_integration as get_langchain_integration,
)

logger = logging.getLogger(__name__)


class LangGraphIntegration(BaseIntegration):
    """
    LangGraph framework integration.

    LangGraph is built on LangChain's callback system, so we reuse the LangChain
    callback handler. This means all provider-agnostic token extraction and cost
    calculation features automatically work with LangGraph.

    Auto-instrumentation is transparent - just call auto_instrument("langgraph")
    and all LangGraph operations will be automatically traced, including:
    - LLM invocations (with token counts and costs)
    - Tool executions (input/output captured)
    - Chain and graph node transitions

    IMPORTANT: This integration shares the callback with LangChain to avoid
    duplicate span creation. When both LangChain and LangGraph are instrumented,
    they use the same callback instance.
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
        - Tool execution tracing (on_tool_start, on_tool_end, on_tool_error)
        """
        # Use the singleton LangChain integration to share callback
        lc_integration = get_langchain_integration()
        return lc_integration._create_callback()

    def enable(self) -> bool:
        """
        Enable observation for LangGraph.

        This method:
        1. Gets or enables the LangChain integration (shares callback to avoid duplicates)
        2. Sets up global callback via tracing_v2_callback_var context variable
        3. Ensures all LangGraph operations are traced, including ToolNode executions

        IMPORTANT: Uses singleton LangChain integration to prevent duplicate callbacks.

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
            # Get the singleton LangChain integration (shared callback)
            lc_integration = get_langchain_integration()

            # Enable LangChain if not already enabled
            # This sets up the callback and patches tools ONCE
            if not lc_integration.enabled:
                if not lc_integration.enable():
                    logger.warning(
                        f"⚠️  Could not enable {self.framework_name}: LangChain integration failed"
                    )
                    return False

            # Use the same callback instance (prevents duplicate spans)
            self._callback = lc_integration.callback()

            # Set up global callback for LangGraph using context variable
            # This is how LangSmith achieves transparent tracing
            try:
                from langchain_core.callbacks.manager import tracing_v2_callback_var

                # Set our callback handler directly in the context variable
                # LangGraph will pick it up via _get_trace_callbacks()
                tracing_v2_callback_var.set(self._callback)

                logger.debug(
                    f"Set global callback via tracing_v2_callback_var: "
                    f"{type(self._callback).__name__}"
                )
            except (ImportError, AttributeError) as e:
                logger.debug(
                    f"Could not set tracing_v2_callback_var: {e}. "
                    f"Tool tracing via BaseTool patching is still active."
                )

            self._enabled = True
            logger.info(f"✓ Observing {self.framework_name} (LLM + tools)")
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
