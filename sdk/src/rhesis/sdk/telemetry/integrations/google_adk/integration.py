"""Google ADK integration for Rhesis observability.

Google ADK (the Agent Development Kit) emits OpenTelemetry spans natively,
following the GenAI semantic conventions in part and its own
``gcp.vertex.agent.*`` namespace for the rest. This integration therefore does
not instrument anything -- it translates.

That makes ``enable()`` unusual. MAF has ``enable_instrumentation()`` and
Pydantic AI has ``Agent.instrument_all()``; **ADK has no on/off switch at all**.
It emits spans unconditionally the moment a ``TracerProvider`` exists, and it
offers no way to stop. So ``enable()`` only ever:

1. wraps the existing Rhesis OTLP exporter with
   :class:`~rhesis.sdk.telemetry.integrations.google_adk.translator.GoogleADKTranslatingExporter`,
2. configures ADK's content-capture knobs to match Rhesis's, and
3. registers the span processor that indexes span structure and dedups LLM spans.

Because there is no switch, failing closed is more important here than for the
other integrations: if no exporter can be wrapped, ADK's raw span names
(``call_llm``, ``invoke_agent root_agent``) reach the backend and are rejected
with HTTP 422, so ``enable()`` returns ``False`` loudly rather than pretending.

We deliberately do **not** call
``google.adk.telemetry.setup.maybe_set_otel_providers()`` -- it installs its own
``TracerProvider`` / ``LoggerProvider`` / ``MeterProvider``, and Rhesis owns those.

Usage::

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)
    auto_instrument("google_adk")   # or "adk"

    # Now every ADK agent / model call / tool call produces Rhesis spans.
"""

from __future__ import annotations

import logging
import os
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
from rhesis.sdk.telemetry.integrations.google_adk.translator import (
    GoogleADKLLMDedupSpanProcessor,
    GoogleADKTranslatingExporter,
    verbose_spans_enabled,
)

logger = logging.getLogger(__name__)

# Span-processor types whose underlying exporter we know how to swap out.
# ``BatchSpanProcessor`` is what Rhesis installs by default;
# ``SimpleSpanProcessor`` is common in local/dev setups. Both expose their
# exporter via ``span_exporter`` or the private ``_batch_processor._exporter``
# slot, and :func:`set_processor_exporter` handles both layouts.
_WRAPPABLE_PROCESSORS: tuple[type[SpanProcessor], ...] = (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)

# ADK's content-capture knobs, and the values that switch content off.
#
# There are three overlapping ones, in ADK's own precedence order (see
# ``google.adk.telemetry.context.TelemetryConfig``): an admin lock, then a
# per-request ``RunConfig.telemetry``, then these env vars. Setting the lock is
# what makes a privacy opt-out actually hold -- without it, an app that passes
# ``RunConfig(telemetry=TelemetryConfig(capture_message_content=SPAN_ONLY))``
# outranks the env vars and puts prompts back on the spans.
_ADK_CAPTURE_IN_SPANS_ENV = "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"
_OTEL_CAPTURE_CONTENT_ENV = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
_ADK_IGNORE_RUN_CONFIG_ENV = "ADK_TELEMETRY_IGNORE_RUN_CONFIG"

_CONTENT_OFF_ENV: dict[str, str] = {
    _ADK_CAPTURE_IN_SPANS_ENV: "false",
    _OTEL_CAPTURE_CONTENT_ENV: "NO_CONTENT",
    _ADK_IGNORE_RUN_CONFIG_ENV: "1",
}

# ADK's telemetry schema-version knob. We only read it, to log which shape we
# are translating; both versions go through the same span-name table.
_ADK_SCHEMA_VERSION_ENV = "ADK_TELEMETRY_SCHEMA_VERSION_OPT_IN"
_AGENT_ENGINE_ID_ENV = "GOOGLE_CLOUD_AGENT_ENGINE_ID"


def _resolved_schema_version() -> int:
    """Mirror ADK's own ``resolve_schema_version()`` for logging purposes.

    Reimplemented rather than imported so this stays a pure read that works even
    if ADK moves the private module. Precedence: the opt-in env var, then 2 on
    Vertex Agent Engine, then 1.
    """
    opt_in = os.environ.get(_ADK_SCHEMA_VERSION_ENV, "").strip()
    if opt_in in ("1", "2"):
        return int(opt_in)
    return 2 if os.environ.get(_AGENT_ENGINE_ID_ENV) else 1


class GoogleADKIntegration(BaseIntegration):
    """Google ADK framework integration.

    Reuses the same lifecycle methods as the other framework integrations so it
    works with :func:`~rhesis.sdk.telemetry.observer.auto_instrument`.

    There is no callback handler in the LangChain sense -- ADK emits spans
    directly via OpenTelemetry. The "callback" returned by ``_create_callback``
    is the span processor that indexes ADK span structure, captures conversation
    content, and toggles the LLM-observation flag.
    """

    def __init__(self) -> None:
        super().__init__()
        self._dedup_processor: Optional[GoogleADKLLMDedupSpanProcessor] = None
        # Original (processor, exporter) pairs we patched, so disable() can revert.
        self._patched_processors: list[tuple[SpanProcessor, SpanExporter]] = []
        # OTEL's TracerProvider exposes no processor-removal API, so we only ever
        # ``add_span_processor`` once and rely on activate()/deactivate() after.
        self._dedup_registered = False
        # Env vars we set for content capture, and their prior values (``None``
        # meaning "was not set"), so disable() restores the process environment.
        self._patched_env: dict[str, Optional[str]] = {}

    @property
    def framework_name(self) -> str:
        return "google_adk"

    def is_installed(self) -> bool:
        """Return True only when a *usable* google-adk install is present.

        Two-step probe: the top-level package plus the telemetry module we
        translate. ``google`` is a namespace package shared by many unrelated
        distributions, so importing ``google.adk`` alone can succeed against a
        partial install; requiring ``google.adk.telemetry.tracing`` confirms the
        piece this integration actually depends on is there.
        """
        try:
            import google.adk  # type: ignore  # noqa: F401
            from google.adk.telemetry import tracing  # type: ignore  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self):  # type: ignore[override]
        """Return (and lazily build) the ADK span processor.

        For ADK this is not a "callback" in the LangChain sense. We return the
        processor object so consumers calling ``integration.callback()`` get a
        useful handle, but the work happens in :meth:`enable`. It is created
        exactly once per integration instance because OTEL exposes no processor
        removal API; the same instance is toggled by ``enable()`` / ``disable()``.
        """
        if self._dedup_processor is None:
            self._dedup_processor = GoogleADKLLMDedupSpanProcessor()
        return self._dedup_processor

    def enable(self) -> bool:
        """Enable observation for Google ADK.

        Steps:

        1. Verify google-adk is installed.
        2. Verify the active tracer provider is a Rhesis SDK ``TracerProvider``.
        3. Wrap each existing exporter with
           :class:`GoogleADKTranslatingExporter`. This is the whole integration:
           ADK is already emitting spans, and if we cannot translate them the
           backend rejects them, so a failure here fails the enable.
        4. Configure ADK's content-capture knobs. Nothing is touched in the
           default (capture-on) case -- ADK already records prompts and tool I/O
           into its span attributes. When ``RHESIS_DISABLE_CONTENT_CAPTURE`` is
           truthy, all three knobs are switched off.
        5. Register the span processor that indexes span structure (for handoff
           edges and for re-pointing children of dropped spans), captures
           per-trace conversation input/output, and toggles the LLM-observation
           flag during model spans so flag-checking auto-instrumentation in the
           same process does not emit a duplicate ``ai.llm.invoke``.

        Returns:
            ``True`` if successfully enabled, ``False`` if google-adk is not
            installed, the active provider is not Rhesis's, or no exporter could
            be wrapped for translation.
        """
        if self._enabled:
            logger.debug("google_adk observation already enabled")
            return True

        if not self.is_installed():
            logger.debug("google_adk not installed")
            return False

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            logger.warning(
                "Active tracer provider is %s, not a Rhesis TracerProvider; "
                "Google ADK spans will still be emitted but will not be translated "
                "and the backend will reject them. Did you forget to create a "
                "RhesisClient before calling auto_instrument()? Returning False so "
                "auto_instrument() does not list google_adk as enabled.",
                type(provider).__name__,
            )
            return False

        if not self._wrap_existing_exporters(provider):
            return False

        capture_content = content_capture_enabled()
        self._configure_content_capture(capture_content)

        self._dedup_processor = self._create_callback()
        if not self._dedup_registered:
            provider.add_span_processor(self._dedup_processor)  # type: ignore[arg-type]
            self._dedup_registered = True
        self._dedup_processor.activate()

        self._callback = self._dedup_processor
        self._enabled = True
        logger.info(
            "✓ Observing google_adk (Google Agent Development Kit); telemetry schema v%d; "
            "content capture %s; infra spans %s",
            _resolved_schema_version(),
            "enabled" if capture_content else f"disabled via {DISABLE_CONTENT_CAPTURE_ENV}",
            "kept" if verbose_spans_enabled() else "trimmed (send_data/caching/merged-tool)",
        )
        return True

    def disable(self) -> None:
        """Disable the integration: unwrap exporters, restore env, stop the processor.

        Note: ADK itself has no "disable instrumentation" switch, so it keeps
        emitting spans. Once the exporters are unwrapped those spans pass through
        untranslated and the backend rejects them individually -- which is the
        same state as never having enabled the integration.

        The span processor stays attached to the ``TracerProvider`` because OTEL
        exposes no removal API; we deactivate it instead so its hooks become
        no-ops. A subsequent ``enable()`` re-activates the same instance, so
        nothing leaks across cycles.
        """
        if not self._enabled:
            return

        for processor, original_exporter in self._patched_processors:
            try:
                set_processor_exporter(processor, original_exporter)
            except Exception:  # noqa: BLE001
                logger.debug("Failed to revert exporter on processor %r", processor, exc_info=True)
        self._patched_processors.clear()

        self._restore_content_capture_env()

        if self._dedup_processor is not None:
            self._dedup_processor.deactivate()
        self._callback = None
        self._enabled = False
        logger.info("✗ Stopped observing google_adk")

    def _configure_content_capture(self, capture_content: bool) -> None:
        """Align ADK's three content-capture knobs with the Rhesis setting.

        With capture on (the default) we set **nothing**. ADK's
        ``ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS`` already defaults to on, which is
        the only source the translator needs. In particular we never set
        ``OTEL_SEMCONV_STABILITY_OPT_IN``: it is a global OpenTelemetry switch
        that changes the attribute shape emitted by unrelated instrumentation
        libraries in the same process, and going behind their back would be a
        nasty surprise. The translator reads the experimental attributes when an
        app has opted in itself.

        With capture off we force all three knobs, including the admin lock, and
        log anything we overrode. The privacy opt-out deliberately wins over
        whatever the app configured: the safe direction for a "do not record
        prompts" request is to over-apply it.
        """
        if capture_content:
            return

        for name, value in _CONTENT_OFF_ENV.items():
            previous = os.environ.get(name)
            if previous == value:
                continue
            if previous is not None:
                logger.info(
                    "%s is set, overriding %s=%r with %r",
                    DISABLE_CONTENT_CAPTURE_ENV,
                    name,
                    previous,
                    value,
                )
            self._patched_env.setdefault(name, previous)
            os.environ[name] = value

    def _restore_content_capture_env(self) -> None:
        """Put back any content-capture env var :meth:`enable` changed."""
        for name, previous in self._patched_env.items():
            try:
                if previous is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = previous
            except Exception:  # noqa: BLE001
                logger.debug("Failed to restore env var %s", name, exc_info=True)
        self._patched_env.clear()

    def _wrap_existing_exporters(self, provider: TracerProvider) -> bool:
        """Find every wrappable span processor on the provider and wrap its exporter.

        Walks the provider's ``_active_span_processor`` (a multi-processor
        composite) and replaces each :class:`BatchSpanProcessor` /
        :class:`SimpleSpanProcessor` underlying exporter with a
        :class:`GoogleADKTranslatingExporter`. Already-translating exporters are
        skipped so :meth:`enable` is idempotent.

        Returns:
            ``True`` when at least one exporter is wrapped (or was already
            wrapped), ``False`` when translation could not be installed -- in
            which case :meth:`enable` fails closed, because ADK is emitting
            spans the backend would reject either way and claiming success would
            be a lie.
        """
        try:
            multi = getattr(provider, "_active_span_processor", None)
            children = getattr(multi, "_span_processors", ()) if multi is not None else ()
        except Exception:  # noqa: BLE001
            logger.warning(
                "Could not introspect provider span processors; refusing to enable "
                "the Google ADK integration since translation of its spans cannot "
                "be guaranteed",
                exc_info=True,
            )
            return False

        verbose_spans = verbose_spans_enabled()

        wrapped_count = 0
        already_wrapped_count = 0
        for child in children:
            if not isinstance(child, _WRAPPABLE_PROCESSORS):
                continue
            current = get_processor_exporter(child)
            if current is None:
                continue
            if isinstance(current, GoogleADKTranslatingExporter):
                already_wrapped_count += 1
                continue
            try:
                set_processor_exporter(
                    child,
                    GoogleADKTranslatingExporter(current, verbose_spans=verbose_spans),
                )
                self._patched_processors.append((child, current))
                wrapped_count += 1
                logger.debug(
                    "Wrapped exporter %s on processor %r with GoogleADKTranslatingExporter",
                    type(current).__name__,
                    child,
                )
            except Exception:  # noqa: BLE001
                logger.warning("Failed to wrap exporter on processor %r", child, exc_info=True)

        if wrapped_count == 0 and already_wrapped_count == 0:
            logger.warning(
                "google_adk: no batch/simple span processor with a wrappable "
                "exporter found on the active TracerProvider; refusing to claim "
                "the integration is enabled when ADK's raw span names (call_llm, "
                "invoke_agent <name>) would be rejected by the backend. Ensure "
                "RhesisClient is created before auto_instrument()."
            )
            return False
        return True


_google_adk_integration = GoogleADKIntegration()


def get_integration() -> GoogleADKIntegration:
    """Return the singleton :class:`GoogleADKIntegration` instance."""
    return _google_adk_integration
