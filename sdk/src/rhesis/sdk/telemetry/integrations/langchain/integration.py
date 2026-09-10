"""LangChain integration class for framework-level instrumentation."""

import logging
from typing import Any, Optional

from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.langchain.callback import create_langchain_callback
from rhesis.sdk.telemetry.integrations.langchain.utils import (
    ToolPatchState,
    ensure_callback_in_config,
    restore_class_method,
)

logger = logging.getLogger(__name__)


class _GlobalCallbackRef:
    """Process-global callback holder for ``register_configure_hook``.

    The hook only ever calls ``.get()`` on what it is given, so this stands in
    for a ContextVar deliberately: a ContextVar set via ``.set()`` is invisible
    to threads that did not inherit the enabling context (``ThreadPoolExecutor``,
    ``run_in_executor``, bare ``threading.Thread``), which silently drops every
    LLM and chain span raised there. Tracing is process-wide, so the holder is
    too - matching what the removed ``set_default_callback_manager`` did.
    """

    def __init__(self) -> None:
        self._callback: Any = None

    def get(self) -> Any:
        return self._callback

    def set(self, callback: Any) -> None:
        self._callback = callback


# Registered with LangChain exactly once; enable/disable swap the referent.
_rhesis_callback_ref = _GlobalCallbackRef()
_hook_registered = False


class LangChainIntegration(BaseIntegration):
    """LangChain framework integration for automatic tracing."""

    @property
    def framework_name(self) -> str:
        return "langchain"

    def is_installed(self) -> bool:
        """Check if LangChain is installed."""
        try:
            import langchain_core  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self):
        """Create LangChain callback handler."""
        return create_langchain_callback()

    def enable(self) -> bool:
        """Enable LangChain observation with global callback registration."""
        if self._enabled:
            return True

        if not self.is_installed():
            logger.debug(f"{self.framework_name} not installed")
            return False

        try:
            self._callback = self._create_callback()
            self._register_global_callback()
            self._patch_tool_invocation()
            self._enabled = True
            logger.info(f"✓ Observing {self.framework_name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to enable {self.framework_name}: {e}")
            logger.debug("Full error:", exc_info=True)
            return False

    def _register_global_callback(self) -> None:
        """Register callback globally via LangChain's configure-hook system.

        ``register_configure_hook`` injects our handler into every
        ``CallbackManager.configure()`` call, which runs on each runnable
        invocation. This replaced the removed ``set_default_callback_manager``.
        """
        global _hook_registered

        _rhesis_callback_ref.set(self._callback)

        # LangChain has no way to unregister a hook, so only ever add one.
        if _hook_registered:
            return

        try:
            from langchain_core.tracers.context import register_configure_hook

            register_configure_hook(_rhesis_callback_ref, inheritable=True)
            _hook_registered = True
            logger.debug("Registered callback via register_configure_hook")
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not register configure hook: {e}")

    def disable(self) -> None:
        """Disable LangChain observation and restore what was patched.

        The configure hook cannot be unregistered, so clear the callback it
        reads instead - otherwise spans keep being emitted after disable().
        """
        _rhesis_callback_ref.set(None)
        self._unpatch_tool_invocation()
        super().disable()

    def _unpatch_tool_invocation(self) -> None:
        """Put BaseTool's own invoke/ainvoke back.

        The patch lives on the class and closes over this integration's
        callback, so leaving it would keep tracing tools through a handler that
        has been disabled.
        """
        original_invoke = ToolPatchState.get_invoke()
        original_ainvoke = ToolPatchState.get_ainvoke()
        if original_invoke is None and original_ainvoke is None:
            ToolPatchState.reset()
            return

        try:
            from langchain_core.tools import BaseTool
        except ImportError:
            ToolPatchState.reset()
            return

        if original_invoke is not None:
            restore_class_method(BaseTool, "invoke", original_invoke)
        if original_ainvoke is not None:
            restore_class_method(BaseTool, "ainvoke", original_ainvoke)

        # Only after restoring: the patched methods resolve the original here.
        ToolPatchState.reset()
        logger.debug("Restored BaseTool invocation")

    def _patch_tool_invocation(self) -> None:
        """Patch BaseTool.invoke/ainvoke to ensure callbacks are triggered."""
        if ToolPatchState.is_done() or ToolPatchState.get_invoke() is not None:
            ToolPatchState.set_done()
            return

        try:
            from langchain_core.tools import BaseTool

            ToolPatchState.set_invoke(BaseTool.invoke)
            ToolPatchState.set_ainvoke(BaseTool.ainvoke)
            callback = self._callback

            def patched_invoke(self_tool, input: dict, config: Optional[dict] = None, **kwargs):
                return ToolPatchState.get_invoke()(
                    self_tool, input, ensure_callback_in_config(config, callback), **kwargs
                )

            async def patched_ainvoke(
                self_tool, input: dict, config: Optional[dict] = None, **kwargs
            ):
                return await ToolPatchState.get_ainvoke()(
                    self_tool, input, ensure_callback_in_config(config, callback), **kwargs
                )

            BaseTool.invoke = patched_invoke
            BaseTool.ainvoke = patched_ainvoke
            ToolPatchState.set_done()
            logger.debug("Patched BaseTool for tool tracing")
        except ImportError as e:
            logger.debug(f"Could not patch tool invocation: {e}")


# Singleton instance
_langchain_integration = LangChainIntegration()


def get_integration() -> LangChainIntegration:
    """Get the singleton LangChain integration instance."""
    return _langchain_integration


def get_callback():
    """
    Get the global callback handler for manual callback injection.

    NOTE: When using auto_instrument("langgraph"), you typically don't need
    to call this function - the SDK automatically patches CompiledGraph methods
    to inject callbacks transparently.

    This function is useful for:
    - Edge cases where auto-instrumentation doesn't apply
    - Custom integrations or wrappers around LangGraph
    - Testing or debugging callback behavior

    Example (only if needed):

        from rhesis.sdk.telemetry.integrations.langchain import get_callback

        callback = get_callback()
        if callback:
            result = graph.invoke(state, config={"callbacks": [callback]})
        else:
            result = graph.invoke(state)

    Returns:
        The callback handler if enabled, None otherwise.
    """
    integration = get_integration()
    if integration.enabled:
        return integration.callback()
    return None
