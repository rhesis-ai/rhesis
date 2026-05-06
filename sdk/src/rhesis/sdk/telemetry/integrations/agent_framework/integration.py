"""Microsoft Agent Framework integration for Rhesis observability.

Microsoft Agent Framework (MAF) is the unified successor to AutoGen and
Semantic Kernel. Unlike LangChain, MAF emits OpenTelemetry spans natively
following the GenAI semantic conventions (``gen_ai.*``). All this integration
needs to do is:

1. Turn on MAF's ``enable_instrumentation()`` switch (which installs the
   ``AgentTelemetryLayer`` / ``ChatTelemetryLayer`` / ``EmbeddingTelemetryLayer``
   wrappers that emit spans).
2. Wrap the existing Rhesis OTLP exporter with a translator so MAF's
   GenAI-shaped spans are rewritten into the Rhesis ``ai.*`` schema before
   reaching the backend.

We deliberately do **not** call ``configure_otel_providers()`` -- that would
replace the global ``TracerProvider`` Rhesis already configured.

Usage::

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)
    auto_instrument("agent_framework")

    # Now all MAF agents/tools/chat clients/workflows produce Rhesis spans.
"""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

from rhesis.sdk.telemetry.integrations.agent_framework.translator import (
    MAFLLMDedupSpanProcessor,
    MAFTranslatingExporter,
)
from rhesis.sdk.telemetry.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class MAFIntegration(BaseIntegration):
    """Microsoft Agent Framework framework integration.

    Reuses the same lifecycle methods as the LangChain/LangGraph integrations
    so it works with :func:`~rhesis.sdk.telemetry.observer.auto_instrument`.

    There is no callback handler in the LangChain sense -- MAF emits spans
    directly via OpenTelemetry. The "callback" returned by ``_create_callback``
    is the dedup span processor that toggles the LLM-observation flag.
    """

    def __init__(self) -> None:
        super().__init__()
        self._dedup_processor: Optional[MAFLLMDedupSpanProcessor] = None
        # Original (processor, exporter) pairs we patched, so disable() can revert.
        self._patched_processors: list[tuple[BatchSpanProcessor, SpanExporter]] = []
        # Track whether the dedup processor has already been registered on the
        # TracerProvider. OTEL's TracerProvider exposes no removal API, so we
        # only ever ``add_span_processor`` once and rely on ``activate()`` /
        # ``deactivate()`` thereafter.
        self._dedup_registered = False

    @property
    def framework_name(self) -> str:
        return "agent_framework"

    def is_installed(self) -> bool:
        """Return True only when a *usable* agent_framework install is present.

        We check both the top-level package import and the
        ``agent_framework.observability`` module that we depend on for
        ``enable_instrumentation``. The two-step probe protects against the
        ``agent-framework-azure-ai-search==0.0.0a1`` stub package, which
        ships an empty ``agent_framework/__init__.py`` and can clobber the
        real one when both are installed (a known trap with the
        ``agent-framework`` meta-package). End users should install via
        ``pip install rhesis-sdk[agent-framework]``, which depends on the
        individual subpackages (``agent-framework-core`` etc.) and avoids
        the conflict.
        """
        try:
            import agent_framework  # type: ignore  # noqa: F401
            from agent_framework.observability import (  # type: ignore  # noqa: F401
                enable_instrumentation,
            )

            return True
        except ImportError:
            return False

    def _create_callback(self):  # type: ignore[override]
        """Return (and lazily build) the dedup span processor.

        For MAF this isn't a "callback" in the LangChain sense. We return the
        processor object so consumers calling ``integration.callback()`` get
        a useful handle, but the heavy lifting happens in :meth:`enable`. The
        processor is created exactly once per integration instance because OTEL
        ``TracerProvider`` exposes no removal API; the same instance is
        toggled on/off by ``enable()`` / ``disable()`` instead.
        """
        if self._dedup_processor is None:
            self._dedup_processor = MAFLLMDedupSpanProcessor()
        return self._dedup_processor

    def enable(self) -> bool:
        """Enable observation for Microsoft Agent Framework.

        Steps:

        1. Verify MAF is installed.
        2. Call ``enable_instrumentation()`` to flip MAF's internal switch.
        3. Wrap each existing OTLP exporter on the global ``TracerProvider``
           with :class:`MAFTranslatingExporter` so MAF spans are rewritten to
           the Rhesis ``ai.*`` schema before export.
        4. Register :class:`MAFLLMDedupSpanProcessor` so any nested
           ``@observe.llm`` decorator de-dupes against MAF chat spans.

        Returns:
            ``True`` if successfully enabled, ``False`` if MAF is not
            installed or instrumentation could not be turned on.
        """
        if self._enabled:
            logger.debug("agent_framework observation already enabled")
            return True

        if not self.is_installed():
            logger.debug("agent_framework not installed")
            return False

        try:
            from agent_framework.observability import enable_instrumentation  # type: ignore
        except ImportError as exc:
            logger.warning("agent_framework.observability is not importable: %s", exc)
            return False

        try:
            enable_instrumentation()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to enable MAF instrumentation: %s", exc)
            return False

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            logger.warning(
                "Active tracer provider is %s, not a Rhesis TracerProvider; "
                "MAF spans will still be emitted but will not be translated. "
                "Did you forget to create a RhesisClient? Returning False so "
                "auto_instrument() does not list agent_framework as enabled.",
                type(provider).__name__,
            )
            return False

        self._wrap_existing_exporters(provider)

        self._dedup_processor = self._create_callback()
        if not self._dedup_registered:
            provider.add_span_processor(self._dedup_processor)  # type: ignore[arg-type]
            self._dedup_registered = True
        self._dedup_processor.activate()

        self._callback = self._dedup_processor
        self._enabled = True
        logger.info("✓ Observing agent_framework (Microsoft Agent Framework)")
        return True

    def disable(self) -> None:
        """Disable the integration: unwrap exporters and neutralize the dedup processor.

        Note: MAF itself does not expose a public "disable instrumentation"
        switch, so the underlying telemetry layers stay attached to any
        agents already constructed. New spans they emit will simply pass
        through untranslated.

        The dedup span processor stays attached to the ``TracerProvider``
        because OTEL exposes no removal API; we deactivate it instead so its
        lifecycle hooks become no-ops. A subsequent ``enable()`` simply
        re-activates the same processor — no leak across cycles.
        """
        if not self._enabled:
            return

        for processor, original_exporter in self._patched_processors:
            try:
                _set_batch_processor_exporter(processor, original_exporter)
            except Exception:  # noqa: BLE001
                logger.debug("Failed to revert exporter on processor %r", processor, exc_info=True)
        self._patched_processors.clear()

        if self._dedup_processor is not None:
            self._dedup_processor.deactivate()
        self._callback = None
        self._enabled = False
        logger.info("✗ Stopped observing agent_framework")

    def _wrap_existing_exporters(self, provider: TracerProvider) -> None:
        """Find every BatchSpanProcessor on the provider and wrap its exporter.

        Walks the provider's ``_active_span_processor`` (a multi-processor
        composite) and replaces each batch processor's underlying exporter
        with a :class:`MAFTranslatingExporter`. Already-translating exporters
        are skipped so :meth:`enable` is idempotent.

        OTEL Python's ``BatchSpanProcessor`` evolved: in older releases the
        exporter was a settable attribute (``span_exporter``); in newer ones
        it's a read-only property forwarding to ``_batch_processor._exporter``.
        :func:`_set_batch_processor_exporter` handles both layouts.
        """
        try:
            multi = getattr(provider, "_active_span_processor", None)
            children = getattr(multi, "_span_processors", ()) if multi is not None else ()
        except Exception:  # noqa: BLE001
            logger.debug("Could not introspect provider span processors", exc_info=True)
            return

        wrapped_count = 0
        already_wrapped_count = 0
        for child in children:
            if not isinstance(child, BatchSpanProcessor):
                continue
            current = getattr(child, "span_exporter", None)
            if current is None:
                continue
            if isinstance(current, MAFTranslatingExporter):
                already_wrapped_count += 1
                continue
            try:
                _set_batch_processor_exporter(child, MAFTranslatingExporter(current))
                self._patched_processors.append((child, current))
                wrapped_count += 1
                logger.debug(
                    "Wrapped exporter %s on processor %r with MAFTranslatingExporter",
                    type(current).__name__,
                    child,
                )
            except Exception:  # noqa: BLE001
                logger.warning("Failed to wrap exporter on processor %r", child, exc_info=True)

        if wrapped_count == 0 and already_wrapped_count == 0:
            # No BatchSpanProcessor present (e.g. user has only a SimpleSpanProcessor
            # for debugging, or no processors at all). MAF spans will pass through
            # untranslated. Log loudly so the surprise is debuggable.
            logger.warning(
                "agent_framework: no BatchSpanProcessor found on the active "
                "TracerProvider; MAF spans will be emitted but not translated "
                "into the Rhesis ai.* schema. Ensure RhesisClient is created "
                "before auto_instrument()."
            )


def _set_batch_processor_exporter(processor: BatchSpanProcessor, exporter: SpanExporter) -> None:
    """Set the underlying exporter on a ``BatchSpanProcessor`` across SDK versions.

    OTEL Python's BatchSpanProcessor used to expose ``span_exporter`` as a
    settable attribute; newer versions wrap it in a read-only property that
    delegates to ``self._batch_processor._exporter``. We try the inner
    attribute first (newer layout), then fall back to direct assignment.
    """
    inner = getattr(processor, "_batch_processor", None)
    if inner is not None and hasattr(inner, "_exporter"):
        inner._exporter = exporter  # noqa: SLF001
        return
    # Older OTEL SDK: span_exporter is a plain attribute we can set directly.
    setattr(processor, "span_exporter", exporter)


_maf_integration = MAFIntegration()


def get_integration() -> MAFIntegration:
    """Return the singleton :class:`MAFIntegration` instance."""
    return _maf_integration
