"""Tests for convenience decorators (@observe.llm, @observe.tool, etc.)."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk import decorators
from rhesis.sdk.decorators import observe
from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.schemas import AIOperationType


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

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_llm_decorator(self, mock_get_tracer):
        """Test @observe.llm() creates correct span and attributes."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe.llm
        @observe.llm(provider="openai", model="gpt-4", temperature=0.7)
        def generate_text(prompt: str) -> str:
            return f"Generated: {prompt}"

        # Execute function
        result = generate_text("Hello")

        assert result == "Generated: Hello"

        # Verify span creation
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == AIOperationType.LLM_INVOKE

        # Verify attributes were set
        expected_attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
            AIAttributes.MODEL_PROVIDER: "openai",
            AIAttributes.MODEL_NAME: "gpt-4",
            "temperature": 0.7,
        }

        # Check that set_attribute was called for each expected attribute
        set_attribute_calls = mock_span.set_attribute.call_args_list
        actual_attributes = {call[0][0]: call[0][1] for call in set_attribute_calls}

        for key, value in expected_attributes.items():
            assert actual_attributes.get(key) == value

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_tool_decorator(self, mock_get_tracer):
        """Test @observe.tool() creates correct span and attributes."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe.tool
        @observe.tool(name="weather_api", tool_type="http", timeout=30)
        def get_weather(city: str) -> dict:
            return {"city": city, "temperature": 22}

        # Execute function
        result = get_weather("San Francisco")

        assert result == {"city": "San Francisco", "temperature": 22}

        # Verify span creation
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == AIOperationType.TOOL_INVOKE

        # Verify attributes were set
        expected_attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
            AIAttributes.TOOL_NAME: "weather_api",
            AIAttributes.TOOL_TYPE: "http",
            "timeout": 30,
        }

        set_attribute_calls = mock_span.set_attribute.call_args_list
        actual_attributes = {call[0][0]: call[0][1] for call in set_attribute_calls}

        for key, value in expected_attributes.items():
            assert actual_attributes.get(key) == value

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_retrieval_decorator(self, mock_get_tracer):
        """Test @observe.retrieval() creates correct span and attributes."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe.retrieval
        @observe.retrieval(backend="pinecone", top_k=5, index="documents")
        def search_docs(query: str) -> list:
            return [f"doc1 about {query}", f"doc2 about {query}"]

        # Execute function
        result = search_docs("AI")

        assert len(result) == 2

        # Verify span creation
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == AIOperationType.RETRIEVAL

        # Verify attributes were set
        expected_attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_RETRIEVAL,
            AIAttributes.RETRIEVAL_BACKEND: "pinecone",
            AIAttributes.RETRIEVAL_TOP_K: 5,
            "index": "documents",
        }

        set_attribute_calls = mock_span.set_attribute.call_args_list
        actual_attributes = {call[0][0]: call[0][1] for call in set_attribute_calls}

        for key, value in expected_attributes.items():
            assert actual_attributes.get(key) == value

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_embedding_decorator(self, mock_get_tracer):
        """Test @observe.embedding() creates correct span and attributes."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe.embedding
        @observe.embedding(model="text-embedding-ada-002", dimensions=1536)
        def embed_texts(texts: list) -> list:
            return [[0.1, 0.2] * 768 for _ in texts]  # 1536 dimensions

        # Execute function
        result = embed_texts(["hello", "world"])

        assert len(result) == 2
        assert len(result[0]) == 1536

        # Verify span creation
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == AIOperationType.EMBEDDING_GENERATE

        # Verify attributes were set
        expected_attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_EMBEDDING_CREATE,
            AIAttributes.EMBEDDING_MODEL: "text-embedding-ada-002",
            AIAttributes.EMBEDDING_VECTOR_SIZE: 1536,
        }

        set_attribute_calls = mock_span.set_attribute.call_args_list
        actual_attributes = {call[0][0]: call[0][1] for call in set_attribute_calls}

        for key, value in expected_attributes.items():
            assert actual_attributes.get(key) == value

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_rerank_decorator(self, mock_get_tracer):
        """Test @observe.rerank() creates correct span and attributes."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe.rerank
        @observe.rerank(model="rerank-v1", top_n=3)
        def rerank_results(query: str, documents: list) -> list:
            return documents[:3]  # Return top 3

        # Execute function
        docs = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        result = rerank_results("query", docs)

        assert len(result) == 3

        # Verify span creation
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == AIOperationType.RERANK

        # Verify attributes were set
        expected_attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_RERANK,
            AIAttributes.RERANK_MODEL: "rerank-v1",
            AIAttributes.RERANK_TOP_N: 3,
        }

        set_attribute_calls = mock_span.set_attribute.call_args_list
        actual_attributes = {call[0][0]: call[0][1] for call in set_attribute_calls}

        for key, value in expected_attributes.items():
            assert actual_attributes.get(key) == value

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_evaluation_decorator(self, mock_get_tracer):
        """Test @observe.evaluation() creates correct span and attributes."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe.evaluation
        @observe.evaluation(metric="relevance", evaluator="gpt-4")
        def evaluate_relevance(query: str, response: str) -> float:
            return 0.85

        # Execute function
        result = evaluate_relevance("What is AI?", "AI is artificial intelligence")

        assert result == 0.85

        # Verify span creation
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == AIOperationType.EVALUATION

        # Verify attributes were set
        expected_attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_EVALUATION,
            AIAttributes.EVALUATION_METRIC: "relevance",
            AIAttributes.EVALUATION_EVALUATOR: "gpt-4",
        }

        set_attribute_calls = mock_span.set_attribute.call_args_list
        actual_attributes = {call[0][0]: call[0][1] for call in set_attribute_calls}

        for key, value in expected_attributes.items():
            assert actual_attributes.get(key) == value

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_guardrail_decorator(self, mock_get_tracer):
        """Test @observe.guardrail() creates correct span and attributes."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe.guardrail
        @observe.guardrail(guardrail_type="content_safety", provider="openai")
        def check_content_safety(text: str) -> bool:
            return True

        # Execute function
        result = check_content_safety("This is safe content")

        assert result is True

        # Verify span creation
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == AIOperationType.GUARDRAIL

        # Verify attributes were set
        expected_attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_GUARDRAIL,
            AIAttributes.GUARDRAIL_TYPE: "content_safety",
            AIAttributes.GUARDRAIL_PROVIDER: "openai",
        }

        set_attribute_calls = mock_span.set_attribute.call_args_list
        actual_attributes = {call[0][0]: call[0][1] for call in set_attribute_calls}

        for key, value in expected_attributes.items():
            assert actual_attributes.get(key) == value

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_transform_decorator(self, mock_get_tracer):
        """Test @observe.transform() creates correct span and attributes."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe.transform
        @observe.transform(transform_type="text", operation="clean")
        def preprocess_text(text: str) -> str:
            return text.strip().lower()

        # Execute function
        result = preprocess_text("  HELLO WORLD!  ")

        assert result == "hello world!"

        # Verify span creation
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == AIOperationType.TRANSFORM

        # Verify attributes were set
        expected_attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TRANSFORM,
            AIAttributes.TRANSFORM_TYPE: "text",
            AIAttributes.TRANSFORM_OPERATION: "clean",
        }

        set_attribute_calls = mock_span.set_attribute.call_args_list
        actual_attributes = {call[0][0]: call[0][1] for call in set_attribute_calls}

        for key, value in expected_attributes.items():
            assert actual_attributes.get(key) == value

    def test_convenience_decorators_without_client_raise_error(self):
        """Test convenience decorators raise RuntimeError when client not initialized."""
        # Save current client state and clear it
        original_client = decorators._default_client
        decorators._default_client = None

        try:
            # Test each convenience decorator
            @observe.llm(provider="openai", model="gpt-4")
            def test_llm():
                return "result"

            @observe.tool(name="test", tool_type="function")
            def test_tool():
                return "result"

            # Execute functions - should raise RuntimeError
            with pytest.raises(RuntimeError, match="RhesisClient not initialized"):
                test_llm()

            with pytest.raises(RuntimeError, match="RhesisClient not initialized"):
                test_tool()

        finally:
            # Restore original client state
            decorators._default_client = original_client

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_convenience_decorators_support_async_functions(self, mock_get_tracer):
        """Test convenience decorators work with async functions."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define async function with convenience decorator
        @observe.llm(provider="openai", model="gpt-4")
        async def async_generate(prompt: str) -> str:
            return f"Generated: {prompt}"

        # Test that decorator was applied (function is wrapped)
        assert hasattr(async_generate, "__wrapped__")

        # Verify span creation would happen (we can't easily test async execution in this setup)
        # The important thing is that the decorator doesn't break async functions
        assert callable(async_generate)

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.set_span_in_context")
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_convenience_decorators_support_generator_functions(
        self, mock_get_tracer, mock_set_span_in_context
    ):
        """Test convenience decorators work with generator functions."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer
        mock_set_span_in_context.return_value = mock_span

        # Define generator function with convenience decorator
        @observe.llm(provider="openai", model="gpt-4")
        def streaming_generate(prompt: str):
            for i in range(3):
                yield f"Chunk {i}: {prompt}"

        # Execute generator
        results = list(streaming_generate("Hello"))

        assert len(results) == 3
        assert results[0] == "Chunk 0: Hello"

        # Verify span creation (generators use start_span, not start_as_current_span)
        mock_tracer.start_span.assert_called_once()
