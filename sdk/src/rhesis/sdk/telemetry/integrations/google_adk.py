"""Google Agent Development Kit (ADK) framework integration."""

import logging
from typing import Any, Callable, Optional

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.tracing_helpers import (
    add_agent_io_events,
    observe_framework_call,
    set_agent_attributes,
    set_token_attributes,
)

logger = logging.getLogger(__name__)

RHESIS_PLUGIN_NAME = "rhesis_telemetry"

_original_runner_init: Optional[Callable] = None
_original_runner_run: Optional[Callable] = None
_patching_done = False
_rhesis_plugin: Any = None


class GoogleADKPatchState:
    """Accessor for Google ADK patching state (used in tests)."""

    @staticmethod
    def is_done() -> bool:
        return _patching_done

    @staticmethod
    def reset() -> None:
        global _original_runner_init, _original_runner_run, _patching_done, _rhesis_plugin
        if _patching_done:
            try:
                from google.adk.runners import Runner

                if _original_runner_init is not None:
                    Runner.__init__ = _original_runner_init
                if _original_runner_run is not None and hasattr(Runner, "run"):
                    Runner.run = _original_runner_run
            except ImportError:
                pass
        _original_runner_init = None
        _original_runner_run = None
        _patching_done = False
        _rhesis_plugin = None


def _extract_usage_from_llm_response(llm_response: Any) -> Any:
    usage = getattr(llm_response, "usage_metadata", None)
    if usage is not None:
        return usage
    if isinstance(llm_response, dict):
        return llm_response.get("usage_metadata") or llm_response.get("usage")
    return None


def _create_rhesis_plugin() -> Any:
    from google.adk.plugins.base_plugin import BasePlugin
    from opentelemetry import context as otel_context
    from opentelemetry import trace

    class RhesisADKPlugin(BasePlugin):
        """Global ADK plugin that emits Rhesis telemetry spans."""

        def __init__(self) -> None:
            super().__init__(name=RHESIS_PLUGIN_NAME)
            self._tracer = trace.get_tracer("rhesis.sdk.integrations.google_adk")

        async def before_agent_callback(self, *, agent, callback_context):
            agent_name = getattr(agent, "name", type(agent).__name__)
            model = getattr(agent, "model", None)
            span = self._tracer.start_span(f"google_adk.agent {agent_name}")
            set_agent_attributes(span, agent_name=agent_name, model=model)
            token = otel_context.attach(trace.set_span_in_context(span))
            callback_context.state["_rhesis_span"] = span
            callback_context.state["_rhesis_span_token"] = token
            return None

        async def after_agent_callback(self, *, agent, callback_context):
            span = callback_context.state.pop("_rhesis_span", None)
            token = callback_context.state.pop("_rhesis_span_token", None)
            if span is not None:
                span.end()
            if token is not None:
                otel_context.detach(token)
            return None

        async def after_model_callback(self, *, callback_context, llm_response):
            span = callback_context.state.get("_rhesis_span")
            if span is not None:
                set_token_attributes(span, _extract_usage_from_llm_response(llm_response))
            return llm_response

    return RhesisADKPlugin()


def _wrap_runner_run(original: Callable) -> Callable:
    async def wrapped(self, *args, **kwargs):
        session_id = kwargs.get("session_id")
        if session_id is None and len(args) >= 2:
            session_id = args[1]
        new_message = kwargs.get("new_message")
        if new_message is None and len(args) >= 3:
            new_message = args[2]

        with observe_framework_call(
            f"google_adk.runner.run {getattr(self, 'app_name', 'adk')}",
            framework="google_adk",
            attributes={AIAttributes.SESSION_ID: session_id} if session_id else None,
        ) as span:
            add_agent_io_events(span, new_message, None)
            result = await original(self, *args, **kwargs)
            add_agent_io_events(span, new_message, result)
            return result

    return wrapped


def _patch_runner() -> Any:
    global _original_runner_init, _original_runner_run, _patching_done, _rhesis_plugin
    if _patching_done:
        return _rhesis_plugin

    from google.adk.runners import Runner

    plugin = _create_rhesis_plugin()
    _rhesis_plugin = plugin

    _original_runner_init = Runner.__init__

    def patched_init(self, *args, **kwargs):
        plugins = list(kwargs.pop("plugins", None) or [])
        if not any(getattr(item, "name", "") == RHESIS_PLUGIN_NAME for item in plugins):
            plugins.append(plugin)
        kwargs["plugins"] = plugins
        return _original_runner_init(self, *args, **kwargs)

    Runner.__init__ = patched_init

    if hasattr(Runner, "run"):
        _original_runner_run = Runner.run
        Runner.run = _wrap_runner_run(_original_runner_run)

    _patching_done = True
    return plugin


class GoogleADKIntegration(BaseIntegration):
    """Google ADK framework integration."""

    @property
    def framework_name(self) -> str:
        return "google_adk"

    def is_installed(self) -> bool:
        try:
            import google.adk  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self):
        return _patch_runner()

    def enable(self) -> bool:
        if self._enabled:
            return True
        if not self.is_installed():
            return False
        try:
            self._callback = self._create_callback()
            self._enabled = True
            logger.info("✓ Observing google_adk")
            return True
        except Exception as exc:
            logger.warning(f"Failed to enable google_adk: {exc}")
            return False

    def disable(self) -> None:
        if self._enabled:
            GoogleADKPatchState.reset()
        super().disable()


_google_adk_integration = GoogleADKIntegration()


def get_integration() -> GoogleADKIntegration:
    """Get the singleton Google ADK integration instance."""
    return _google_adk_integration
