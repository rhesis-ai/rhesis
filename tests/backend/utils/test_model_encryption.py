import pytest
import os
from cryptography.fernet import Fernet
from sqlalchemy import text

from rhesis.backend.app.models.model import Model
from rhesis.backend.app.utils.encryption import is_encrypted
from tests.backend.routes.fixtures.data_factories import BaseDataFactory
from faker import Faker

fake = Faker()


class ModelEncryptionDataFactory(BaseDataFactory):
    """Factory for generating model test data for encryption tests"""

    @classmethod
    def minimal_data(cls) -> dict:
        return {
            "name": fake.company() + " Model",
            "model_name": fake.random_element(
                ["gpt-4", "gpt-4-turbo", "claude-3-opus", "claude-3-sonnet", "gemini-pro"]
            ),
            "endpoint": fake.url(),
            "key": "sk-" + fake.sha256()[:40],  # Simulate API key format
        }

    @classmethod
    def sample_data(cls) -> dict:
        data = cls.minimal_data()
        data.update(
            {
                "description": fake.text(max_nb_chars=200),
                "icon": fake.random_element(["🤖", "🧠", "💡", "⚡"]),
                "request_headers": {"Content-Type": "application/json", "User-Agent": "Rhesis/1.0"},
            }
        )
        return data

    @classmethod
    def openai_key(cls) -> str:
        """Generate OpenAI-style API key"""
        return "sk-" + fake.sha256()[:48]

    @classmethod
    def anthropic_key(cls) -> str:
        """Generate Anthropic-style API key"""
        return "sk-ant-" + fake.sha256()[:40]

    @classmethod
    def google_key(cls) -> str:
        """Generate Google-style API key"""
        return "AIza" + fake.sha256()[:35]


@pytest.fixture
def encryption_key():
    """Provide test encryption key"""
    # Preserve original value
    original_key = os.environ.get("DB_ENCRYPTION_KEY")
    key = Fernet.generate_key().decode()
    os.environ["DB_ENCRYPTION_KEY"] = key
    yield key
    # Restore original value or remove if it wasn't set
    if original_key is not None:
        os.environ["DB_ENCRYPTION_KEY"] = original_key
    elif "DB_ENCRYPTION_KEY" in os.environ:
        del os.environ["DB_ENCRYPTION_KEY"]


class TestModelEncryption:
    """Test encryption of Model API key field"""

    def test_api_key_encrypted_in_db(self, test_db, encryption_key):
        """Test that API key is encrypted when stored in database"""
        model_data = ModelEncryptionDataFactory.sample_data()
        model = Model(**model_data)
        test_db.add(model)
        test_db.commit()

        # Read directly from DB (bypassing ORM)
        result = test_db.execute(
            text("SELECT key FROM model WHERE id = :id"), {"id": str(model.id)}
        ).fetchone()

        # Verify encrypted in DB
        assert result[0] is not None
        assert result[0] != model_data["key"]
        assert is_encrypted(result[0])

        # Verify ORM returns decrypted value
        test_db.refresh(model)
        assert model.key == model_data["key"]

    def test_different_provider_keys(self, test_db, encryption_key):
        """Test encryption works for different LLM provider key formats"""
        provider_keys = [
            ModelEncryptionDataFactory.openai_key(),
            ModelEncryptionDataFactory.anthropic_key(),
            ModelEncryptionDataFactory.google_key(),
        ]

        for api_key in provider_keys:
            model_data = ModelEncryptionDataFactory.minimal_data()
            model_data["key"] = api_key
            model = Model(**model_data)
            test_db.add(model)
            test_db.commit()

            # Check encryption
            result = test_db.execute(
                text("SELECT key FROM model WHERE id = :id"), {"id": str(model.id)}
            ).fetchone()

            assert is_encrypted(result[0])
            test_db.refresh(model)
            assert model.key == api_key

    def test_update_api_key(self, test_db, encryption_key):
        """Test updating API key (key rotation scenario)"""
        model_data = ModelEncryptionDataFactory.sample_data()
        model = Model(**model_data)
        test_db.add(model)
        test_db.commit()

        # Rotate key
        new_key = ModelEncryptionDataFactory.openai_key()
        model.key = new_key
        test_db.commit()

        # Verify new key is encrypted
        result = test_db.execute(
            text("SELECT key FROM model WHERE id = :id"), {"id": str(model.id)}
        ).fetchone()

        assert is_encrypted(result[0])
        test_db.refresh(model)
        assert model.key == new_key
        assert model.key != model_data["key"]

    def test_model_name_not_encrypted(self, test_db, encryption_key):
        """Test that model_name is NOT encrypted (it's public)"""
        model_data = ModelEncryptionDataFactory.sample_data()
        model = Model(**model_data)
        test_db.add(model)
        test_db.commit()

        result = test_db.execute(
            text("SELECT model_name FROM model WHERE id = :id"), {"id": str(model.id)}
        ).fetchone()

        assert result[0] == model_data["model_name"]
        assert not is_encrypted(result[0])

    def test_endpoint_not_encrypted(self, test_db, encryption_key):
        """Test that endpoint URL is NOT encrypted (it's public)"""
        model_data = ModelEncryptionDataFactory.sample_data()
        model = Model(**model_data)
        test_db.add(model)
        test_db.commit()

        result = test_db.execute(
            text("SELECT endpoint FROM model WHERE id = :id"), {"id": str(model.id)}
        ).fetchone()

        assert result[0] == model_data["endpoint"]
        assert not is_encrypted(result[0])

    def test_multiple_models_with_different_keys(self, test_db, encryption_key):
        """Test multiple models with different API keys"""
        models_data = [
            ModelEncryptionDataFactory.sample_data(),
            ModelEncryptionDataFactory.sample_data(),
            ModelEncryptionDataFactory.sample_data(),
        ]

        created_models = []
        for model_data in models_data:
            model = Model(**model_data)
            test_db.add(model)
            test_db.commit()
            created_models.append((model.id, model_data["key"]))

        # Verify each model's key is encrypted and decrypts correctly
        for model_id, original_key in created_models:
            result = test_db.execute(
                text("SELECT key FROM model WHERE id = :id"), {"id": str(model_id)}
            ).fetchone()

            assert is_encrypted(result[0])

            model = test_db.query(Model).filter(Model.id == model_id).first()
            assert model.key == original_key

    def test_empty_key_not_allowed(self, test_db, encryption_key):
        """Test that empty key is not allowed (nullable=False)"""
        model_data = ModelEncryptionDataFactory.minimal_data()
        model_data["key"] = None

        model = Model(**model_data)
        test_db.add(model)

        # Should raise IntegrityError due to nullable=False
        with pytest.raises(Exception):
            test_db.commit()

        test_db.rollback()
