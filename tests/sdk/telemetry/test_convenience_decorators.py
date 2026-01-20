"""Tests for convenience decorators (@observe.llm, @observe.tool, etc.)."""

from unittest.mock import MagicMock

import pytest

from rhesis.sdk.decorators import _state as decorators_state
from rhesis.sdk.decorators import observe
from rhesis.sdk.telemetry.attributes import AIAttributes


@pytest.fixture
def mock_client_with_tracer():
    """Create a mock client that executes functions properly."""
    mock_client = MagicMock()

    # Mock tracer that executes functions
    mock_tracer = MagicMock()
    mock_tracer.trace_execution = MagicMock(
        side_effect=lambda fn, f, a, k, sn=None, ea=None: f(*a, **k)
    )
    mock_tracer.trace_execution_async = MagicMock(
        side_effect=lambda fn, f, a, k, sn=None, ea=None: f(*a, **k)
    )

    mock_client._tracer = mock_tracer

    return mock_client


class TestConvenienceDecorators:
    """Tests for convenience decorators on the observe instance."""

    def test_observe_has_convenience_methods(self):
        """Test that observe instance has all convenience methods."""
        assert hasattr(observe, "llm")
        assert hasattr(observe, "tool")
        assert hasattr(observe, "retrieval")
        assert hasattr(observe, "embedding")
        assert hasattr(observe, "rerank")
        assert hasattr(observe, "evaluation")
        assert hasattr(observe, "guardrail")
        assert hasattr(observe, "transform")

    def test_observe_llm_decorator(self, mock_client_with_tracer):
        """Test @observe.llm() creates correct span and attributes."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.llm(provider="openai", model="gpt-4", temperature=0.7)
        def generate_text(prompt: str) -> str:
            return f"Generated: {prompt}"

        result = generate_text("Hello")
        assert result == "Generated: Hello"

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args

        extra_attrs = call_args[0][5]
        assert extra_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_LLM_INVOKE
        assert extra_attrs[AIAttributes.MODEL_PROVIDER] == "openai"
        assert extra_attrs[AIAttributes.MODEL_NAME] == "gpt-4"
        assert extra_attrs["temperature"] == 0.7

        decorators_state._default_client = None

    def test_observe_tool_decorator(self, mock_client_with_tracer):
        """Test @observe.tool() creates correct span and attributes."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.tool(name="weather_api", tool_type="http", timeout=30)
        def get_weather(city: str) -> dict:
            return {"city": city, "temperature": 22}

        result = get_weather("San Francisco")
        assert result == {"city": "San Francisco", "temperature": 22}

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args

        extra_attrs = call_args[0][5]
        assert extra_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_TOOL_INVOKE
        assert extra_attrs[AIAttributes.TOOL_NAME] == "weather_api"
        assert extra_attrs[AIAttributes.TOOL_TYPE] == "http"
        assert extra_attrs["timeout"] == 30

        decorators_state._default_client = None

    def test_observe_retrieval_decorator(self, mock_client_with_tracer):
        """Test @observe.retrieval() creates correct span and attributes."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.retrieval(backend="vector_db", top_k=5)
        def search_docs(query: str) -> list:
            return ["doc1", "doc2"]

        result = search_docs("test query")
        assert result == ["doc1", "doc2"]

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args

        extra_attrs = call_args[0][5]
        assert extra_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_RETRIEVAL

        decorators_state._default_client = None

    def test_observe_embedding_decorator(self, mock_client_with_tracer):
        """Test @observe.embedding() creates correct span and attributes."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.embedding(model="text-embedding-ada-002", dimensions=1536)
        def embed_text(text: str) -> list:
            return [0.1, 0.2, 0.3]

        result = embed_text("test")
        assert result == [0.1, 0.2, 0.3]

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args

        extra_attrs = call_args[0][5]
        assert extra_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_EMBEDDING_CREATE

        decorators_state._default_client = None

    def test_observe_rerank_decorator(self, mock_client_with_tracer):
        """Test @observe.rerank() creates correct span and attributes."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.rerank(model="rerank-english-v2.0", top_n=3)
        def rerank_docs(query: str, docs: list) -> list:
            return docs[::-1]

        result = rerank_docs("query", ["a", "b", "c"])
        assert result == ["c", "b", "a"]

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args

        extra_attrs = call_args[0][5]
        assert extra_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_RERANK

        decorators_state._default_client = None

    def test_observe_evaluation_decorator(self, mock_client_with_tracer):
        """Test @observe.evaluation() creates correct span and attributes."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.evaluation(metric="accuracy", evaluator="deepeval")
        def evaluate_response(response: str, expected: str) -> float:
            return 0.95

        result = evaluate_response("answer", "expected")
        assert result == 0.95

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args

        extra_attrs = call_args[0][5]
        assert extra_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_EVALUATION

        decorators_state._default_client = None

    def test_observe_guardrail_decorator(self, mock_client_with_tracer):
        """Test @observe.guardrail() creates correct span and attributes."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.guardrail(guardrail_type="content_filter", provider="guardrails")
        def check_content(text: str) -> bool:
            return True

        result = check_content("safe text")
        assert result is True

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args

        extra_attrs = call_args[0][5]
        assert extra_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_GUARDRAIL

        decorators_state._default_client = None

    def test_observe_transform_decorator(self, mock_client_with_tracer):
        """Test @observe.transform() creates correct span and attributes."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.transform(transform_type="text_to_json", operation="parse")
        def parse_response(text: str) -> dict:
            return {"parsed": text}

        result = parse_response("test")
        assert result == {"parsed": "test"}

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args

        extra_attrs = call_args[0][5]
        assert extra_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_TRANSFORM

        decorators_state._default_client = None

    def test_convenience_decorators_without_client_raise_error(self):
        """Test that convenience decorators raise error without client."""
        decorators_state._default_client = None

        @observe.llm(provider="openai", model="gpt-4")
        def generate_text(prompt: str) -> str:
            return f"Generated: {prompt}"

        with pytest.raises(RuntimeError, match="RhesisClient not initialized"):
            generate_text("Hello")

    def test_convenience_decorators_support_async_functions(self, mock_client_with_tracer):
        """Test that convenience decorators work with async functions."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.llm(provider="openai", model="gpt-4")
        async def async_generate(prompt: str) -> str:
            return f"Generated: {prompt}"

        # Note: In real async execution, we'd use await
        # For this test, we just verify the decorator doesn't break
        assert callable(async_generate)

        decorators_state._default_client = None

    def test_convenience_decorators_support_generator_functions(self, mock_client_with_tracer):
        """Test that convenience decorators work with generator functions."""
        decorators_state._default_client = mock_client_with_tracer

        @observe.llm(provider="openai", model="gpt-4")
        def stream_tokens(prompt: str):
            for token in ["Hello", " ", "World"]:
                yield token

        result = list(stream_tokens("test"))
        assert result == ["Hello", " ", "World"]

        mock_client_with_tracer._tracer.trace_execution.assert_called_once()

        decorators_state._default_client = None
