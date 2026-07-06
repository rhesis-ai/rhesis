"""Pydantic AI integration for Rhesis observability.

Pydantic AI ships built-in OpenTelemetry instrumentation following the GenAI
semantic conventions (``gen_ai.*``). Unlike the previous integration (which
monkey-patched ``Agent.run``), all this integration needs to do is:

1. Turn on Pydantic AI's native instrumentation via
   ``Agent.instrument_all(InstrumentationSettings(...))``, pinned to a known
   instrumentation version and with binary content excluded from spans.
2. Wrap the existing Rhesis OTLP exporter with a translator so Pydantic AI's
   GenAI-shaped spans are rewritten into the Rhesis ``ai.*`` schema before
   reaching the backend.

This covers every Pydantic AI entry point (``run``, ``run_sync``,
``run_stream``) and yields per-model-call ``ai.llm.invoke`` spans, per-tool
``ai.tool.invoke`` spans, and synthesized ``ai.agent.handoff`` spans for
multi-agent delegation — none of which the ``Agent.run`` patch could see.

We deliberately do **not** pass a ``tracer_provider`` to
``InstrumentationSettings`` — it defaults to the global ``TracerProvider``
Rhesis already configured, and ``enable()`` verifies that provider is in
place first.

Usage::

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)
    auto_instrument("pydantic_ai")

    # Now all Pydantic AI agents/models/tools produce Rhesis spans.
"""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)

from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.genai import (
    DISABLE_CONTENT_CAPTURE_ENV,
    content_capture_enabled,
    get_processor_exporter,
    set_processor_exporter,
)
from rhesis.sdk.telemetry.integrations.pydantic_ai.translator import (
    PydanticAILLMDedupSpanProcessor,
    PydanticAITranslatingExporter,
)

logger = logging.getLogger(__name__)

# The Pydantic AI instrumentation version this integration's translator is
# written against (span names, gen_ai.* attribute shapes, message-attribute
# JSON layout — all verified empirically at this version). Pinned explicitly
# because InstrumentationSettings defaults to "latest", which would let the
# gen_ai.* schema shift under the translator on a Pydantic AI upgrade.
PINNED_INSTRUMENTATION_VERSION = 5

# Span-processor types whose underlying exporter we know how to swap out for
# translation. ``BatchSpanProcessor`` is what Rhesis installs by default;
# ``SimpleSpanProcessor`` is common in local/dev setups.
_WRAPPABLE_PROCESSORS: tuple[type[SpanProcessor], ...] = (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)


class PydanticAIIntegration(BaseIntegration):
    """Pydantic AI framework integration.

    Reuses the same lifecycle methods as the LangChain/LangGraph/MAF
    integrations so it works with
    :func:`~rhesis.sdk.telemetry.observer.auto_instrument`.

    There is no callback handler in the LangChain sense — Pydantic AI emits
    spans directly via OpenTelemetry. The "callback" returned by
    ``_create_callback`` is the dedup span processor that records span
    ancestry and toggles the LLM-observation flag.
    """

    def __init__(self) -> None:
        super().__init__()
        self._dedup_processor: Optional[PydanticAILLMDedupSpanProcessor] = None
        # Original (processor, exporter) pairs we patched, so disable() can revert.
        self._patched_processors: list[tuple[SpanProcessor, SpanExporter]] = []
        # Track whether the dedup processor has already been registered on the
        # TracerProvider. OTEL's TracerProvider exposes no removal API, so we
        # only ever ``add_span_processor`` once and rely on ``activate()`` /
        # ``deactivate()`` thereafter.
        self._dedup_registered = False

    @property
    def framework_name(self) -> str:
        return "pydantic_ai"

    def is_installed(self) -> bool:
        """Return True when a usable Pydantic AI install is present.

        Besides the top-level package we probe ``InstrumentationSettings``,
        which this integration depends on to enable native instrumentation
        (it appeared well before the 1.0 release, so this only filters out
        genuinely ancient installs).
        """
        try:
            import pydantic_ai  # noqa: F401
            from pydantic_ai.models.instrumented import (  # noqa: F401
                InstrumentationSettings,
            )

            return True
        except ImportError:
            return False

    def _create_callback(self):  # type: ignore[override]
        """Return (and lazily build) the dedup span processor.

        The processor is created exactly once per integration instance because
        OTEL ``TracerProvider`` exposes no removal API; the same instance is
        toggled on/off by ``enable()`` / ``disable()`` instead.
        """
        if self._dedup_processor is None:
            self._dedup_processor = PydanticAILLMDedupSpanProcessor()
        return self._dedup_processor

    def enable(self) -> bool:
        """Enable observation for Pydantic AI.

        Steps:

        1. Verify Pydantic AI is installed.
        2. Call ``Agent.instrument_all(InstrumentationSettings(...))`` with the
           pinned instrumentation version, ``include_binary_content=False``
           (attachment bytes must never reach spans — the same leak surface
           closed in the previous integration), and content capture honoring
           the ``RHESIS_DISABLE_CONTENT_CAPTURE`` env var.
        3. Wrap each existing exporter on the global ``TracerProvider`` with
           :class:`PydanticAITranslatingExporter` so spans are rewritten to
           the Rhesis ``ai.*`` schema before export.
        4. Register :class:`PydanticAILLMDedupSpanProcessor` for span-ancestry
           recording (handoff edges) and LLM-observation flag toggling.

        Returns:
            ``True`` if successfully enabled, ``False`` if Pydantic AI is not
            installed or instrumentation could not be turned on.
        """
        if self._enabled:
            logger.debug("pydantic_ai observation already enabled")
            return True

        if not self.is_installed():
            logger.debug("pydantic_ai not installed")
            return False

        try:
            from pydantic_ai import Agent
            from pydantic_ai.models.instrumented import InstrumentationSettings
        except ImportError as exc:
            logger.warning("pydantic_ai is not importable: %s", exc)
            return False

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            logger.warning(
                "Active tracer provider is %s, not a Rhesis TracerProvider; "
                "Pydantic AI spans will still be emitted but will not be "
                "translated. Did you forget to create a RhesisClient? "
                "Returning False so auto_instrument() does not list "
                "pydantic_ai as enabled.",
                type(provider).__name__,
            )
            return False

        capture_content = content_capture_enabled()
        try:
            Agent.instrument_all(
                InstrumentationSettings(
                    version=PINNED_INSTRUMENTATION_VERSION,
                    # Attachment bytes must never end up in span attributes.
                    include_binary_content=False,
                    include_content=capture_content,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to enable Pydantic AI instrumentation: %s", exc)
            return False

        self._wrap_existing_exporters(provider)

        self._dedup_processor = self._create_callback()
        if not self._dedup_registered:
            provider.add_span_processor(self._dedup_processor)  # type: ignore[arg-type]
            self._dedup_registered = True
        self._dedup_processor.activate()

        self._callback = self._dedup_processor
        self._enabled = True
        logger.info(
            "✓ Observing pydantic_ai (native instrumentation v%s); content capture %s",
            PINNED_INSTRUMENTATION_VERSION,
            "enabled" if capture_content else f"disabled via {DISABLE_CONTENT_CAPTURE_ENV}",
        )
        return True

    def disable(self) -> None:
        """Disable the integration: turn off instrumentation and unwrap exporters.

        Unlike MAF, Pydantic AI exposes a public off switch
        (``Agent.instrument_all(False)``), so newly constructed agents stop
        emitting spans entirely. Agents created with an explicit
        ``instrument=`` argument keep their own setting.

        The dedup span processor stays attached to the ``TracerProvider``
        because OTEL exposes no removal API; we deactivate it instead so its
        lifecycle hooks become no-ops. A subsequent ``enable()`` simply
        re-activates the same processor — no leak across cycles.
        """
        if not self._enabled:
            return

        try:
            from pydantic_ai import Agent

            Agent.instrument_all(False)
        except Exception:  # noqa: BLE001
            logger.debug("Failed to turn off Pydantic AI instrumentation", exc_info=True)

        for processor, original_exporter in self._patched_processors:
            try:
                set_processor_exporter(processor, original_exporter)
            except Exception:  # noqa: BLE001
                logger.debug("Failed to revert exporter on processor %r", processor, exc_info=True)
        self._patched_processors.clear()

        if self._dedup_processor is not None:
            self._dedup_processor.deactivate()
        self._callback = None
        self._enabled = False
        logger.info("✗ Stopped observing pydantic_ai")

    def _wrap_existing_exporters(self, provider: TracerProvider) -> None:
        """Find every wrappable span processor on the provider and wrap its exporter.

        Walks the provider's ``_active_span_processor`` (a multi-processor
        composite) and replaces each :class:`BatchSpanProcessor` /
        :class:`SimpleSpanProcessor` underlying exporter with a
        :class:`PydanticAITranslatingExporter`. Already-translating exporters
        are skipped so :meth:`enable` is idempotent. Other processor types
        (custom, multi-processor composites, etc.) are left untouched.
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
            if not isinstance(child, _WRAPPABLE_PROCESSORS):
                continue
            current = get_processor_exporter(child)
            if current is None:
                continue
            if isinstance(current, PydanticAITranslatingExporter):
                already_wrapped_count += 1
                continue
            try:
                set_processor_exporter(child, PydanticAITranslatingExporter(current))
                self._patched_processors.append((child, current))
                wrapped_count += 1
                logger.debug(
                    "Wrapped exporter %s on processor %r with PydanticAITranslatingExporter",
                    type(current).__name__,
                    child,
                )
            except Exception:  # noqa: BLE001
                logger.warning("Failed to wrap exporter on processor %r", child, exc_info=True)

        if wrapped_count == 0 and already_wrapped_count == 0:
            # No batch / simple span processor with a wrappable exporter
            # (e.g. only a custom processor, or no processors at all).
            # Pydantic AI spans will pass through untranslated and raw GenAI
            # span names like ``chat gpt-4o`` will fail backend span-name
            # validation. Log loudly so the surprise is debuggable.
            logger.warning(
                "pydantic_ai: no batch/simple span processor with a "
                "wrappable exporter found on the active TracerProvider; "
                "Pydantic AI spans will be emitted but not translated into "
                "the Rhesis ai.* schema. Ensure RhesisClient is created "
                "before auto_instrument()."
            )


_pydantic_ai_integration = PydanticAIIntegration()


def get_integration() -> PydanticAIIntegration:
    """Return the singleton :class:`PydanticAIIntegration` instance."""
    return _pydantic_ai_integration
