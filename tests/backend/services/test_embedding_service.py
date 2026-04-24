"""Tests for EmbeddingService with async/sync orchestration."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import TestType
from rhesis.backend.app.models import Behavior, Category, Prompt, Test, Topic, TypeLookup
from rhesis.backend.app.models.enums import ModelType
from rhesis.backend.app.services.embedding.services import EmbeddingService


@pytest.fixture
def embedding_model(test_db: Session, test_org_id: str, authenticated_user_id: str, db_status):
    """Create an embedding model for testing."""
    from rhesis.backend.app.models.type_lookup import TypeLookup

    provider_type = (
        test_db.query(TypeLookup)
        .filter(
            TypeLookup.type_value == "openai",
            TypeLookup.organization_id == test_org_id,
        )
        .first()
    )

    if not provider_type:
        provider_type = TypeLookup(
            type_value="openai",
            type_category="provider",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(provider_type)
        test_db.commit()
        test_db.refresh(provider_type)

    model = models.Model(
        name="Test Embedding Model",
        model_name="text-embedding-3-small",
        model_type=ModelType.EMBEDDING.value,
        key="test-api-key",
        dimension=768,
        provider_type_id=provider_type.id,
        status_id=db_status.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        owner_id=authenticated_user_id,
    )
    test_db.add(model)
    test_db.commit()
    test_db.refresh(model)
    return model


@pytest.fixture
def test_entity(
    test_db: Session,
    test_org_id: str,
    authenticated_user_id: str,
    db_status,
):
    """Create a test entity that implements to_searchable_text."""

    # Create TypeLookup entries
    single_turn_type = TypeLookup(
        type_name="TestType",
        type_value=TestType.SINGLE_TURN,
        description="Single request-response test type",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(single_turn_type)
    test_db.flush()
    test_db.refresh(single_turn_type)

    # Create Topic
    topic = Topic(
        name="Test Topic",
        description="A test topic",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        status_id=db_status.id,
        entity_type_id=single_turn_type.id,
    )
    test_db.add(topic)
    test_db.flush()
    test_db.refresh(topic)

    # Create Behavior
    behavior = Behavior(
        name="Test Behavior",
        description="A test behavior",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        status_id=db_status.id,
    )
    test_db.add(behavior)
    test_db.flush()
    test_db.refresh(behavior)

    # Create Category
    category = Category(
        name="Test Category",
        description="A test category",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        status_id=db_status.id,
        entity_type_id=single_turn_type.id,
    )
    test_db.add(category)
    test_db.flush()
    test_db.refresh(category)

    prompt = Prompt(
        content="What is the capital of France?",
        expected_response="Paris",
        language_code="en-US",
        status_id=db_status.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(prompt)
    test_db.commit()
    test_db.refresh(prompt)

    test = Test(
        prompt_id=prompt.id,
        test_type_id=single_turn_type.id,
        topic_id=topic.id,
        behavior_id=behavior.id,
        category_id=category.id,
        status_id=db_status.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(test)
    test_db.flush()
    test_db.refresh(test)
    return test


@pytest.fixture
def user_with_embedding_model(
    test_db: Session, db_user, embedding_model
):
    """Create a user with embedding model configured in settings."""
    db_user.settings.update({
        "models": {
            "embedding": {"model_id": str(embedding_model.id)}
        }
    })
    test_db.commit()
    test_db.refresh(db_user)
    return db_user


@pytest.mark.unit
@pytest.mark.service
class TestEmbeddingService:
    """Test EmbeddingService async/sync orchestration."""

    def test_init(self, test_db):
        """Test service initialization."""
        service = EmbeddingService(test_db)
        assert service.db == test_db

    @patch("rhesis.backend.app.services.embedding.generator.EmbeddingGenerator")
    def test_execute_sync(
        self,
        mock_generator_class,
        test_db,
        test_entity,
        embedding_model,
        db_user,
    ):
        """Test synchronous execution."""
        mock_generator = Mock()
        mock_generator.generate.return_value = {"status": "success", "embedding_id": "test-id"}
        mock_generator_class.return_value = mock_generator

        service = EmbeddingService(test_db)
        service._execute_sync(
            str(embedding_model.id),
            entity_type="Test",
            entity_id=str(test_entity.id),
            searchable_text=test_entity.to_searchable_text(),
            user_id=str(db_user.id),
            organization_id=str(db_user.organization_id),
        )

        mock_generator.generate.assert_called_once_with(
            entity_id=str(test_entity.id),
            entity_type="Test",
            organization_id=str(db_user.organization_id),
            user_id=str(db_user.id),
            model_id=str(embedding_model.id),
            searchable_text=test_entity.to_searchable_text(),
            entity=None,
        )

    @patch("rhesis.backend.app.services.embedding.services.task_launcher")
    @patch("rhesis.backend.app.services.embedding.services.generate_embedding_task")
    def test_enqueue_async(
        self,
        mock_task,
        mock_launcher,
        test_db,
        test_entity,
        embedding_model,
        db_user,
    ):
        """Test asynchronous task enqueuing."""
        service = EmbeddingService(test_db)
        service._enqueue_async(
            str(embedding_model.id),
            entity_type="Test",
            entity_id=str(test_entity.id),
            searchable_text=test_entity.to_searchable_text(),
            user_id=str(db_user.id),
            organization_id=str(db_user.organization_id),
        )

        mock_launcher.assert_called_once()
        call_kw = mock_launcher.call_args.kwargs
        assert call_kw["entity_id"] == str(test_entity.id)
        assert call_kw["entity_type"] == "Test"
        assert call_kw["model_id"] == str(embedding_model.id)
        assert call_kw["searchable_text"] == test_entity.to_searchable_text()
        assert str(call_kw["current_user"].id) == str(db_user.id)
        assert str(call_kw["current_user"].organization_id) == str(db_user.organization_id)

    def test_resolve_model_id_explicit(self, test_db, embedding_model, authenticated_user_id):
        """Test resolving model ID when explicitly provided."""
        service = EmbeddingService(test_db)

        result = service._resolve_model_id(authenticated_user_id, str(embedding_model.id))

        assert result == str(embedding_model.id)

    def test_resolve_model_id_from_user_settings(
        self, test_db, user_with_embedding_model, embedding_model
    ):
        """Test resolving model ID from user settings."""
        service = EmbeddingService(test_db)

        result = service._resolve_model_id(str(user_with_embedding_model.id), None)

        assert result == str(embedding_model.id)

    def test_resolve_model_id_no_model_configured(self, test_db, db_user):
        """Test error when no embedding model is configured."""
        service = EmbeddingService(test_db)

        with pytest.raises(ValueError, match="No embedding model found"):
            service._resolve_model_id(str(db_user.id), None)

    def test_resolve_model_id_user_not_found(self, test_db):
        """Test error when user is not found."""
        service = EmbeddingService(test_db)

        with pytest.raises(ValueError, match="No embedding model found"):
            service._resolve_model_id("00000000-0000-0000-0000-000000000000", None)

    @patch.object(EmbeddingService, "_check_workers_available")
    @patch.object(EmbeddingService, "_execute_sync")
    @patch.object(EmbeddingService, "_enqueue_async")
    def test_enqueue_embedding_sync_fallback(
        self,
        mock_enqueue,
        mock_execute,
        mock_workers,
        test_db,
        test_entity,
        user_with_embedding_model,
    ):
        """Test enqueue_embedding with sync fallback when no workers available."""
        mock_workers.return_value = False
        mock_execute.return_value = {"status": "success"}

        test_entity.user_id = user_with_embedding_model.id
        test_db.commit()

        # Commit triggers EmbeddableMixin listeners; reset mocks to assert only this direct call:
        mock_execute.reset_mock()
        mock_enqueue.reset_mock()

        service = EmbeddingService(test_db)
        result = service.enqueue_embedding(
            entity_type="Test",
            entity_id=str(test_entity.id),
            searchable_text=test_entity.to_searchable_text(),
            user_id=str(user_with_embedding_model.id),
            organization_id=str(test_entity.organization_id),
        )

        assert result is False
        mock_execute.assert_called_once()
        mock_enqueue.assert_not_called()

    @patch.object(EmbeddingService, "_check_workers_available")
    @patch.object(EmbeddingService, "_execute_sync")
    @patch.object(EmbeddingService, "_enqueue_async")
    def test_enqueue_embedding_async_success(
        self,
        mock_enqueue,
        mock_execute,
        mock_workers,
        test_db,
        test_entity,
        user_with_embedding_model,
    ):
        """Test enqueue_embedding with async execution when workers available."""
        mock_workers.return_value = True

        test_entity.user_id = user_with_embedding_model.id
        test_db.commit()

        mock_execute.reset_mock()
        mock_enqueue.reset_mock()

        service = EmbeddingService(test_db)
        result = service.enqueue_embedding(
            entity_type="Test",
            entity_id=str(test_entity.id),
            searchable_text=test_entity.to_searchable_text(),
            user_id=str(user_with_embedding_model.id),
            organization_id=str(test_entity.organization_id),
        )

        assert result is True
        mock_enqueue.assert_called_once()
        mock_execute.assert_not_called()

    @patch.object(EmbeddingService, "_check_workers_available")
    @patch.object(EmbeddingService, "_execute_sync")
    @patch.object(EmbeddingService, "_enqueue_async")
    def test_enqueue_embedding_async_fallback_to_sync(
        self,
        mock_enqueue,
        mock_execute,
        mock_workers,
        test_db,
        test_entity,
        user_with_embedding_model,
    ):
        """Test enqueue_embedding falls back to sync when async fails."""
        mock_workers.return_value = True
        mock_enqueue.side_effect = Exception("Celery error")
        mock_execute.return_value = {"status": "success"}

        test_entity.user_id = user_with_embedding_model.id
        test_db.commit()

        mock_execute.reset_mock()
        mock_enqueue.reset_mock()

        service = EmbeddingService(test_db)
        result = service.enqueue_embedding(
            entity_type="Test",
            entity_id=str(test_entity.id),
            searchable_text=test_entity.to_searchable_text(),
            user_id=str(user_with_embedding_model.id),
            organization_id=str(test_entity.organization_id),
        )

        assert result is False
        mock_enqueue.assert_called_once()
        mock_execute.assert_called_once()

    @patch.object(EmbeddingService, "_resolve_model_id")
    @patch.object(EmbeddingService, "_check_workers_available")
    def test_enqueue_embedding_handles_exception(
        self,
        mock_workers,
        mock_resolve,
        test_db,
        test_entity,
        db_user,
    ):
        """Test enqueue_embedding handles exceptions gracefully."""
        mock_resolve.side_effect = ValueError("No model found")
        mock_workers.return_value = False

        service = EmbeddingService(test_db)
        result = service.enqueue_embedding(
            entity_type="Test",
            entity_id=str(test_entity.id),
            searchable_text=test_entity.to_searchable_text(),
            user_id=str(db_user.id),
            organization_id=str(test_entity.organization_id),
        )

        assert result is False

    @patch.object(EmbeddingService, "_check_workers_available")
    @patch.object(EmbeddingService, "_execute_sync")
    @patch.object(EmbeddingService, "_enqueue_async")
    def test_enqueue_embedding_after_test_entity_has_user_id(
        self,
        mock_enqueue,
        mock_execute,
        mock_workers,
        test_db,
        test_entity,
        user_with_embedding_model,
    ):
        """enqueue_embedding works when Test row has user_id set (listeners reset mocks)."""
        mock_workers.return_value = False
        mock_execute.return_value = {"status": "success"}

        test_entity.user_id = user_with_embedding_model.id
        test_db.commit()

        mock_execute.reset_mock()
        mock_enqueue.reset_mock()

        service = EmbeddingService(test_db)
        result = service.enqueue_embedding(
            entity_type="Test",
            entity_id=str(test_entity.id),
            searchable_text=test_entity.to_searchable_text(),
            user_id=str(user_with_embedding_model.id),
            organization_id=str(test_entity.organization_id),
        )

        assert result is False
        mock_execute.assert_called_once()


@pytest.mark.unit
@pytest.mark.service
class TestEmbeddingServiceWorkerDetection:
    """Test worker detection functionality in EmbeddingService."""

    @patch("rhesis.backend.app.services.embedding.services.EmbeddingService._worker_cache_ttl", 0)
    @patch("rhesis.backend.worker.app")
    def test_check_workers_available_with_workers(self, mock_celery_app, test_db):
        """Test worker detection when workers are available."""
        mock_inspect = Mock()
        mock_inspect.ping.return_value = {"worker1": {"ok": "pong"}}
        mock_celery_app.control.inspect.return_value = mock_inspect

        service = EmbeddingService(test_db)
        result = service._check_workers_available()

        assert result is True

    @patch("rhesis.backend.app.services.embedding.services.EmbeddingService._worker_cache_ttl", 0)
    @patch("rhesis.backend.worker.app")
    def test_check_workers_available_no_workers(self, mock_celery_app, test_db):
        """Test worker detection when no workers are available."""
        mock_inspect = Mock()
        mock_inspect.ping.return_value = None
        mock_celery_app.control.inspect.return_value = mock_inspect

        service = EmbeddingService(test_db)
        result = service._check_workers_available()

        assert result is False

    @patch("rhesis.backend.app.services.embedding.services.EmbeddingService._worker_cache_ttl", 0)
    @patch("rhesis.backend.worker.app")
    def test_check_workers_available_exception(self, mock_celery_app, test_db):
        """Test worker detection handles exceptions gracefully."""
        mock_celery_app.control.inspect.side_effect = Exception("Connection error")

        service = EmbeddingService(test_db)
        result = service._check_workers_available()

        assert result is False

    @patch("rhesis.backend.worker.app")
    def test_check_workers_available_caching(self, mock_celery_app, test_db):
        """Test that worker availability is cached."""
        mock_inspect = Mock()
        mock_inspect.ping.return_value = {"worker1": {"ok": "pong"}}
        mock_celery_app.control.inspect.return_value = mock_inspect

        service = EmbeddingService(test_db)
        # Clear cache before testing caching functionality
        if "checked_at" in EmbeddingService._worker_cache:
            EmbeddingService._worker_cache["checked_at"] = 0
            EmbeddingService._worker_cache["available"] = None

        result1 = service._check_workers_available()
        result2 = service._check_workers_available()

        assert result1 is True
        assert result2 is True
        assert mock_celery_app.control.inspect.call_count == 1


@pytest.mark.unit
@pytest.mark.service
class TestEmbeddingServiceIntegration:
    """Integration tests for EmbeddingService with real generator."""

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    @patch.object(EmbeddingService, "_check_workers_available")
    def test_full_sync_flow(
        self,
        mock_workers,
        mock_get_model,
        test_db,
        test_entity,
        user_with_embedding_model,
    ):
        """Test complete sync flow with real generator."""
        mock_workers.return_value = False

        mock_embedder = Mock()
        mock_embedder.generate.return_value = [0.1] * 768
        mock_get_model.return_value = mock_embedder

        test_entity.user_id = user_with_embedding_model.id
        test_db.commit()

        service = EmbeddingService(test_db)
        result = service.enqueue_embedding(
            entity_type="Test",
            entity_id=str(test_entity.id),
            searchable_text=test_entity.to_searchable_text(),
            user_id=str(user_with_embedding_model.id),
            organization_id=str(test_entity.organization_id),
        )

        assert result is False

        embeddings = (
            test_db.query(models.Embedding)
            .filter_by(entity_id=str(test_entity.id), entity_type="Test")
            .all()
        )
        assert len(embeddings) == 1
        assert embeddings[0].dimension == 768
        assert len(embeddings[0].embedding) == 768
