"""Tests for EmbeddingGenerator service."""

import hashlib
import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.enums import EmbeddingStatus, ModelType
from rhesis.backend.app.services.embedding.generator import EmbeddingGenerator


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
    from rhesis.backend.app.models import Behavior, Category, Prompt, Test, TypeLookup, Topic
    from rhesis.backend.app.constants import TestType

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


@pytest.mark.unit
@pytest.mark.service
class TestEmbeddingGenerator:
    """Test EmbeddingGenerator functionality."""

    def test_compute_hash_string(self, test_db):
        """Test computing hash of a string."""
        generator = EmbeddingGenerator(test_db)
        text = "Hello, world!"
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        result = generator._compute_hash(text)

        assert result == expected_hash

    def test_compute_hash_dict(self, test_db):
        """Test computing hash of a dictionary."""
        generator = EmbeddingGenerator(test_db)
        data = {"model": "text-embedding-3-small", "dimension": 768}
        expected_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode("utf-8")
        ).hexdigest()

        result = generator._compute_hash(data)

        assert result == expected_hash

    def test_compute_hash_dict_deterministic(self, test_db):
        """Test that hash is deterministic regardless of key order."""
        generator = EmbeddingGenerator(test_db)
        data1 = {"a": 1, "b": 2, "c": 3}
        data2 = {"c": 3, "a": 1, "b": 2}

        hash1 = generator._compute_hash(data1)
        hash2 = generator._compute_hash(data2)

        assert hash1 == hash2

    def test_get_entity_success(
        self, test_db, test_entity, test_org_id, authenticated_user_id
    ):
        """Test successfully retrieving an entity."""
        generator = EmbeddingGenerator(test_db)

        result = generator._get_entity(str(test_entity.id), "Test", test_org_id)

        assert result.id == test_entity.id
        assert isinstance(result, models.Test)

    def test_get_entity_not_found(self, test_db, test_org_id):
        """Test error when entity is not found."""
        generator = EmbeddingGenerator(test_db)

        with pytest.raises(ValueError, match="Entity not found"):
            generator._get_entity("00000000-0000-0000-0000-000000000000", "Test", test_org_id)

    def test_get_entity_invalid_type(self, test_db, test_org_id):
        """Test error when entity type doesn't exist."""
        generator = EmbeddingGenerator(test_db)

        with pytest.raises(ValueError, match="Entity type InvalidType not found"):
            generator._get_entity(
                "00000000-0000-0000-0000-000000000000", "InvalidType", test_org_id
            )

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    def test_generate_embedding_vector_success(self, mock_get_model, test_db):
        """Test successful embedding vector generation."""
        generator = EmbeddingGenerator(test_db)

        mock_embedder = Mock()
        mock_embedder.generate.return_value = [0.1] * 768
        mock_get_model.return_value = mock_embedder

        result = generator._generate_embedding_vector(
            searchable_text="Test text",
            provider="openai",
            model_name="text-embedding-3-small",
            api_key="test-key",
            dimension=768,
        )

        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)
        mock_embedder.generate.assert_called_once_with("Test text")

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    def test_generate_embedding_vector_model_creation_error(self, mock_get_model, test_db):
        """Test error when embedding model creation fails."""
        generator = EmbeddingGenerator(test_db)
        mock_get_model.side_effect = ValueError("Invalid provider")

        with pytest.raises(ValueError, match="Failed to create embedder"):
            generator._generate_embedding_vector(
                searchable_text="Test text",
                provider="invalid",
                model_name="test-model",
                api_key="test-key",
                dimension=768,
            )

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    def test_generate_embedding_vector_generation_error(self, mock_get_model, test_db):
        """Test error when embedding generation fails."""
        generator = EmbeddingGenerator(test_db)

        mock_embedder = Mock()
        mock_embedder.generate.side_effect = Exception("API error")
        mock_get_model.return_value = mock_embedder

        with pytest.raises(ValueError, match="Failed to generate embedding"):
            generator._generate_embedding_vector(
                searchable_text="Test text",
                provider="openai",
                model_name="text-embedding-3-small",
                api_key="test-key",
                dimension=768,
            )

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    def test_generate_creates_new_embedding(
        self,
        mock_get_model,
        test_db,
        test_entity,
        embedding_model,
        test_org_id,
        authenticated_user_id,
    ):
        """Test generating a new embedding."""
        generator = EmbeddingGenerator(test_db)

        mock_embedder = Mock()
        mock_embedder.generate.return_value = [0.1] * 768
        mock_get_model.return_value = mock_embedder

        result = generator.generate(
            entity_id=str(test_entity.id),
            entity_type="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            model_id=str(embedding_model.id),
        )

        assert result["status"] == "success"
        assert "embedding_id" in result

        embedding = test_db.query(models.Embedding).filter_by(id=result["embedding_id"]).first()
        assert embedding is not None
        assert str(embedding.entity_id) == str(test_entity.id)
        assert embedding.entity_type == "Test"
        assert embedding.status.name.lower() == EmbeddingStatus.ACTIVE.value.lower()
        assert embedding.dimension == 768
        assert len(embedding.embedding) == 768

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    def test_generate_with_entity_provided(
        self,
        mock_get_model,
        test_db,
        test_entity,
        embedding_model,
        test_org_id,
        authenticated_user_id,
    ):
        """Test generating embedding with entity object provided."""
        generator = EmbeddingGenerator(test_db)

        mock_embedder = Mock()
        mock_embedder.generate.return_value = [0.1] * 768
        mock_get_model.return_value = mock_embedder

        result = generator.generate(
            entity_id=str(test_entity.id),
            entity_type="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            model_id=str(embedding_model.id),
            entity=test_entity,
        )

        assert result["status"] == "success"
        assert "embedding_id" in result

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    def test_generate_returns_existing_embedding(
        self,
        mock_get_model,
        test_db,
        test_entity,
        embedding_model,
        test_org_id,
        authenticated_user_id,
    ):
        """Test that existing embedding is returned if hash matches."""
        generator = EmbeddingGenerator(test_db)

        mock_embedder = Mock()
        mock_embedder.generate.return_value = [0.1] * 768
        mock_get_model.return_value = mock_embedder

        result1 = generator.generate(
            entity_id=str(test_entity.id),
            entity_type="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            model_id=str(embedding_model.id),
        )

        result2 = generator.generate(
            entity_id=str(test_entity.id),
            entity_type="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            model_id=str(embedding_model.id),
        )

        assert result1["embedding_id"] == result2["embedding_id"]
        assert mock_embedder.generate.call_count == 1

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    def test_generate_marks_old_embeddings_stale(
        self,
        mock_get_model,
        test_db,
        test_entity,
        embedding_model,
        test_org_id,
        authenticated_user_id,
    ):
        """Test that old embeddings are marked as stale when content changes."""
        generator = EmbeddingGenerator(test_db)

        mock_embedder = Mock()
        mock_embedder.generate.return_value = [0.1] * 768
        mock_get_model.return_value = mock_embedder

        result1 = generator.generate(
            entity_id=str(test_entity.id),
            entity_type="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            model_id=str(embedding_model.id),
        )

        test_entity.prompt.content = "What is the capital of Spain?"
        test_db.commit()
        test_db.refresh(test_entity)

        result2 = generator.generate(
            entity_id=str(test_entity.id),
            entity_type="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            model_id=str(embedding_model.id),
        )

        assert result1["embedding_id"] != result2["embedding_id"]

        old_embedding = test_db.query(models.Embedding).filter_by(
            id=result1["embedding_id"]
        ).first()
        assert old_embedding.status.name.lower() == EmbeddingStatus.STALE.value.lower()

        new_embedding = test_db.query(models.Embedding).filter_by(
            id=result2["embedding_id"]
        ).first()
        assert new_embedding.status.name.lower() == EmbeddingStatus.ACTIVE.value.lower()

    def test_generate_entity_without_to_searchable_text(
        self, test_db, test_org_id, authenticated_user_id, embedding_model, db_status
    ):
        """Test error when entity doesn't support embedding."""
        import uuid
        user = models.User(
            name="Test User",
            email=f"test_{uuid.uuid4()}@example.com",
            organization_id=test_org_id,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        generator = EmbeddingGenerator(test_db)

        with pytest.raises(ValueError, match="does not support embedding"):
            generator.generate(
                entity_id=str(user.id),
                entity_type="User",
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                model_id=str(embedding_model.id),
            )

    def test_generate_model_not_found(
        self, test_db, test_entity, test_org_id, authenticated_user_id
    ):
        """Test error when model is not found."""
        generator = EmbeddingGenerator(test_db)

        with pytest.raises(ValueError, match="Model not found"):
            generator.generate(
                entity_id=str(test_entity.id),
                entity_type="Test",
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                model_id="00000000-0000-0000-0000-000000000000",
            )

    @patch("rhesis.sdk.models.factory.get_embedding_model")
    def test_generate_different_dimensions(
        self,
        mock_get_model,
        test_db,
        test_entity,
        test_org_id,
        authenticated_user_id,
        db_status,
    ):
        """Test generating embeddings with different dimensions."""
        from rhesis.backend.app.models.type_lookup import TypeLookup

        provider_type = (
            test_db.query(TypeLookup)
            .filter(
                TypeLookup.type_value == "openai",
                TypeLookup.organization_id == test_org_id,
            )
            .first()
        )

        dimensions_to_test = [384, 768, 1024, 1536]

        for dim in dimensions_to_test:
            model = models.Model(
                name=f"Test Model {dim}",
                model_name="test-model",
                model_type=ModelType.EMBEDDING.value,
                key="test-key",
                dimension=dim,
                provider_type_id=provider_type.id,
                status_id=db_status.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                owner_id=authenticated_user_id,
            )
            test_db.add(model)
            test_db.commit()
            test_db.refresh(model)

            mock_embedder = Mock()
            mock_embedder.generate.return_value = [0.1] * dim
            mock_get_model.return_value = mock_embedder

            generator = EmbeddingGenerator(test_db)
            result = generator.generate(
                entity_id=str(test_entity.id),
                entity_type="Test",
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                model_id=str(model.id),
            )

            embedding = test_db.query(models.Embedding).filter_by(
                id=result["embedding_id"]
            ).first()
            assert embedding.dimension == dim
            assert len(embedding.embedding) == dim
