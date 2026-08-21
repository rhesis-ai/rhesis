"""Adapters that let one set of tracing assertions run against either Haystack integration.

The native integration (``rhesis-sdk[haystack]``) and deepset's upstream one (``rhesis-haystack``)
expose the same ``RhesisTracing`` / ``RhesisTelemetry`` / ``RhesisTracer`` API, so the tests can be
written once and parametrized. Only two things genuinely differ:

- the import path
- how ``RhesisTracing`` gets its provider. Upstream builds a private one through
  ``RhesisConnector``; native reuses whatever provider ``RhesisClient`` installed. So each adapter
  supplies its own way of pointing ``RhesisTracing`` at an in-memory provider.

The upstream adapter is skipped when its package is absent, which is the normal state of this repo
until that work lands on main. Install it to activate those params:

    uv pip install -e <path-to>/haystack-core-integrations/integrations/rhesis
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any, Callable

NATIVE_MODULE = "rhesis.sdk.telemetry.integrations.haystack"
UPSTREAM_MODULE = "haystack_integrations.tracing.rhesis"


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


NATIVE_INSTALLED = _installed(NATIVE_MODULE)
UPSTREAM_INSTALLED = _installed(UPSTREAM_MODULE)


@dataclass(frozen=True)
class Integration:
    """One integration's symbols, plus how to aim its ``RhesisTracing`` at a test provider."""

    name: str
    RhesisTracing: Any
    RhesisTelemetry: Any
    RhesisTracer: Any
    rhesis_invocation_context: Any
    # Called with (monkeypatch, provider) before RhesisTracing() is constructed.
    aim_at_provider: Callable[[Any, Any], None]


def _aim_native(monkeypatch: Any, provider: Any) -> None:
    """Make the native ``RhesisTracing`` adopt ``provider``.

    Native reads the active OpenTelemetry provider and expects a ``RhesisClient`` to exist, so both
    are stubbed rather than building a real client that would resolve a project over HTTP. Mirrors
    the ``sdk_provider`` fixture in the SDK's own suite.
    """
    from opentelemetry import trace as otel_trace

    class _StubClient:
        project_id = "proj-test"
        environment = "test"
        _base_url = "http://localhost:8080"
        api_key = "test-key"

    monkeypatch.setenv("RHESIS_API_KEY", "test-key")
    monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: provider)
    monkeypatch.setattr(
        "rhesis.sdk.decorators.get_default_client", lambda: _StubClient(), raising=False
    )


def _aim_upstream(monkeypatch: Any, provider: Any) -> None:
    """Make the upstream ``RhesisTracing`` adopt ``provider``.

    Upstream constructs a ``RhesisConnector``, which would build its own provider and exporter, so
    the connector is stubbed to hand back this one instead.
    """
    import haystack_integrations.components.connectors.rhesis as connector_module
    from haystack_integrations.tracing.rhesis.tracer import RhesisTelemetry

    class _StubConnector:
        def __init__(self, name: str, **kwargs: Any) -> None:
            self.tracer = type(
                "_StubTracer",
                (),
                {
                    "telemetry": RhesisTelemetry(
                        provider=provider,
                        otel_tracer=provider.get_tracer("visit-prep-turn"),
                        project_id="proj-test",
                        environment="test",
                        base_url="http://localhost:8080",
                    ),
                    "flush": lambda self: None,
                },
            )()

    monkeypatch.setenv("RHESIS_API_KEY", "test-key")
    monkeypatch.setattr(connector_module, "RhesisConnector", _StubConnector)


def load(name: str) -> Integration:
    """Import one integration's symbols. Raises ImportError when it is not installed."""
    if name == "native":
        from rhesis.sdk.telemetry.integrations.haystack import RhesisTracing
        from rhesis.sdk.telemetry.integrations.haystack.tracer import (
            RhesisTelemetry,
            RhesisTracer,
            rhesis_invocation_context,
        )

        return Integration(
            name="native",
            RhesisTracing=RhesisTracing,
            RhesisTelemetry=RhesisTelemetry,
            RhesisTracer=RhesisTracer,
            rhesis_invocation_context=rhesis_invocation_context,
            aim_at_provider=_aim_native,
        )

    if name == "upstream":
        from haystack_integrations.tracing.rhesis import RhesisTracing
        from haystack_integrations.tracing.rhesis.tracer import (
            RhesisTelemetry,
            RhesisTracer,
            rhesis_invocation_context,
        )

        return Integration(
            name="upstream",
            RhesisTracing=RhesisTracing,
            RhesisTelemetry=RhesisTelemetry,
            RhesisTracer=RhesisTracer,
            rhesis_invocation_context=rhesis_invocation_context,
            aim_at_provider=_aim_upstream,
        )

    raise ValueError(f"unknown integration {name!r}")
