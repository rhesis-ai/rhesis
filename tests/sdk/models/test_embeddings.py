"""Tests for embedding functionality across models."""

from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.providers.litellm import LiteLLM


class TestLiteLLMEmbeddings:
    """Test embedding functionality with LiteLLM provider."""

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_embed_single_text(self, mock_embedding):
        """Test embedding a single text string."""
        # Setup mock response
        mock_response = Mock()
        mock_item = Mock()
        mock_item.embedding = [0.1, 0.2, 0.3]
        mock_response.data = [mock_item]
        mock_embedding.return_value = mock_response

        # Create model directly (bypass API key requirement)
        model = LiteLLM("openai/text-embedding-3-small", api_key="test-key")
        result = model.embed("Hello world")

        # Assertions
        assert result == [0.1, 0.2, 0.3]
        mock_embedding.assert_called_once()
        call_kwargs = mock_embedding.call_args[1]
        assert call_kwargs["model"] == "openai/text-embedding-3-small"
        assert call_kwargs["input"] == "Hello world"

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_embed_multiple_texts(self, mock_embedding):
        """Test embedding multiple text strings."""
        # Setup mock response with multiple embeddings
        mock_response = Mock()
        mock_items = [Mock(), Mock()]
        mock_items[0].embedding = [0.1, 0.2, 0.3]
        mock_items[1].embedding = [0.4, 0.5, 0.6]
        mock_response.data = mock_items
        mock_embedding.return_value = mock_response

        # Create model directly
        model = LiteLLM("openai/text-embedding-3-small", api_key="test-key")
        result = model.embed(["Hello", "world"])

        # Assertions
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]
        mock_embedding.assert_called_once()
        call_kwargs = mock_embedding.call_args[1]
        assert call_kwargs["input"] == ["Hello", "world"]

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_embed_with_dimensions(self, mock_embedding):
        """Test embedding with custom dimensions parameter."""
        # Setup mock response
        mock_response = Mock()
        mock_item = Mock()
        mock_item.embedding = [0.1, 0.2]  # 2 dimensions
        mock_response.data = [mock_item]
        mock_embedding.return_value = mock_response

        # Create model directly
        model = LiteLLM("openai/text-embedding-3-small", api_key="test-key")
        result = model.embed("Hello", dimensions=2)

        # Assertions
        assert len(result) == 2
        mock_embedding.assert_called_once()
        call_kwargs = mock_embedding.call_args[1]
        assert call_kwargs["dimensions"] == 2

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_embed_with_input_type(self, mock_embedding):
        """Test embedding with input_type parameter."""
        # Setup mock response
        mock_response = Mock()
        mock_item = Mock()
        mock_item.embedding = [0.1, 0.2, 0.3]
        mock_response.data = [mock_item]
        mock_embedding.return_value = mock_response

        # Create model directly
        model = LiteLLM("openai/text-embedding-3-small", api_key="test-key")
        model.embed("Search query", input_type="query")

        # Assertions
        mock_embedding.assert_called_once()
        call_kwargs = mock_embedding.call_args[1]
        assert call_kwargs["input_type"] == "query"

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_embed_with_vertex_ai_params(self, mock_embedding):
        """Test embedding with Vertex AI specific parameters."""
        # Setup mock response
        mock_response = Mock()
        mock_item = Mock()
        mock_item.embedding = [0.1, 0.2, 0.3]
        mock_response.data = [mock_item]
        mock_embedding.return_value = mock_response

        # Create model directly
        model = LiteLLM("vertex_ai/textembedding-gecko", api_key="test-key")
        model.embed(
            "Document text",
            task_type="RETRIEVAL_DOCUMENT",
            auto_truncate=True,
            title="Test Document",
        )

        # Assertions
        mock_embedding.assert_called_once()
        call_kwargs = mock_embedding.call_args[1]
        assert call_kwargs["task_type"] == "RETRIEVAL_DOCUMENT"
        assert call_kwargs["auto_truncate"] is True
        assert call_kwargs["title"] == "Test Document"

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_embed_error_handling(self, mock_embedding):
        """Test that embedding errors are properly handled."""
        # Setup mock to raise an exception
        mock_embedding.side_effect = Exception("API error")

        # Create model directly
        model = LiteLLM("openai/text-embedding-3-small", api_key="test-key")

        # Verify error is raised with proper message
        with pytest.raises(ValueError, match="Embedding generation failed"):
            model.embed("Hello world")

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_embed_empty_list(self, mock_embedding):
        """Test embedding an empty list."""
        # Setup mock response
        mock_response = Mock()
        mock_response.data = []
        mock_embedding.return_value = mock_response

        # Create model directly
        model = LiteLLM("openai/text-embedding-3-small", api_key="test-key")
        result = model.embed([])

        # Assertions
        assert result == []
        mock_embedding.assert_called_once()


class TestEmbeddingIntegration:
    """Integration tests for embedding with different models."""

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_openai_embedding_integration(self, mock_embedding):
        """Test OpenAI embedding integration."""
        mock_response = Mock()
        mock_item = Mock()
        mock_item.embedding = [0.1] * 1536  # OpenAI typical dimension
        mock_response.data = [mock_item]
        mock_embedding.return_value = mock_response

        model = LiteLLM("openai/text-embedding-3-small", api_key="test-key")
        result = model.embed("Test text")

        assert len(result) == 1536
        assert all(isinstance(x, float) for x in result)

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_vertex_ai_embedding_integration(self, mock_embedding):
        """Test Vertex AI embedding integration."""
        mock_response = Mock()
        mock_item = Mock()
        mock_item.embedding = [0.1] * 768  # Gecko typical dimension
        mock_response.data = [mock_item]
        mock_embedding.return_value = mock_response

        model = LiteLLM("vertex_ai/textembedding-gecko", api_key="test-key")
        result = model.embed("Test text", task_type="RETRIEVAL_QUERY")

        assert len(result) == 768
        mock_embedding.assert_called_once()
        call_kwargs = mock_embedding.call_args[1]
        assert "vertex_ai" in call_kwargs["model"]
        assert call_kwargs["task_type"] == "RETRIEVAL_QUERY"

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_batch_embedding_different_sizes(self, mock_embedding):
        """Test batch embedding with texts of different sizes."""
        mock_response = Mock()
        mock_items = [Mock(), Mock(), Mock()]
        mock_items[0].embedding = [0.1, 0.2, 0.3]
        mock_items[1].embedding = [0.4, 0.5, 0.6]
        mock_items[2].embedding = [0.7, 0.8, 0.9]
        mock_response.data = mock_items
        mock_embedding.return_value = mock_response

        model = LiteLLM("openai/text-embedding-3-small", api_key="test-key")
        texts = ["Short", "Medium length text", "A much longer text with more words and details"]
        result = model.embed(texts)

        assert len(result) == 3
        assert all(len(emb) == 3 for emb in result)
