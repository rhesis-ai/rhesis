"""Tests for Haystack span mapping and translation."""

import importlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.trace import Event

from rhesis.sdk.telemetry.attributes import AIAttributes, validate_span_name
from rhesis.sdk.telemetry.integrations.haystack import (
    HaystackTranslatingExporter,
    mapping,
    translate_span,
)
from rhesis.sdk.telemetry.integrations.tracing_helpers import sanitize_for_tracing, truncate_content
from rhesis.telemetry.schemas import AIOperationType

INTEGRATION_MODULE = importlib.import_module(
    "rhesis.sdk.telemetry.integrations.haystack.integration"
)


@pytest.fixture(autouse=True)
def reset_haystack_patch_state():
    INTEGRATION_MODULE.HaystackPatchState.reset()
    yield
    INTEGRATION_MODULE.HaystackPatchState.reset()


def _span(name, attributes=None, events=(), scope_name="rhesis.sdk.haystack"):
    return SimpleNamespace(
        name=name,
        attributes=attributes or {},
        events=events,
        instrumentation_scope=SimpleNamespace(name=scope_name),
    )


def test_translate_pipeline_run_span():
    translated = translate_span(
        _span(
            "haystack.pipeline.run",
            {
                "haystack.pipeline.input_data": json.dumps({"query": "hello"}),
                "haystack.pipeline.output_data": json.dumps({"answer": "world"}),
                "haystack.pipeline.metadata": json.dumps({"name": "qa-pipeline"}),
            },
        )
    )

    assert translated.name == AIOperationType.AGENT_INVOKE
    assert validate_span_name(translated.name)
    assert translated.attributes[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_AGENT_INVOKE
    assert translated.attributes[AIAttributes.AGENT_NAME] == "qa-pipeline"
    event_names = {event.name for event in translated.events}
    assert "ai.agent.input" in event_names
    assert "ai.agent.output" in event_names


def test_translate_llm_component_span_with_tokens():
    output = {
        "replies": [
            {
                "role": "assistant",
                "content": "Paris",
                "meta": {
                    "model": "gpt-4o-mini",
                    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
                },
            }
        ]
    }
    translated = translate_span(
        _span(
            "haystack.component.run",
            {
                "haystack.component.name": "generator",
                "haystack.component.type": "OpenAIChatGenerator",
                "haystack.component.fully_qualified_type": "haystack.components.generators.chat.OpenAIChatGenerator",
                "haystack.component.input": json.dumps({"messages": [{"role": "user", "content": "Capital of France?"}]}),
                "haystack.component.output": json.dumps(output),
            },
        )
    )

    assert translated.name == AIOperationType.LLM_INVOKE
    assert translated.attributes[AIAttributes.MODEL_NAME] == "gpt-4o-mini"
    assert translated.attributes[AIAttributes.MODEL_PROVIDER] == "openai"
    assert translated.attributes[AIAttributes.LLM_TOKENS_INPUT] == 12
    assert translated.attributes[AIAttributes.LLM_TOKENS_OUTPUT] == 3
    assert translated.attributes[AIAttributes.LLM_TOKENS_TOTAL] == 15
    event_names = {event.name for event in translated.events}
    assert "ai.prompt" in event_names
    assert "ai.completion" in event_names


def test_translate_retriever_component_span():
    translated = translate_span(
        _span(
            "haystack.component.run",
            {
                "haystack.component.name": "retriever",
                "haystack.component.type": "InMemoryBM25Retriever",
                "haystack.component.fully_qualified_type": "haystack.components.retrievers.in_memory.InMemoryBM25Retriever",
                "haystack.component.input": json.dumps({"query": "Haystack docs"}),
                "haystack.component.output": json.dumps({"documents": [{"content": "doc"}]}),
            },
        )
    )

    assert translated.name == AIOperationType.RETRIEVAL
    event_names = {event.name for event in translated.events}
    assert "ai.retrieval.query" in event_names
    assert "ai.retrieval.results" in event_names


def test_translating_exporter_passes_through_non_haystack_spans():
    exported = []

    class _CaptureExporter:
        def export(self, spans):
            exported.extend(spans)
            return 0

    exporter = HaystackTranslatingExporter(_CaptureExporter())
    other = _span("ai.llm.invoke", {"ai.model.name": "gpt-4"}, scope_name="other")
    exporter.export([other])

    assert exported[0].name == "ai.llm.invoke"


def test_sanitize_binary_and_signed_urls():
    assert sanitize_for_tracing(b"secret-bytes") == "[binary data omitted]"
    signed = "https://example.com/file?X-Amz-Signature=abc123"
    assert sanitize_for_tracing(signed) == "[signed url omitted]"
    embedding = [0.1] * 128
    assert "embedding vector omitted" in truncate_content(embedding)


def test_mapping_classifies_handoff_component():
    name = mapping.translate_span_name(
        "haystack.component.run",
        {
            "haystack.component.type": "AgentHandoff",
            "haystack.component.fully_qualified_type": "haystack.components.agents.AgentHandoff",
        },
    )
    assert name == AIOperationType.AGENT_HANDOFF


def test_enable_wraps_exporter_and_translates_spans():
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult

    class CaptureExporter:
        def __init__(self):
            self.spans = []

        def export(self, spans):
            self.spans.extend(spans)
            return SpanExportResult.SUCCESS

        def shutdown(self):
            return None

        def force_flush(self, timeout_millis=30000):
            return True

    provider = TracerProvider()
    capture = CaptureExporter()
    provider.add_span_processor(BatchSpanProcessor(capture))

    integration = INTEGRATION_MODULE.HaystackIntegration()
    integration._wrap_existing_exporters(provider)
    assert len(integration._patched_processors) == 1

    wrapped_exporter = integration._patched_processors[0][0].span_exporter
    wrapped_exporter.export(
        [
            _span(
                "haystack.component.run",
                {
                    "haystack.component.type": "OpenAIChatGenerator",
                    "haystack.component.name": "generator",
                    "haystack.component.fully_qualified_type": "haystack.components.generators.chat.OpenAIChatGenerator",
                    "haystack.component.output": json.dumps(
                        {"replies": [{"role": "assistant", "content": "ok"}]}
                    ),
                },
            )
        ]
    )

    assert capture.spans
    assert capture.spans[0].name == AIOperationType.LLM_INVOKE
    integration.disable()


def test_enable_falls_back_to_pipeline_patch(monkeypatch):
    class FakePipeline:
        def run(self, data=None, *args, **kwargs):
            return {"answer": "ok"}

    fake_haystack = MagicMock()
    fake_haystack.Pipeline = FakePipeline
    monkeypatch.setitem(__import__("sys").modules, "haystack", fake_haystack)

    def _boom():
        raise ImportError("tracing unavailable")

    monkeypatch.setattr(
        INTEGRATION_MODULE,
        "_enable_haystack_tracing",
        _boom,
    )

    integration = INTEGRATION_MODULE.HaystackIntegration()
    assert integration.enable() is True
    assert INTEGRATION_MODULE.HaystackPatchState.is_done() is True
    integration.disable()
    assert INTEGRATION_MODULE.HaystackPatchState.is_done() is False
