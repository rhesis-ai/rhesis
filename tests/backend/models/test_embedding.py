"""
🧪 Embedding Model Testing

Comprehensive test suite for the Embedding model and EmbeddingConfig.
Tests focus on:
- EmbeddingConfig validation and dimension handling
- Embedding property setters/getters
- Database constraints (CHECK constraint for exactly one embedding)
- Relationship loading (Test.embeddings, Source.embeddings)
- to_searchable_text() implementations

"""

import uuid
from typing import List

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app.models import Embedding, Source, Test
from rhesis.backend.app.models.embedding import EmbeddingConfig

# Import the test_model fixture
pytest_plugins = ["tests.backend.metrics.fixtures.metric_fixtures"]


@pytest.mark.unit
class TestEmbeddingConfig:
    """🔧 Test EmbeddingConfig utility class"""

    def test_supported_dimensions(self):
        """Test that supported dimensions are correctly defined"""
        expected_dimensions = {384: "embedding_384", 768: "embedding_768", 1024: "embedding_1024", 1536: "embedding_1536"}
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
class TestEmbeddingModel:
    """🗄️ Test Embedding model properties and methods"""

    def test_embedding_property_getter(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test reading embedding from the correct column"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        vector = [0.1] * 768
        embedding.embedding_768 = vector

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        # Property should return the vector from embedding_768
        assert embedding.embedding == vector
        assert len(embedding.embedding) == 768

    def test_embedding_property_setter(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test setting embedding sets the correct column"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 1536, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        vector = [0.2] * 1536
        embedding.embedding = vector

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        # Should be stored in embedding_1536
        assert embedding.embedding_1536 == vector
        assert embedding.embedding_384 is None
        assert embedding.embedding_768 is None
        assert embedding.embedding_1024 is None

    def test_embedding_property_setter_clears_other_columns(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test that setting embedding clears other dimension columns"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Set initial embedding
        embedding.embedding = [0.1] * 768
        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        # Update config and set new embedding
        embedding.embedding_config = {"dimension": 1024, "model": "test-model"}
        embedding.embedding = [0.2] * 1024
        test_db.commit()
        test_db.refresh(embedding)

        # Only embedding_1024 should have data
        assert embedding.embedding_768 is None
        assert embedding.embedding_1024 == [0.2] * 1024
        assert embedding.embedding_384 is None
        assert embedding.embedding_1536 is None

    def test_embedding_property_without_config(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test that accessing embedding without config raises error"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding_768 = [0.1] * 768

        with pytest.raises(ValueError, match="Embedding configuration is not set"):
            _ = embedding.embedding

    def test_embedding_property_setter_without_config(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test that setting embedding without config raises error"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        with pytest.raises(ValueError, match="embedding_config must be set"):
            embedding.embedding = [0.1] * 768

    def test_embedding_property_setter_dimension_mismatch(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test that setting wrong dimension raises error"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Try to set 384-dim vector when config says 768
        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            embedding.embedding = [0.1] * 384

    def test_dimension_property(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test dimension property returns config dimension"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 1024, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert embedding.dimension == 1024

    def test_dimension_property_without_config(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test dimension property raises error without config"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        with pytest.raises(ValueError, match="Embedding configuration is not set"):
            _ = embedding.dimension

    def test_active_dimension_property(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test active_dimension returns the actual stored dimension"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 384, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding_384 = [0.1] * 384

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        assert embedding.active_dimension == 384

    def test_active_dimension_property_none(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test active_dimension returns None when no embedding stored"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        assert embedding.active_dimension is None

    def test_embedding_column_name_property(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test embedding_column_name returns correct column name"""
        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 1536, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding_1536 = [0.1] * 1536

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        assert embedding.embedding_column_name == "embedding_1536"

    def test_repr(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test string representation"""
        entity_id = uuid.uuid4()
        embedding = Embedding(
            entity_id=entity_id,
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
            status="active",
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


@pytest.mark.unit
class TestEmbeddingConstraints:
    """🔒 Test database constraints on Embedding model"""

    def test_check_constraint_exactly_one_embedding(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
    ):
        """Test that CHECK constraint enforces exactly one embedding column"""
        # This would violate the CHECK constraint (two embeddings set)
        # We can't test this directly via SQLAlchemy ORM since the property setter
        # clears other columns, but we can test via raw SQL
        from sqlalchemy import text

        embedding = Embedding(
            entity_id=uuid.uuid4(),
            entity_type="Test",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "test-model"},
            config_hash="test_hash",
            searchable_text="test text",
            text_hash="text_hash",
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
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
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
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
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
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding2.embedding = [0.2] * 768
        test_db.add(embedding2)

        with pytest.raises(IntegrityError, match="ix_embedding_nano_id"):
            test_db.commit()

        test_db.rollback()


@pytest.mark.unit
class TestEmbeddingRelationships:
    """🔗 Test polymorphic relationships with Test and Source models"""

    def test_test_embeddings_relationship(
        self, test_db: Session, db_test_minimal, test_org_id: str, authenticated_user_id: str, test_model
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
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
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


@pytest.mark.unit
class TestSearchableText:
    """📝 Test to_searchable_text() implementations"""

    def test_source_to_searchable_text_full(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test Source.to_searchable_text() with all fields"""
        source = Source(
            title="AI Safety Research",
            description="Study on AI alignment",
            content="In this paper we explore..." * 100,
            citation="Smith et al. 2024",
            url="https://example.com/paper",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        text = source.to_searchable_text()

        assert "AI Safety Research" in text
        assert "Study on AI alignment" in text
        assert "In this paper we explore" in text
        assert "Smith et al. 2024" in text
        assert "https://example.com/paper" in text

    def test_source_to_searchable_text_truncation(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that content is truncated to 20000 chars"""
        # Create content longer than 20000 chars
        long_content = "A" * 25000

        source = Source(
            title="Test",
            content=long_content,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        text = source.to_searchable_text()

        # Should be truncated (20000 chars + title + spaces)
        assert len(text) < 25000
        assert "Test" in text

    def test_source_to_searchable_text_partial(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test Source.to_searchable_text() with missing fields"""
        source = Source(
            title="Test Source", organization_id=test_org_id, user_id=authenticated_user_id
        )

        text = source.to_searchable_text()

        assert text == "Test Source"

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

    def test_embeddable_mixin_not_implemented(self, test_db: Session):
        """Test that EmbeddableMixin raises NotImplementedError"""
        from rhesis.backend.app.models.mixins import EmbeddableMixin

        class DummyModel(EmbeddableMixin):
            __name__ = "DummyModel"

        dummy = DummyModel()
        with pytest.raises(NotImplementedError, match="DummyModel must implement to_searchable_text"):
            dummy.to_searchable_text()


@pytest.mark.unit
class TestEmbeddingDefaults:
    """🎯 Test default values and server defaults"""

    def test_weight_default(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
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
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        assert embedding.weight == 1.0

    def test_status_default(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, test_model
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
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768

        test_db.add(embedding)
        test_db.commit()
        test_db.refresh(embedding)

        assert embedding.status == "active"
