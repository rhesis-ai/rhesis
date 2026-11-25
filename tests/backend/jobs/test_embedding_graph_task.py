"""Tests for embedding graph Celery helpers."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.jobs.embedding import generate_embedding_task
from rhesis.backend.jobs.embedding.graph import (
    _ensure_embeddings_for_entities,
    compute_source_graph_task,
    compute_test_set_graph_task,
)


@pytest.mark.unit
class TestEnsureEmbeddingsForEntities:
    def test_skips_when_all_entities_already_embedded(self):
        entity_id = uuid.uuid4()
        user = MagicMock(organization_id=uuid.uuid4(), id=uuid.uuid4())

        with patch(
            "rhesis.backend.app.services.embedding.graph_builder.fetch_embeddings",
            return_value=[MagicMock(entity_id=entity_id)],
        ):
            with patch(
                "rhesis.backend.app.services.embedding.services.EmbeddingService"
            ) as mock_service:
                _ensure_embeddings_for_entities(
                    MagicMock(),
                    entity_ids=[entity_id],
                    user=user,
                    embedded_entity="Test",
                )
                mock_service.assert_not_called()

    @patch("rhesis.backend.app.services.embedding.generator.EmbeddingGenerator")
    @patch("rhesis.backend.app.services.embedding.services.EmbeddingService")
    @patch("rhesis.backend.app.services.embedding.graph_builder.fetch_embeddings")
    def test_generates_missing_embeddings(self, mock_fetch, mock_service_cls, mock_generator_cls):
        missing_id = uuid.uuid4()
        existing_id = uuid.uuid4()
        user = MagicMock(organization_id=uuid.uuid4(), id=uuid.uuid4())

        mock_fetch.return_value = [MagicMock(entity_id=existing_id)]
        mock_service_cls.return_value.resolve_model_id.return_value = "model-1"

        mock_generator = mock_generator_cls.return_value
        mock_generator.generate.return_value = {
            "status": "success",
            "embedding_id": str(uuid.uuid4()),
        }

        _ensure_embeddings_for_entities(
            MagicMock(),
            entity_ids=[existing_id, missing_id],
            user=user,
            embedded_entity="Test",
        )

        mock_generator.generate.assert_called_once_with(
            entity_id=str(missing_id),
            entity_type="Test",
            organization_id=str(user.organization_id),
            user_id=str(user.id),
            model_id="model-1",
        )

    @patch("rhesis.backend.app.services.embedding.services.EmbeddingService")
    @patch("rhesis.backend.app.services.embedding.graph_builder.fetch_embeddings")
    def test_skips_backfill_when_no_embedding_model(self, mock_fetch, mock_service_cls):
        entity_id = uuid.uuid4()
        user = MagicMock(organization_id=uuid.uuid4(), id=uuid.uuid4())

        mock_fetch.return_value = []
        mock_service_cls.return_value.resolve_model_id.side_effect = ValueError(
            "No embedding model"
        )

        with patch(
            "rhesis.backend.app.services.embedding.generator.EmbeddingGenerator"
        ) as mock_generator_cls:
            _ensure_embeddings_for_entities(
                MagicMock(),
                entity_ids=[entity_id],
                user=user,
                embedded_entity="Test",
            )
            mock_generator_cls.assert_not_called()


@pytest.mark.unit
class TestEmbeddingJobsWhenDisabled:
    """Jobs queued before embeddings were switched off do nothing."""

    @pytest.fixture(autouse=True)
    def _embeddings_off(self, monkeypatch):
        monkeypatch.setattr(get_application_settings(), "embeddings_enabled", False)

    def test_generate_embedding_skips(self):
        with patch(
            "rhesis.backend.app.services.embedding.generator.EmbeddingGenerator"
        ) as generator:
            result = generate_embedding_task.run(entity_id=str(uuid.uuid4()), entity_type="Test")

        assert result["status"] == "skipped_disabled"
        generator.assert_not_called()

    @pytest.mark.parametrize(
        "task, runner",
        [
            (compute_test_set_graph_task, "_run_test_set_embedding_graph"),
            (compute_source_graph_task, "_run_source_embedding_graph"),
        ],
    )
    def test_graph_tasks_skip(self, task, runner):
        with patch(f"rhesis.backend.jobs.embedding.graph.{runner}") as run:
            task.run(str(uuid.uuid4()), str(uuid.uuid4()))

        run.assert_not_called()
