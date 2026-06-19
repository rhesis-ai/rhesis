"""Haystack framework integration."""

import logging
from typing import Any, Callable, Optional

from opentelemetry import trace

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.tracing_helpers import (
    add_agent_io_events,
    observe_framework_call,
)

logger = logging.getLogger(__name__)

_original_pipeline_run: Optional[Callable] = None
_original_pipeline_run_async: Optional[Callable] = None
_patching_done = False


class HaystackPatchState:
    """Accessor for Haystack patching state (used in tests)."""

    @staticmethod
    def is_done() -> bool:
        return _patching_done

    @staticmethod
    def reset() -> None:
        global _original_pipeline_run, _original_pipeline_run_async, _patching_done
        if _patching_done and _original_pipeline_run is not None:
            try:
                from haystack import Pipeline

                Pipeline.run = _original_pipeline_run
                if _original_pipeline_run_async is not None:
                    Pipeline.run_async = _original_pipeline_run_async
            except ImportError:
                pass
        _original_pipeline_run = None
        _original_pipeline_run_async = None
        _patching_done = False


def _wrap_pipeline_run(original: Callable) -> Callable:
    def wrapped(self, data=None, *args, **kwargs):
        pipeline_name = getattr(self, "metadata", {}).get("name") or type(self).__name__
        with observe_framework_call(
            f"haystack.pipeline.run {pipeline_name}",
            framework="haystack",
            operation_type=AIAttributes.OPERATION_TRANSFORM,
        ) as span:
            add_agent_io_events(span, data, None)
            result = original(self, data, *args, **kwargs)
            add_agent_io_events(span, data, result)
            return result

    return wrapped


def _wrap_pipeline_run_async(original: Callable) -> Callable:
    async def wrapped(self, data=None, *args, **kwargs):
        pipeline_name = getattr(self, "metadata", {}).get("name") or type(self).__name__
        with observe_framework_call(
            f"haystack.pipeline.run_async {pipeline_name}",
            framework="haystack",
            operation_type=AIAttributes.OPERATION_TRANSFORM,
        ) as span:
            add_agent_io_events(span, data, None)
            result = await original(self, data, *args, **kwargs)
            add_agent_io_events(span, data, result)
            return result

    return wrapped


def _patch_pipeline_run() -> None:
    global _original_pipeline_run, _original_pipeline_run_async, _patching_done
    if _patching_done:
        return

    from haystack import Pipeline

    _original_pipeline_run = Pipeline.run
    Pipeline.run = _wrap_pipeline_run(_original_pipeline_run)

    if hasattr(Pipeline, "run_async"):
        _original_pipeline_run_async = Pipeline.run_async
        Pipeline.run_async = _wrap_pipeline_run_async(_original_pipeline_run_async)

    _patching_done = True


def _enable_haystack_tracing() -> Any:
    from haystack import tracing
    from haystack.tracing import OpenTelemetryTracer

    haystack_tracer = OpenTelemetryTracer(trace.get_tracer("rhesis.sdk.haystack"))
    tracing.enable_tracing(haystack_tracer)
    return haystack_tracer


class HaystackIntegration(BaseIntegration):
    """Haystack framework integration."""

    @property
    def framework_name(self) -> str:
        return "haystack"

    def is_installed(self) -> bool:
        try:
            import haystack  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self):
        """Enable Haystack tracing and patch Pipeline.run as a fallback."""
        callback: Any = None
        try:
            callback = _enable_haystack_tracing()
        except Exception as exc:
            logger.debug(f"Haystack tracing API unavailable, using pipeline patch: {exc}")
        _patch_pipeline_run()
        return callback or "haystack_patched"

    def enable(self) -> bool:
        if self._enabled:
            return True
        if not self.is_installed():
            return False
        try:
            self._callback = self._create_callback()
            self._enabled = True
            logger.info("✓ Observing haystack")
            return True
        except Exception as exc:
            logger.warning(f"Failed to enable haystack: {exc}")
            return False

    def disable(self) -> None:
        if self._enabled:
            HaystackPatchState.reset()
        super().disable()


_haystack_integration = HaystackIntegration()


def get_integration() -> HaystackIntegration:
    """Get the singleton Haystack integration instance."""
    return _haystack_integration
