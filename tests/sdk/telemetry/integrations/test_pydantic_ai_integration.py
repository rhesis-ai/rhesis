"""Tests for Pydantic AI auto-instrumentation integration.

Verifies that the SDK correctly patches Agent.run to inject OpenTelemetry
spans (covering run_sync too, since it delegates to run internally), and
that the captured attributes/events match Rhesis's AI semantic conventions.
"""

import asyncio
import importlib

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from rhesis.sdk.telemetry.integrations.pydantic_ai import (
    AgentPatchState,
    PydanticAIIntegration,
)

# `rhesis.sdk.telemetry.integrations.__init__` rebinds the name `pydantic_ai` in the
# parent package namespace to the singleton instance, so `import ...pydantic_ai as x`
# would bind `x` to that instance rather than the module. Go through sys.modules
# (via importlib) to get the actual module unambiguously.
pyai_module = importlib.import_module("rhesis.sdk.telemetry.integrations.pydantic_ai")


@pytest.fixture(autouse=True)
def reset_patch_state():
    """Reset Agent patching state before each test.

    Agent.run is patched on the real, shared pydantic_ai.Agent class, so
    leaving it patched after a test would leak into every other test
    module that imports Agent (e.g. the Penelope target tests). Capture
    and restore the real method around each test.
    """
    original_run = Agent.run

    pyai_module._agent_patching_done = False
    pyai_module._original_agent_run = None
    yield
    Agent.run = original_run
    pyai_module._agent_patching_done = False
    pyai_module._original_agent_run = None


@pytest.fixture
def span_exporter(monkeypatch):
    """Route the integration's tracer to an in-memory exporter for assertions."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.pydantic_ai")

    monkeypatch.setattr(pyai_module.trace, "get_tracer", lambda *a, **kw: tracer)
    return exporter


@pytest.fixture
def integration():
    """Create a fresh PydanticAIIntegration."""
    return PydanticAIIntegration()


@pytest.fixture
def agent():
    """Create a Pydantic AI agent backed by TestModel."""
    return Agent(TestModel(custom_output_text="hello from test model"), name="my-agent")


def _spans_named(exporter, name):
    return [s for s in exporter.get_finished_spans() if s.name == name]


# --- Import and API surface tests ---


class TestPydanticAIImports:
    def test_agent_import(self):
        assert Agent is not None

    def test_agent_has_run(self):
        assert hasattr(Agent, "run")

    def test_agent_has_run_sync(self):
        assert hasattr(Agent, "run_sync")


# --- Integration enable/patching tests ---


class TestAgentPatching:
    def test_is_installed(self, integration):
        assert integration.is_installed() is True

    def test_enable_succeeds(self, integration, span_exporter):
        assert integration.enable() is True
        assert integration.enabled is True

    def test_enable_patches_run(self, integration, span_exporter):
        integration.enable()
        assert AgentPatchState.is_done()
        assert AgentPatchState.get_run() is not None

    def test_run_is_patched(self, integration, span_exporter):
        integration.enable()
        original = AgentPatchState.get_run()
        assert Agent.run is not original

    def test_callback_is_tracer(self, integration, span_exporter):
        integration.enable()
        assert integration._callback is not None

    def test_enable_idempotent(self, integration, span_exporter):
        integration.enable()
        first_callback = integration._callback
        integration.enable()
        assert integration._callback is first_callback


# --- Instrumented invocation tests ---


class TestInstrumentedInvocation:
    def test_run_sync_returns_output(self, integration, span_exporter, agent):
        integration.enable()
        result = agent.run_sync("hi there")
        assert result.output == "hello from test model"

    def test_run_sync_creates_single_span(self, integration, span_exporter, agent):
        """run_sync delegates to run() internally - patching run() alone must
        not produce a duplicate nested span for a single run_sync() call."""
        integration.enable()
        agent.run_sync("hi there")

        spans = _spans_named(span_exporter, "ai.agent.invoke")
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    def test_run_sync_span_attributes(self, integration, span_exporter, agent):
        integration.enable()
        agent.run_sync("hi there")

        span = _spans_named(span_exporter, "ai.agent.invoke")[0]
        assert span.attributes["ai.operation.type"] == "agent.invoke"
        assert span.attributes["ai.agent.name"] == "my-agent"
        assert span.attributes["ai.model.name"] == "test"
        assert span.attributes["ai.model.provider"] == "test"
        assert span.attributes["ai.llm.tokens.input"] > 0
        assert span.attributes["ai.llm.tokens.output"] > 0
        assert (
            span.attributes["ai.llm.tokens.total"]
            == span.attributes["ai.llm.tokens.input"] + span.attributes["ai.llm.tokens.output"]
        )

    def test_run_sync_span_events(self, integration, span_exporter, agent):
        integration.enable()
        agent.run_sync("hi there")

        span = _spans_named(span_exporter, "ai.agent.invoke")[0]
        event_names = [e.name for e in span.events]
        assert "ai.prompt" in event_names
        assert "ai.completion" in event_names

        prompt_event = next(e for e in span.events if e.name == "ai.prompt")
        assert prompt_event.attributes["ai.prompt.content"] == "hi there"

        completion_event = next(e for e in span.events if e.name == "ai.completion")
        assert completion_event.attributes["ai.completion.content"] == "hello from test model"

    def test_async_run_creates_span(self, integration, span_exporter, agent):
        integration.enable()

        result = asyncio.run(agent.run("hi there"))
        assert result.output == "hello from test model"

        spans = _spans_named(span_exporter, "ai.agent.invoke")
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    def test_run_sync_error_sets_error_status(self, integration, span_exporter, agent):
        integration.enable()

        with pytest.raises(Exception):
            agent.run_sync(None)

        span = _spans_named(span_exporter, "ai.agent.invoke")[0]
        assert span.status.status_code == StatusCode.ERROR
        assert any(e.name == "exception" for e in span.events)
