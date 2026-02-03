"""LangChain integration class for framework-level instrumentation."""

import logging
from typing import Optional

from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.langchain.callback import create_langchain_callback
from rhesis.sdk.telemetry.integrations.langchain.utils import (
    ToolPatchState,
    ensure_callback_in_config,
)

logger = logging.getLogger(__name__)


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
        """Register callback globally using LangChain's callback manager."""
        try:
            from langchain_core.callbacks.manager import CallbackManager
            from langchain_core.globals import set_default_callback_manager

            set_default_callback_manager(CallbackManager(handlers=[self._callback]))
            logger.debug("Configured callback via set_default_callback_manager")
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not use set_default_callback_manager: {e}")
            self._register_fallback_callback()

    def _register_fallback_callback(self) -> None:
        """Fallback callback registration for older LangChain versions."""
        try:
            from langchain_core.callbacks import manager as cb_module
            from langchain_core.callbacks.manager import CallbackManager

            if hasattr(cb_module, "_default_callback_manager"):
                if cb_module._default_callback_manager is None:
                    cb_module._default_callback_manager = CallbackManager(handlers=[self._callback])
                else:
                    cb_module._default_callback_manager.add_handler(self._callback)
                logger.debug("Added callback via fallback method")
        except Exception as e:
            logger.debug(f"Fallback registration failed: {e}")

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
