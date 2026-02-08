"""LangGraph framework integration."""

import logging
from typing import Any, Callable, List, Optional

from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.langchain import (
    get_integration as get_langchain_integration,
)
from rhesis.sdk.telemetry.integrations.langchain.utils import ensure_callback_in_config

logger = logging.getLogger(__name__)

# Module-level state for graph patching (singleton pattern)
_original_graph_invoke: Callable | None = None
_original_graph_ainvoke: Callable | None = None
_original_graph_stream: Callable | None = None
_original_graph_astream: Callable | None = None
_graph_patching_done: bool = False


class GraphPatchState:
    """Accessor for graph patching state."""

    @staticmethod
    def get_invoke() -> Callable | None:
        return _original_graph_invoke

    @staticmethod
    def set_invoke(func: Callable) -> None:
        global _original_graph_invoke
        _original_graph_invoke = func

    @staticmethod
    def get_ainvoke() -> Callable | None:
        return _original_graph_ainvoke

    @staticmethod
    def set_ainvoke(func: Callable) -> None:
        global _original_graph_ainvoke
        _original_graph_ainvoke = func

    @staticmethod
    def get_stream() -> Callable | None:
        return _original_graph_stream

    @staticmethod
    def set_stream(func: Callable) -> None:
        global _original_graph_stream
        _original_graph_stream = func

    @staticmethod
    def get_astream() -> Callable | None:
        return _original_graph_astream

    @staticmethod
    def set_astream(func: Callable) -> None:
        global _original_graph_astream
        _original_graph_astream = func

    @staticmethod
    def is_done() -> bool:
        return _graph_patching_done

    @staticmethod
    def set_done(done: bool = True) -> None:
        global _graph_patching_done
        _graph_patching_done = done


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
        2. Patches CompiledGraph.invoke/ainvoke/stream/astream to inject callbacks
        3. Sets up global callback via tracing_v2_callback_var context variable
        4. Ensures all LangGraph operations are traced, including ToolNode executions

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

            # Patch CompiledGraph methods to automatically inject callbacks
            # This is the most reliable way to ensure all graph invocations are traced
            self._patch_graph_invocation()

            # Also set up global callback via context variable as a fallback
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
                    f"Could not set tracing_v2_callback_var: {e}. Graph patching is still active."
                )

            self._enabled = True
            logger.info(f"✓ Observing {self.framework_name} (LLM + tools + graphs)")
            return True
        except Exception as e:
            logger.warning(f"⚠️  Could not enable {self.framework_name} observation: {e}")
            logger.debug("   Full error:", exc_info=True)
            return False

    def _patch_graph_invocation(self) -> None:
        """
        Patch CompiledGraph.invoke/ainvoke/stream/astream to ensure callbacks are triggered.

        This provides reliable auto-instrumentation by injecting our callback
        into the config of every graph invocation, eliminating the need for
        clients to manually call get_callback() and pass it in the config.
        """
        if GraphPatchState.is_done() or GraphPatchState.get_invoke() is not None:
            GraphPatchState.set_done()
            return

        try:
            from langgraph.graph.state import CompiledStateGraph
        except ImportError:
            try:
                # Fallback for different langgraph versions
                from langgraph.graph import CompiledGraph as CompiledStateGraph
            except ImportError as e:
                logger.debug(f"Could not import CompiledGraph for patching: {e}")
                return

        callback = self._callback

        # Store original methods
        GraphPatchState.set_invoke(CompiledStateGraph.invoke)
        GraphPatchState.set_ainvoke(CompiledStateGraph.ainvoke)
        if hasattr(CompiledStateGraph, "stream"):
            GraphPatchState.set_stream(CompiledStateGraph.stream)
        if hasattr(CompiledStateGraph, "astream"):
            GraphPatchState.set_astream(CompiledStateGraph.astream)

        def patched_invoke(self_graph, input: Any, config: Optional[dict] = None, **kwargs):
            return GraphPatchState.get_invoke()(
                self_graph, input, ensure_callback_in_config(config, callback), **kwargs
            )

        async def patched_ainvoke(self_graph, input: Any, config: Optional[dict] = None, **kwargs):
            return await GraphPatchState.get_ainvoke()(
                self_graph, input, ensure_callback_in_config(config, callback), **kwargs
            )

        def patched_stream(self_graph, input: Any, config: Optional[dict] = None, **kwargs):
            return GraphPatchState.get_stream()(
                self_graph, input, ensure_callback_in_config(config, callback), **kwargs
            )

        async def patched_astream(self_graph, input: Any, config: Optional[dict] = None, **kwargs):
            async for chunk in GraphPatchState.get_astream()(
                self_graph, input, ensure_callback_in_config(config, callback), **kwargs
            ):
                yield chunk

        # Apply patches
        CompiledStateGraph.invoke = patched_invoke
        CompiledStateGraph.ainvoke = patched_ainvoke
        if GraphPatchState.get_stream() is not None:
            CompiledStateGraph.stream = patched_stream
        if GraphPatchState.get_astream() is not None:
            CompiledStateGraph.astream = patched_astream

        GraphPatchState.set_done()
        logger.debug("Patched CompiledGraph for automatic callback injection")


# Singleton instance
_langgraph_integration = LangGraphIntegration()


def get_integration() -> LangGraphIntegration:
    """Get the singleton LangGraph integration instance."""
    return _langgraph_integration
