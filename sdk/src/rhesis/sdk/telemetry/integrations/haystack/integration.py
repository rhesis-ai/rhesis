"""Haystack framework integration."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.genai import (
    DISABLE_CONTENT_CAPTURE_ENV,
    content_capture_enabled,
    get_processor_exporter,
    set_processor_exporter,
)
from rhesis.sdk.telemetry.integrations.haystack.translator import HaystackTranslatingExporter
from rhesis.sdk.telemetry.integrations.tracing_helpers import (
    add_agent_io_events,
    observe_framework_call,
    set_agent_attributes,
)
from rhesis.telemetry.schemas import AIOperationType

logger = logging.getLogger(__name__)

# Span-processor types whose underlying exporter we know how to swap out for
# translation. ``BatchSpanProcessor`` is what Rhesis installs by default;
# ``SimpleSpanProcessor`` is common in local/dev setups (and was previously
# missed by a copy that only probed ``BatchSpanProcessor``).
_WRAPPABLE_PROCESSORS: tuple[type[SpanProcessor], ...] = (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)

_SETUP_ORDER_HINT = (
    "Create RhesisClient before auto_instrument('haystack'): "
    "client = RhesisClient(api_key=..., project_id=...); auto_instrument('haystack')"
)

_original_pipeline_run: Optional[Callable] = None
_original_pipeline_run_async: Optional[Callable] = None
_patching_done = False


class HaystackPatchState:
    """Accessor for Haystack patching state (used in tests)."""

    @staticmethod
    def get_run() -> Callable | None:
        return _original_pipeline_run

    @staticmethod
    def set_run(func: Callable) -> None:
        global _original_pipeline_run
        _original_pipeline_run = func

    @staticmethod
    def get_run_async() -> Callable | None:
        return _original_pipeline_run_async

    @staticmethod
    def set_run_async(func: Callable) -> None:
        global _original_pipeline_run_async
        _original_pipeline_run_async = func

    @staticmethod
    def is_done() -> bool:
        return _patching_done

    @staticmethod
    def set_done(done: bool = True) -> None:
        global _patching_done
        _patching_done = done

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
            AIOperationType.AGENT_INVOKE,
            framework="haystack",
            operation_type=AIAttributes.OPERATION_AGENT_INVOKE,
            attributes={AIAttributes.AGENT_NAME: pipeline_name},
        ) as span:
            set_agent_attributes(span, agent_name=pipeline_name)
            add_agent_io_events(span, data, None)
            result = original(self, data, *args, **kwargs)
            add_agent_io_events(span, None, result)
            return result

    return wrapped


def _wrap_pipeline_run_async(original: Callable) -> Callable:
    async def wrapped(self, data=None, *args, **kwargs):
        pipeline_name = getattr(self, "metadata", {}).get("name") or type(self).__name__
        with observe_framework_call(
            AIOperationType.AGENT_INVOKE,
            framework="haystack",
            operation_type=AIAttributes.OPERATION_AGENT_INVOKE,
            attributes={AIAttributes.AGENT_NAME: pipeline_name},
        ) as span:
            set_agent_attributes(span, agent_name=pipeline_name)
            add_agent_io_events(span, data, None)
            result = await original(self, data, *args, **kwargs)
            add_agent_io_events(span, None, result)
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


def _enable_content_tracing() -> None:
    """Enable Haystack content tracing only when capture is not opted out.

    Mirrors MAF and Pydantic AI: prompt/completion/tool I/O capture is gated on
    :func:`content_capture_enabled`, which honors ``RHESIS_DISABLE_CONTENT_CAPTURE``.
    We never write to ``os.environ`` so the setting does not leak into other
    tracing in the process after ``disable()``.
    """
    if not content_capture_enabled():
        logger.info(
            "Haystack content tracing left disabled (capture opted out via %s)",
            DISABLE_CONTENT_CAPTURE_ENV,
        )
        return
    from haystack import tracing

    tracing.tracer.is_content_tracing_enabled = True


def _enable_haystack_tracing() -> Any:
    from haystack import tracing
    from haystack.tracing import OpenTelemetryTracer

    _enable_content_tracing()
    haystack_tracer = OpenTelemetryTracer(trace.get_tracer("rhesis.sdk.haystack"))
    tracing.enable_tracing(haystack_tracer)
    return haystack_tracer


def _disable_haystack_tracing() -> None:
    """Best-effort revert of :func:`_enable_haystack_tracing`.

    Called on the ``enable()`` early-return paths so a failed/false enable never
    leaves Haystack emitting untranslated spans. ``disable_tracing`` is only
    available in Haystack >= 2.x; older versions have no public teardown, so we
    limit the damage by disabling content tracing and swallowing the rest.
    """
    try:
        from haystack import tracing

        disable = getattr(tracing, "disable_tracing", None)
        if disable is not None:
            disable()
    except Exception:  # noqa: BLE001
        logger.debug("Could not disable Haystack tracing on revert", exc_info=True)
    # Always stop content tracing so a failed enable does not leak captures.
    try:
        from haystack import tracing

        tracer = getattr(tracing, "tracer", None)
        if tracer is not None:
            tracer.is_content_tracing_enabled = False
    except Exception:  # noqa: BLE001
        logger.debug("Could not disable Haystack content tracing on revert", exc_info=True)


class HaystackIntegration(BaseIntegration):
    """Haystack framework integration."""

    def __init__(self) -> None:
        super().__init__()
        self._patched_processors: list[tuple[SpanProcessor, SpanExporter]] = []

    @property
    def framework_name(self) -> str:
        return "haystack"

    def is_installed(self) -> bool:
        try:
            import haystack  # noqa: F401

            return True
        except ImportError:
            return False

    def _wrap_existing_exporters(self, provider: TracerProvider) -> bool:
        try:
            multi = getattr(provider, "_active_span_processor", None)
            children = getattr(multi, "_span_processors", ()) if multi is not None else ()
        except Exception:  # noqa: BLE001
            logger.warning(
                "haystack: could not introspect provider span processors; refusing to "
                "enable instrumentation whose spans could not be translated into the "
                "Rhesis ai.* schema. %s",
                _SETUP_ORDER_HINT,
                exc_info=True,
            )
            return False

        wrapped_count = 0
        already_wrapped_count = 0
        for child in children:
            if not isinstance(child, _WRAPPABLE_PROCESSORS):
                continue
            current = get_processor_exporter(child)
            if current is None:
                continue
            if isinstance(current, HaystackTranslatingExporter):
                already_wrapped_count += 1
                continue
            try:
                set_processor_exporter(child, HaystackTranslatingExporter(current))
                self._patched_processors.append((child, current))
                wrapped_count += 1
            except Exception:  # noqa: BLE001
                logger.warning("Failed to wrap exporter on processor %r", child, exc_info=True)

        if wrapped_count == 0 and already_wrapped_count == 0:
            logger.warning(
                "haystack: no batch/simple span processor with a wrappable exporter found "
                "on the active TracerProvider; refusing to enable instrumentation whose "
                "spans could not be translated into the Rhesis ai.* schema. %s",
                _SETUP_ORDER_HINT,
            )
            return False
        return True

    def _unwrap_exporters(self) -> None:
        for processor, original_exporter in self._patched_processors:
            try:
                set_processor_exporter(processor, original_exporter)
            except Exception:  # noqa: BLE001
                logger.debug("Failed to revert exporter on processor %r", processor, exc_info=True)
        self._patched_processors.clear()

    def _create_callback(self):
        """Enable Haystack native tracing (used by :meth:`enable`)."""
        return _enable_haystack_tracing()

    def enable(self) -> bool:
        if self._enabled:
            logger.debug("%s observation already enabled", self.framework_name)
            return True

        if not self.is_installed():
            logger.debug("%s not installed", self.framework_name)
            return False

        # Try the native Haystack tracing path first (it produces the richest,
        # ai.*-translated spans). To fail closed we verify a Rhesis TracerProvider
        # and a wrappable exporter *after* enabling (option b of the review): if
        # either check fails we revert Haystack tracing so we never leave the
        # process emitting untranslated spans or stale content capture.
        try:
            haystack_tracer = _enable_haystack_tracing()
        except Exception as exc:
            logger.debug("Haystack tracing API unavailable, using pipeline patch fallback: %s", exc)
            try:
                _patch_pipeline_run()
                self._callback = "haystack_patched"
                self._enabled = True
                logger.info("✓ Observing %s (pipeline patch fallback)", self.framework_name)
                return True
            except Exception as fallback_exc:
                logger.warning("Failed to enable %s: %s", self.framework_name, fallback_exc)
                return False

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            logger.warning(
                "Active tracer provider is %s, not a Rhesis TracerProvider; Haystack spans "
                "will not be translated into the Rhesis ai.* schema. %s",
                type(provider).__name__,
                _SETUP_ORDER_HINT,
            )
            _disable_haystack_tracing()
            return False

        if not self._wrap_existing_exporters(provider):
            _disable_haystack_tracing()
            return False

        self._callback = haystack_tracer
        self._enabled = True
        logger.info("✓ Observing %s", self.framework_name)
        return True

    def disable(self) -> None:
        if self._enabled:
            self._unwrap_exporters()
            HaystackPatchState.reset()
            if self._callback != "haystack_patched":
                _disable_haystack_tracing()
        super().disable()


_haystack_integration = HaystackIntegration()


def get_integration() -> HaystackIntegration:
    """Get the singleton Haystack integration instance."""
    return _haystack_integration
