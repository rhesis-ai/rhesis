"""Fixtures for the Haystack integration tests.

Every fixture here is scoped to this package. Three of the four are autouse because the state they
manage is process-wide: Haystack's content-tracing flag, the integration's ContextVars, and the
tracer Haystack keeps in a module-level global.
"""

import pytest

pytest.importorskip("haystack")

from haystack import tracing
from opentelemetry import context as otel_context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from rhesis.sdk.telemetry.integrations.haystack.integration import get_integration
from rhesis.sdk.telemetry.integrations.haystack.tracer import (
    RhesisTelemetry,
    RhesisTracer,
    span_stack_var,
    trace_id_var,
    tracing_context_var,
)


@pytest.fixture(autouse=True)
def content_tracing_enabled(monkeypatch):
    """Force Haystack's content-tracing flag on.

    Patches the resolved flag rather than ``HAYSTACK_CONTENT_TRACING_ENABLED``: Haystack reads that
    variable once, when ``haystack.tracing`` is imported, so patching the env var would make the
    suite depend on collection order.
    """
    monkeypatch.setattr(tracing.tracer, "is_content_tracing_enabled", True)


@pytest.fixture(autouse=True)
def isolate_otel_context():
    """Give each test a fresh OpenTelemetry context.

    A test that opens a span through ``DefaultSpanHandler.create_span`` without closing it leaves
    that span attached as the current one. Without this, the next test's "root" span would nest
    under it and inherit its trace id -- an order-dependent failure that only shows up when the
    whole file runs.
    """
    token = otel_context.attach(otel_context.Context())
    yield
    otel_context.detach(token)


@pytest.fixture(autouse=True)
def reset_context_vars():
    """Give each test its own ContextVar state.

    pytest runs the whole session in one context, so a test that sets an invocation context or
    leaves a span on the stack would otherwise be visible to the next one.
    """
    context_token = tracing_context_var.set({})
    stack_token = span_stack_var.set(None)
    trace_token = trace_id_var.set("")
    yield
    tracing_context_var.reset(context_token)
    span_stack_var.reset(stack_token)
    trace_id_var.reset(trace_token)


@pytest.fixture(autouse=True)
def reset_global_tracer():
    """Undo the process-wide tracer registration and integration state after each test."""
    yield
    integration = get_integration()
    integration.disable()
    # Reset the settings ``configure()`` may have changed, so tests do not inherit each other's
    # trace name or span handler.
    integration._trace_name = "Haystack"
    integration._span_handler = None
    integration._frontend_url = None
    tracing.disable_tracing()


@pytest.fixture
def traced_exporter():
    """A real tracer wired to an in-memory exporter, registered with Haystack.

    Yields ``(exporter, tracer)``. ``enforce_flush`` is off so tests do not pay a force-flush per
    run; ``SimpleSpanProcessor`` exports synchronously, so spans are readable immediately.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    telemetry = RhesisTelemetry(
        provider=provider,
        otel_tracer=provider.get_tracer("rhesis-tests"),
        project_id="proj-test",
        environment="test",
        base_url="http://localhost:8080",
    )
    tracer = RhesisTracer(telemetry=telemetry, name="rhesis-tests")
    tracer.enforce_flush = False
    tracing.enable_tracing(tracer)
    yield exporter, tracer
    tracing.disable_tracing()


class StubClient:
    """Stands in for a RhesisClient that has already installed a provider."""

    def __init__(self, project_id="proj-test", environment="test", base_url=None):
        self.project_id = project_id
        self.environment = environment
        self._base_url = base_url or "http://localhost:8080"
        self.api_key = "rh-test-token"


@pytest.fixture
def sdk_provider(monkeypatch):
    """Pretend a ``RhesisClient`` already installed an SDK tracer provider.

    ``trace.set_tracer_provider`` is only honoured once per process, so patching the getter is the
    only way to give each test its own provider. Also stubs the default client, so nothing tries to
    build a real one (which would resolve a project id over HTTP).

    Yields ``(exporter, provider)``.
    """
    from opentelemetry import trace as otel_trace

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: provider)
    monkeypatch.setattr(
        "rhesis.sdk.decorators.get_default_client", lambda: StubClient(), raising=False
    )
    yield exporter, provider
