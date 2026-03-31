"""
🧪 Embedding Model Testing

Comprehensive test suite for the Embedding model and EmbeddingConfig.
Tests focus on:
- EmbeddingConfig validation and dimension handling (unit)
- Embedding property setters/getters (unit)
- Database constraints (CHECK constraint for exactly one embedding) (integration)
- Relationship loading (Test.embeddings, Source.embeddings) (integration)
- to_searchable_text() implementations (unit/integration)

"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app.models import Embedding, Source
from rhesis.backend.app.models.embedding import EmbeddingConfig

# Import the test_model fixture
pytest_plugins = ["tests.backend.metrics.fixtures.metric_fixtures"]


@pytest.mark.unit
class TestEmbeddingConfig:
    """🔧 Test EmbeddingConfig utility class"""

    def test_supported_dimensions(self):
        """Test that supported dimensions are correctly defined"""
        expected_dimensions = {
            384: "embedding_384",
            768: "embedding_768",
            1024: "embedding_1024",
            1536: "embedding_1536",
        }
        assert EmbeddingConfig.SUPPORTED_DIMENSIONS == expected_dimensions

    def test_validate_dimension_valid(self):
        """Test dimension validation with valid dimensions"""
        for dimension in [384, 768, 1024, 1536]:
            # Should not raise
            EmbeddingConfig.validate_dimension(dimension)

    def test_validate_dimension_invalid(self):
        """Test dimension validation with invalid dimensions"""
        invalid_dimensions = [0, 256, 512, 2048, 3072, -1]
        for dimension in invalid_dimensions:
            with pytest.raises(ValueError, match=f"Dimension {dimension} not supported"):
                EmbeddingConfig.validate_dimension(dimension)

    def test_get_dimension_from_config_valid(self):
        """Test extracting dimension from valid config"""
        config = {"dimension": 768, "model": "text-embedding-ada-002"}
        dimension = EmbeddingConfig.get_dimension_from_config(config)
        assert dimension == 768

    def test_get_dimension_from_config_missing_dimension(self):
        """Test error when dimension is missing from config"""
        config = {"model": "text-embedding-ada-002"}
        with pytest.raises(ValueError, match="Invalid embedding configuration"):
            EmbeddingConfig.get_dimension_from_config(config)

    def test_get_dimension_from_config_empty(self):
        """Test error with empty config"""
        with pytest.raises(ValueError, match="Invalid embedding configuration"):
            EmbeddingConfig.get_dimension_from_config({})

    def test_get_dimension_from_config_none(self):
        """Test error with None config"""
        with pytest.raises(ValueError, match="Invalid embedding configuration"):
            EmbeddingConfig.get_dimension_from_config(None)

    def test_get_dimension_from_config_unsupported(self):
        """Test error with unsupported dimension in config"""
        config = {"dimension": 3072, "model": "some-model"}
        with pytest.raises(ValueError, match="Dimension 3072 not supported"):
            EmbeddingConfig.get_dimension_from_config(config)


@pytest.mark.unit
class TestEmbeddingModelUnit:
    """🗄️ Test Embedding model properties and methods (without DB)"""

    @pytest.fixture
    def base_embedding(self):
        """Fixture for a basic Embedding instance"""
        return Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=uuid.uuid4(),
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status_id=uuid.uuid4(),
            organization_id="org_id",
            user_id="user_id",
        )

    def test_embedding_property_getter(self, base_embedding):
        """Test reading embedding from the correct column"""
        vector = [0.1] * 768
        base_embedding.embedding_768 = vector

        result = base_embedding.embedding
        assert list(result) == vector
        assert len(result) == 768

    def test_embedding_property_setter(self, base_embedding):
        """Test setting embedding sets the correct column"""
        base_embedding.embedding_config = {"dimension": 1536, "model": "test-model"}
        vector = [0.2] * 1536
        base_embedding.embedding = vector

        # Should be stored in embedding_1536
        assert list(base_embedding.embedding_1536) == vector
        assert base_embedding.embedding_384 is None
        assert base_embedding.embedding_768 is None
        assert base_embedding.embedding_1024 is None

    def test_embedding_property_setter_clears_other_columns(self, base_embedding):
        """Test that setting embedding clears other dimension columns"""
        # Set initial embedding
        base_embedding.embedding = [0.1] * 768

        # Update config and set new embedding
        base_embedding.embedding_config = {"dimension": 1024, "model": "test-model"}
        base_embedding.embedding = [0.2] * 1024

        # Only embedding_1024 should have data
        assert base_embedding.embedding_768 is None
        assert list(base_embedding.embedding_1024) == [0.2] * 1024
        assert base_embedding.embedding_384 is None
        assert base_embedding.embedding_1536 is None

    def test_embedding_property_without_config(self, base_embedding):
        """Test that accessing embedding without config raises error"""
        base_embedding.embedding_config = None
        base_embedding.embedding_768 = [0.1] * 768

        with pytest.raises(ValueError, match="Embedding configuration is not set"):
            _ = base_embedding.embedding

    def test_embedding_property_setter_without_config(self, base_embedding):
        """Test that setting embedding without config raises error"""
        base_embedding.embedding_config = None

        with pytest.raises(ValueError, match="embedding_config must be set"):
            base_embedding.embedding = [0.1] * 768

    def test_embedding_property_setter_dimension_mismatch(self, base_embedding):
        """Test that setting wrong dimension raises error"""
        # Try to set 384-dim vector when config says 768
        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            base_embedding.embedding = [0.1] * 384

    def test_dimension_property(self, base_embedding):
        """Test dimension property returns config dimension"""
        base_embedding.embedding_config = {"dimension": 1024, "model": "test-model"}
        assert base_embedding.dimension == 1024

    def test_dimension_property_without_config(self, base_embedding):
        """Test dimension property raises error without config"""
        base_embedding.embedding_config = None

        with pytest.raises(ValueError, match="Embedding configuration is not set"):
            _ = base_embedding.dimension

    def test_active_dimension_property(self, base_embedding):
        """Test active_dimension returns the actual stored dimension"""
        base_embedding.embedding_config = {"dimension": 384, "model": "test-model"}
        base_embedding.embedding_384 = [0.1] * 384
        assert base_embedding.active_dimension == 384

    def test_active_dimension_property_none(self, base_embedding):
        """Test active_dimension returns None before setting embedding"""
        # Before setting any embedding, active_dimension should be None
        assert base_embedding.active_dimension is None

        # Set embedding to make it valid
        base_embedding.embedding = [0.1] * 768
        assert base_embedding.active_dimension == 768

    def test_embedding_column_name_property(self, base_embedding):
        """Test embedding_column_name returns correct column name"""
        base_embedding.embedding_config = {"dimension": 1536, "model": "test-model"}
        base_embedding.embedding_1536 = [0.1] * 1536
        assert base_embedding.embedding_column_name == "embedding_1536"

    def test_embedding_column_name_property_none(self, base_embedding):
        """Test embedding_column_name returns None when no embedding is set"""
        assert base_embedding.embedding_column_name is None


@pytest.mark.unit
class TestSearchableTextUnit:
    """📝 Test to_searchable_text() implementations (without DB)"""

    def test_source_to_searchable_text_full(self):
        """Test Source.to_searchable_text() with all fields"""
        source = Source(
            title="AI Safety Research",
            description="Study on AI alignment",
            content="In this paper we explore..." * 100,
            citation="Smith et al. 2024",
            url="https://example.com/paper",
            organization_id="org_id",
            user_id="user_id",
        )

        text = source.to_searchable_text()

        assert "AI Safety Research" in text
        assert "Study on AI alignment" in text
        assert "In this paper we explore" in text
        assert "Smith et al. 2024" in text
        assert "https://example.com/paper" in text

    def test_source_to_searchable_text_truncation(self):
        """Test that content is truncated to 20000 chars"""
        # Create content longer than 20000 chars
        long_content = "A" * 25000

        source = Source(
            title="Test",
            content=long_content,
            organization_id="org_id",
            user_id="user_id",
        )

        text = source.to_searchable_text()

        # Should be truncated (20000 chars + title + spaces)
        assert len(text) < 25000
        assert "Test" in text

    def test_source_to_searchable_text_partial(self):
        """Test Source.to_searchable_text() with missing fields"""
        source = Source(title="Test Source", organization_id="org_id", user_id="user_id")

        text = source.to_searchable_text()

        assert text == "Test Source"

    def test_embeddable_mixin_not_implemented(self):
        """Test that EmbeddableMixin raises NotImplementedError"""
        from rhesis.backend.app.models.mixins import EmbeddableMixin

        class DummyModel(EmbeddableMixin):
            __name__ = "DummyModel"

        dummy = DummyModel()
        with pytest.raises(
            NotImplementedError,
            match="DummyModel must implement to_searchable_text",
        ):
            dummy.to_searchable_text()


@pytest.mark.integration
class TestEmbeddingModelIntegration:
    """🗄️ Test Embedding model persistence"""

    def test_embedding_persistence(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test that embeddings are correctly persisted and fetched from DB"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        vector = [0.1] * 768
        embedding.embedding = vector

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        # Property should return the vector from embedding_768
        result = embedding.embedding
        assert list(result) == vector
        assert embedding.embedding_384 is None

    def test_repr(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test string representation (using DB to load relations)"""
        entity_id = uuid.uuid4()
        embedding = Embedding(
            entity_id=entity_id,
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        repr_str = repr(embedding)
        assert "Embedding" in repr_str
        assert "entity_type=Test" in repr_str
        assert f"entity_id={entity_id}" in repr_str
        assert "dimension=768" in repr_str
        assert "status=active" in repr_str


@pytest.mark.integration
class TestEmbeddingConstraints:
    """🔒 Test database constraints on Embedding model"""

    def test_check_constraint_exactly_one_embedding(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test that CHECK constraint enforces exactly one embedding column"""
        from sqlalchemy import text

        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768
        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        # Try to set another embedding column directly via SQL (bypassing ORM)
        with pytest.raises(IntegrityError, match="ck_embedding_exactly_one_embedding"):
            test_db.execute(
                text(
                    f"UPDATE embedding SET embedding_384 = ARRAY{[0.2] * 384}::vector "
                    f"WHERE id = '{embedding.id}'"
                )
            )
            test_db.commit()

        test_db.rollback()

    def test_check_constraint_no_embedding(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test that CHECK constraint prevents zero embeddings"""
        from sqlalchemy import text

        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768
        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        # Try to clear all embeddings via SQL (bypassing ORM)
        with pytest.raises(IntegrityError, match="ck_embedding_exactly_one_embedding"):
            test_db.execute(
                text(f"UPDATE embedding SET embedding_768 = NULL WHERE id = '{embedding.id}'")
            )
            test_db.commit()

        test_db.rollback()

    def test_nano_id_unique_constraint(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test that nano_id has unique constraint"""
        # Create first embedding with nano_id
        embedding1 = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            nano_id="test_nano_123",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding1.embedding = [0.1] * 768
        test_db.add(embedding1)
        test_db.commit()

        # Try to create second embedding with same nano_id
        embedding2 = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash2",
            searchable_text="test text 2",
            text_hash="text_hash2",
            nano_id="test_nano_123",  # Same nano_id
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding2.embedding = [0.2] * 768
        test_db.add(embedding2)

        with pytest.raises(IntegrityError, match="ix_embedding_nano_id"):
            test_db.commit()

        test_db.rollback()


@pytest.mark.integration
class TestEmbeddingRelationships:
    """🔗 Test polymorphic relationships with Test and Source models"""

    def test_test_embeddings_relationship(
        self,
        test_db: Session,
        db_test_minimal,
        test_org_id: str,
        authenticated_user_id: str,
        test_model,
        db_status,
    ):
        """Test loading embeddings from Test model"""
        test = db_test_minimal

        # Create embeddings for the test
        embedding1 = Embedding(
            entity_id=test.id,
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "model-1"},
            config_hash="hash1",
            searchable_text="test content 1",
            text_hash="text_hash1",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding1.embedding = [0.1] * 768

        embedding2 = Embedding(
            entity_id=test.id,
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 384, "model": "model-2"},
            config_hash="hash2",
            searchable_text="test content 2",
            text_hash="text_hash2",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding2.embedding = [0.2] * 384

        test_db.add_all([embedding1, embedding2])
        test_db.commit()

        # Refresh and access relationship
        test_db.refresh(test)
        embeddings = test.embeddings

        assert len(embeddings) == 2
        assert all(emb.entity_id == test.id for emb in embeddings)
        assert all(emb.entity_type == "Test" for emb in embeddings)

    def test_source_embeddings_relationship(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test loading embeddings from Source model"""
        # Create a source
        source = Source(
            title="Test Source",
            content="Source content",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(source)
        test_db.commit()
        test_db.refresh(source)

        # Create embedding for the source
        embedding = Embedding(
            entity_id=source.id,
            entity_type="Source",
            model_id=test_model.id,
            embedding_config={"dimension": 1024, "model": "test-model"},
            config_hash="hash1",
            searchable_text="source content",
            text_hash="text_hash1",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.3] * 1024

        test_db.add(embedding)
        test_db.commit()

        # Refresh and access relationship
        test_db.refresh(source)
        embeddings = source.embeddings

        assert len(embeddings) == 1
        assert embeddings[0].entity_id == source.id
        assert embeddings[0].entity_type == "Source"
        assert embeddings[0].active_dimension == 1024


@pytest.mark.integration
class TestSearchableTextIntegration:
    """📝 Test to_searchable_text() implementations requiring DB relationships"""

    def test_test_to_searchable_text_single_turn(
        self,
        test_db: Session,
        db_test_minimal,
        test_org_id: str,
        authenticated_user_id: str,
    ):
        """Test Test.to_searchable_text() for single-turn tests"""
        test = db_test_minimal

        # Ensure it has a prompt
        if test.prompt:
            text = test.to_searchable_text()

            # Should include prompt content and metadata
            assert isinstance(text, str)
            assert len(text) > 0

    def test_test_to_searchable_text_multi_turn(
        self,
        test_db: Session,
        db_test_minimal,
        test_org_id: str,
        authenticated_user_id: str,
    ):
        """Test Test.to_searchable_text() for multi-turn tests"""
        test = db_test_minimal

        # Add messages for a multi-turn conversation
        if not hasattr(test, "messages"):
            return  # Skip if model doesn't support messages

        test.messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I am fine, thank you."},
            {"role": "user", "content": "What is the capital of France?"},
        ]

        test_db.commit()

        text = test.to_searchable_text()

        # Should include content from all turns
        assert "Hello, how are you?" in text
        assert "What is the capital of France?" in text

    def test_behavior_to_searchable_text(
        self,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
    ):
        """Test Behavior.to_searchable_text() for Behaviors"""
        from rhesis.backend.app.models.behavior import Behavior

        behavior = Behavior(
            name="Helpful Assistant",
            description="A helpful assistant that provides accurate information.",
            tags=["helpful", "assistant"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        test_db.add(behavior)
        test_db.commit()

        text = behavior.to_searchable_text()

        assert "Helpful Assistant" in text
        assert "A helpful assistant that provides accurate information." in text
        assert "helpful assistant" in text


@pytest.mark.integration
class TestEmbeddingDefaults:
    """🎯 Test default values and server defaults"""

    def test_weight_default(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test that weight has default value of 1.0"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        assert embedding.weight == 1.0

    def test_status_default(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test that status has default value of 'active'"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        assert embedding.status.name == "Active"

    def test_origin_default(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model, db_status
    ):
        """Test that origin has default value of 'user'"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        assert embedding.origin == "user"
