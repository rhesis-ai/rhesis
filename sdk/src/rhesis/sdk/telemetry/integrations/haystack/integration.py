"""Haystack integration for Rhesis observability.

Haystack does not emit OpenTelemetry spans on its own. It has its own tracing abstraction and you
register an implementation with ``haystack.tracing.enable_tracing``. So this integration follows
the same registration shape as the LangChain one rather than the exporter-wrapping shape used for
Google ADK, MAF and Pydantic AI: there is nothing to translate after the fact, because
:class:`~rhesis.sdk.telemetry.integrations.haystack.tracer.RhesisTracer` writes Rhesis span names
and attributes as the spans are opened.

Nothing in this module imports Haystack at module level. ``tracer.py`` does -- it subclasses
Haystack base classes -- so it is imported lazily, which is what keeps
``from rhesis.sdk.telemetry.integrations import get_all_integrations`` working for users who do not
have Haystack installed.

Usage::

    import os

    os.environ["HAYSTACK_CONTENT_TRACING_ENABLED"] = "true"  # before importing haystack

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)
    auto_instrument("haystack")

    # Now every pipeline run, component, agent step and tool call produces Rhesis spans.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from rhesis.sdk.telemetry.integrations.base import BaseIntegration

if TYPE_CHECKING:
    from rhesis.sdk.telemetry.integrations.haystack.tracer import (
        RhesisTelemetry,
        RhesisTracer,
        SpanHandler,
    )

logger = logging.getLogger(__name__)

DEFAULT_TRACE_NAME = "Haystack"
TRACE_NAME_ENV_VAR = "RHESIS_HAYSTACK_TRACE_NAME"
FRONTEND_URL_ENV_VAR = "RHESIS_FRONTEND_URL"

_OTEL_INSTRUMENTATION_SCOPE = "rhesis.sdk.telemetry.integrations.haystack"


def _resolve_config() -> tuple[Optional[str], str, str]:
    """Return ``(project_id, environment, base_url)`` for trace deep links and the span resource.

    Read from the default ``RhesisClient`` when one exists, since that is the client whose provider
    the spans are going to, and from the environment otherwise. Note this is not used to build a
    provider -- see :meth:`HaystackIntegration.enable`.
    """
    from rhesis.sdk.config import get_base_url
    from rhesis.sdk.decorators import get_default_client

    client = get_default_client()
    if client is not None:
        base_url = getattr(client, "_base_url", None) or getattr(client, "base_url", None)
        return (
            getattr(client, "project_id", None),
            getattr(client, "environment", None) or "development",
            base_url or get_base_url(),
        )
    return (
        os.getenv("RHESIS_PROJECT_ID"),
        os.getenv("RHESIS_ENVIRONMENT", "development"),
        get_base_url(),
    )


class HaystackIntegration(BaseIntegration):
    """Haystack framework integration for automatic tracing."""

    def __init__(self) -> None:
        super().__init__()
        self._trace_name = os.getenv(TRACE_NAME_ENV_VAR) or DEFAULT_TRACE_NAME
        self._span_handler: Optional[SpanHandler] = None
        self._frontend_url: Optional[str] = None
        self._telemetry: Optional[RhesisTelemetry] = None

    @property
    def framework_name(self) -> str:
        return "haystack"

    def is_installed(self) -> bool:
        """Return True only when a *usable* haystack-ai install is present.

        Two-step probe: the top-level package plus the tracing module this integration plugs into.
        ``haystack`` is also the name of the unrelated, long-abandoned ``haystack`` distribution on
        PyPI, and farm-haystack 1.x has no ``haystack.tracing`` at all, so requiring the tracing
        module confirms the piece this integration actually depends on is there.
        """
        try:
            import haystack  # noqa: F401
            from haystack.tracing import Tracer  # noqa: F401

            return True
        except ImportError:
            return False

    def configure(
        self,
        *,
        name: Optional[str] = None,
        span_handler: Optional[SpanHandler] = None,
        frontend_url: Optional[str] = None,
    ) -> None:
        """Set the trace name, span handler and frontend URL used when the tracer is built.

        Call before :meth:`enable`. When already enabled, the tracer is rebuilt and re-registered
        so the new settings take effect immediately.
        """
        if name:
            self._trace_name = name
        if span_handler is not None:
            self._span_handler = span_handler
        if frontend_url is not None:
            self._frontend_url = frontend_url
        if self._enabled:
            self._enabled = False
            self.enable()

    def _create_callback(self) -> Any:
        """Build the Haystack tracer.

        Not a callback in the LangChain sense -- Haystack takes a ``Tracer`` implementation. It is
        returned from here so ``integration.callback()`` yields a useful handle, and so the base
        class's lifecycle bookkeeping still applies.
        """
        from rhesis.sdk.telemetry.integrations.haystack.tracer import RhesisTelemetry, RhesisTracer

        provider = trace.get_tracer_provider()
        project_id, environment, base_url = _resolve_config()
        self._telemetry = RhesisTelemetry(
            provider=provider,  # type: ignore[arg-type]
            otel_tracer=provider.get_tracer(_OTEL_INSTRUMENTATION_SCOPE),
            project_id=project_id,
            environment=environment,
            base_url=base_url,
            frontend_url=self._frontend_url or os.getenv(FRONTEND_URL_ENV_VAR),
        )
        return RhesisTracer(
            telemetry=self._telemetry,
            name=self._trace_name,
            span_handler=self._span_handler,
        )

    def enable(self) -> bool:
        """Enable observation for Haystack.

        Steps:

        1. Verify haystack-ai is installed.
        2. Verify the active tracer provider is an OpenTelemetry SDK ``TracerProvider``. Rhesis
           installs one when a ``RhesisClient`` is created; the default global is a no-op proxy
           whose tracers drop every span, so enabling against it would report success and export
           nothing.
        3. Build the :class:`RhesisTracer` and register it with ``haystack.tracing.enable_tracing``.

        Returns:
            ``True`` if successfully enabled, ``False`` if haystack-ai is not installed or the
            active provider is not a real SDK provider.
        """
        if self._enabled:
            logger.debug("haystack observation already enabled")
            return True

        if not self.is_installed():
            logger.debug("haystack not installed")
            return False

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            logger.warning(
                "Active tracer provider is %s, not an OpenTelemetry SDK TracerProvider, so every "
                "Haystack span would be dropped instead of exported. Did you forget to create a "
                "RhesisClient before calling auto_instrument()? Returning False so "
                "auto_instrument() does not list haystack as enabled.",
                type(provider).__name__,
            )
            return False

        try:
            from haystack import tracing as haystack_tracing

            self._callback = self._create_callback()
            haystack_tracing.enable_tracing(self._callback)
            self._enabled = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to enable haystack: %s", exc)
            logger.debug("Full error:", exc_info=True)
            return False

        logger.info(
            "✓ Observing haystack (trace name %r); content capture %s; flush %s",
            self._trace_name,
            "enabled" if self._content_capture_state() else "disabled",
            "per run" if self._callback.enforce_flush else "batched",
        )
        return True

    def disable(self) -> None:
        """Unregister the tracer from Haystack.

        Haystack's ``disable_tracing`` swaps in its own no-op tracer, so pipeline runs after this
        emit nothing at all -- the same state as never having enabled the integration.
        """
        if not self._enabled:
            return

        try:
            from haystack import tracing as haystack_tracing

            haystack_tracing.disable_tracing()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to disable haystack tracing", exc_info=True)

        self._callback = None
        self._telemetry = None
        self._enabled = False
        logger.info("✗ Stopped observing haystack")

    def _content_capture_state(self) -> bool:
        from rhesis.sdk.telemetry.integrations.haystack.tracer import capture_content

        return capture_content()

    @property
    def telemetry(self) -> Optional[RhesisTelemetry]:
        """The provider and tracer spans are opened through, or ``None`` when disabled."""
        return self._telemetry

    def flush(self) -> None:
        """Flush pending Haystack spans. No-op when the integration is not enabled."""
        if self._telemetry is not None:
            self._telemetry.flush()


_haystack_integration = HaystackIntegration()


def get_integration() -> HaystackIntegration:
    """Return the singleton :class:`HaystackIntegration` instance."""
    return _haystack_integration


def get_tracer() -> Optional[RhesisTracer]:
    """Return the registered :class:`RhesisTracer`, or ``None`` when not enabled."""
    integration = get_integration()
    if integration.enabled:
        return integration.callback()
    return None


def get_trace_id() -> str:
    """Return the trace id of the Haystack run currently open in this context.

    Empty outside a run. This and :func:`get_trace_url` replace the ``trace_id``/``trace_url``
    outputs the upstream ``rhesis-haystack`` package exposes through its pipeline component, which
    this integration deliberately does not ship.
    """
    tracer = get_tracer()
    return tracer.get_trace_id() if tracer is not None else ""


def get_trace_url() -> str:
    """Return the Rhesis frontend deep link for the run currently open in this context.

    Empty outside a run, and empty when the frontend origin cannot be derived from the backend URL
    -- set ``RHESIS_FRONTEND_URL`` for self-hosted deployments.
    """
    tracer = get_tracer()
    return tracer.get_trace_url() if tracer is not None else ""
