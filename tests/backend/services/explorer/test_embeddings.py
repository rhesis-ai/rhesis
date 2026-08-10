"""Tests for explorer embedding resolution."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.explorer.embeddings import resolve_embedder
from rhesis.backend.app.utils.model_errors import ModelConfigurationError


@pytest.mark.unit
class TestResolveEmbedder:
    def test_user_not_found_raises(self, test_db: Session):
        with pytest.raises(ValueError, match="User not found"):
            resolve_embedder(test_db, "00000000-0000-0000-0000-000000000000")

    @patch("rhesis.backend.app.services.explorer.embeddings.get_user_embedding_model")
    def test_recursive_native_provider_fails_before_any_network_call(
        self,
        mock_get_user_embedding_model,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
    ):
        """DEFAULT_EMBEDDING_MODEL misconfigured back to the Rhesis native
        provider must fail in-process, not via a doomed HTTP round-trip to
        this backend's own /services/generate/embedding endpoint.

        Same latent recursion as EmbeddingGenerator._resolve_embedder
        (apps/backend/.../services/embedding/generator.py), just reached from
        the explorer suggestions/test-embedding paths instead of the Celery
        embedding task.
        """
        from rhesis.sdk.models.providers.native import RhesisEmbedder

        # isinstance() against a Mock(spec=...) succeeds, so this stands in for
        # a real RhesisEmbedder without needing RHESIS_API_KEY configured.
        fake_native_embedder = Mock(spec=RhesisEmbedder)
        mock_get_user_embedding_model.return_value = fake_native_embedder

        with pytest.raises(ModelConfigurationError, match="recursively"):
            resolve_embedder(test_db, authenticated_user_id)

        fake_native_embedder.generate.assert_not_called()

    @patch("rhesis.backend.app.services.explorer.embeddings.get_model")
    @patch("rhesis.backend.app.services.explorer.embeddings.get_user_embedding_model")
    def test_ordinary_provider_string_is_resolved_normally(
        self,
        mock_get_user_embedding_model,
        mock_get_model,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
    ):
        """A correctly configured provider still resolves — the recursion
        guard must not fire on an unrelated embedder type."""
        mock_get_user_embedding_model.return_value = "vertex_ai/text-embedding-005"
        mock_embedder = Mock()
        mock_get_model.return_value = mock_embedder

        result = resolve_embedder(test_db, authenticated_user_id)

        assert result is mock_embedder
        mock_get_model.assert_called_once_with(
            "vertex_ai/text-embedding-005", model_type="embedding", dimensions=768
        )
