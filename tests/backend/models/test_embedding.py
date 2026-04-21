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
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models import Embedding
from rhesis.backend.app.models.embedding import EmbeddingConfig
from rhesis.backend.app.utils.crud_utils import get_or_create_status

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


    def test_test_result_to_searchable_text(self):
        """Test TestResult.to_searchable_text() extracts relevant fields"""
        from rhesis.backend.app.models import Status, TestResult

        status = Status(name="Failed")
        test_result = TestResult(
            status=status,
            test_output={"response": "I don't know the answer to that."},
            test_metrics={
                "metric_1": {"reason": "The model failed to answer the question."},
                "metric_2": {"reasoning": "Hallucinated information."}
            }
        )

        text = test_result.to_searchable_text()

        assert "Failed" in text
        assert "I don't know the answer to that." in text
        assert "The model failed to answer the question." in text
        assert "Hallucinated information." in text

    def test_trace_to_searchable_text(self):
        """Test Trace.to_searchable_text() extracts span data but filters system prompts"""
        from rhesis.backend.app.constants import AISpanAttributes
        from rhesis.backend.app.models import Trace

        trace = Trace(
            span_name="llm_call",
            status_code="OK",
            status_message="Success",
            attributes={
                AISpanAttributes.OPERATION_TYPE: "completion",
                AISpanAttributes.MODEL_NAME: "gpt-4",
                "gen_ai.prompt": "User query here",
                "gen_ai.system.message": "You are a helpful assistant",  # Should be filtered
                "gen_ai.completion": "Assistant response here",
                "gen_ai.tool.calls": "weather_api",
            }
        )

        text = trace.to_searchable_text()

        assert "llm_call" in text
        assert "OK" in text
        assert "Success" in text
        assert "completion" in text
        assert "gpt-4" in text
        assert "User query here" in text
        assert "Assistant response here" in text
        assert "weather_api" in text
        assert "You are a helpful assistant" not in text

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
    """🔗 Test polymorphic relationships with Test, Trace and Chunk models"""

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

    def test_trace_embeddings_relationship(
        self,
        test_db: Session,
        db_project,
        test_org_id: str,
        authenticated_user_id: str,
        test_model,
        db_status,
    ):
        """Test loading embeddings from Trace model"""
        from datetime import datetime, timezone

        from rhesis.backend.app.models import Trace

        trace = Trace(
            trace_id="test_trace_id_123",
            span_id="test_span_id_123",
            project_id=db_project.id,
            organization_id=test_org_id,
            environment="test",
            span_name="test_span",
            span_kind="INTERNAL",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            duration_ms=10.0,
            status_code="OK",
        )
        test_db.add(trace)
        test_db.commit()
        test_db.refresh(trace)

        # Create embeddings for the trace
        embedding = Embedding(
            entity_id=trace.id,
            entity_type="Trace",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "model-1"},
            config_hash="hash1",
            searchable_text="test content 1",
            text_hash="text_hash1",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768

        test_db.add(embedding)
        test_db.commit()

        # Refresh and access relationship
        test_db.refresh(trace)
        embeddings = trace.embeddings

        assert len(embeddings) == 1
        assert embeddings[0].entity_id == trace.id
        assert embeddings[0].entity_type == "Trace"

    def test_chunk_embeddings_relationship(
        self,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
        test_model,
        db_status,
    ):
        """Test loading embeddings from Chunk model"""
        from rhesis.backend.app.models import Chunk, Source

        source = Source(
            title="Test Source",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(source)
        test_db.commit()

        chunk = Chunk(
            source_id=source.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            content="test chunk content",
            chunk_index=0,
            token_count=3,
        )
        test_db.add(chunk)
        test_db.commit()
        test_db.refresh(chunk)

        # Create embeddings for the chunk
        embedding = Embedding(
            entity_id=chunk.id,
            entity_type="Chunk",
            model_id=test_model.id,
            embedding_config={"dimension": 768, "model": "model-1"},
            config_hash="hash1",
            searchable_text="test content 1",
            text_hash="text_hash1",
            status_id=db_status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        embedding.embedding = [0.1] * 768

        test_db.add(embedding)
        test_db.commit()

        # Refresh and access relationship
        test_db.refresh(chunk)
        embeddings = chunk.embeddings

        assert len(embeddings) == 1
        assert embeddings[0].entity_id == chunk.id
        assert embeddings[0].entity_type == "Chunk"


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


@pytest.mark.integration
class TestEmbeddableMixinEmbeddingListeners:
    """EmbeddableMixin after_insert/after_update skip enqueue when user_id is missing."""

    @patch("rhesis.backend.app.services.embedding.services.EmbeddingService")
    def test_insert_skips_enqueue_when_user_id_none(
        self,
        mock_embedding_service_class,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
        db_test_with_prompt,
    ):
        """No embedding job when TestResult has no user_id (nullable ownership)."""
        mock_instance = mock_embedding_service_class.return_value

        status = get_or_create_status(
            test_db,
            name="completed",
            entity_type="TestResult",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_result = models.TestResult(
            test_id=db_test_with_prompt.id,
            test_run_id=None,
            test_configuration_id=None,
            test_output={"response": "hello"},
            status_id=status.id,
            organization_id=test_org_id,
            user_id=None,
        )
        test_db.add(test_result)
        test_db.commit()

        mock_instance.enqueue_embedding.assert_not_called()

    @patch("rhesis.backend.app.services.embedding.services.EmbeddingService")
    def test_update_skips_enqueue_when_user_id_none(
        self,
        mock_embedding_service_class,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
        db_test_with_prompt,
    ):
        """Updates still skip embedding when user_id remains unset."""
        mock_instance = mock_embedding_service_class.return_value

        status = get_or_create_status(
            test_db,
            name="completed",
            entity_type="TestResult",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_result = models.TestResult(
            test_id=db_test_with_prompt.id,
            test_run_id=None,
            test_configuration_id=None,
            test_output={"response": "before"},
            status_id=status.id,
            organization_id=test_org_id,
            user_id=None,
        )
        test_db.add(test_result)
        test_db.commit()
        mock_instance.enqueue_embedding.reset_mock()

        test_result.test_output = {"response": "after update"}
        test_db.commit()

        mock_instance.enqueue_embedding.assert_not_called()


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
