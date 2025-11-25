import os

import pytest
from cryptography.fernet import Fernet
from faker import Faker
from sqlalchemy import text

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.utils.encryption import is_encrypted
from tests.backend.routes.fixtures.data_factories import BaseDataFactory

fake = Faker()


class EndpointEncryptionDataFactory(BaseDataFactory):
    """Factory for generating endpoint test data for encryption tests"""

    @classmethod
    def minimal_data(cls) -> dict:
        return {"name": fake.company() + " API", "connection_type": "REST", "url": fake.url()}

    @classmethod
    def sample_data(cls) -> dict:
        data = cls.minimal_data()
        data.update(
            {
                "auth_token": fake.sha256(),
                "client_id": fake.uuid4(),
                "client_secret": fake.sha256(),
                "last_token": fake.sha256(),
            }
        )
        return data

    @classmethod
    def update_data(cls) -> dict:
        return {"auth_token": fake.sha256(), "client_secret": fake.sha256()}

    @classmethod
    def invalid_data(cls) -> dict:
        return {}  # Missing required fields


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


class TestEndpointEncryption:
    """Test encryption of Endpoint model authentication fields"""

    def test_auth_token_encrypted_in_db(self, test_db, encryption_key):
        """Test that auth_token is encrypted when stored in database"""
        # Create endpoint using factory
        endpoint_data = EndpointEncryptionDataFactory.sample_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        # Read directly from DB (bypassing ORM)
        result = test_db.execute(
            text("SELECT auth_token FROM endpoint WHERE id = :id"), {"id": str(endpoint.id)}
        ).fetchone()

        # Verify encrypted in DB
        assert result[0] is not None
        assert result[0] != endpoint_data["auth_token"]
        assert is_encrypted(result[0])

        # Verify ORM returns decrypted value
        test_db.refresh(endpoint)
        assert endpoint.auth_token == endpoint_data["auth_token"]

    def test_client_secret_encrypted_in_db(self, test_db, encryption_key):
        """Test that client_secret is encrypted when stored"""
        endpoint_data = EndpointEncryptionDataFactory.sample_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        # Check DB directly
        result = test_db.execute(
            text("SELECT client_secret FROM endpoint WHERE id = :id"), {"id": str(endpoint.id)}
        ).fetchone()

        assert is_encrypted(result[0])
        test_db.refresh(endpoint)
        assert endpoint.client_secret == endpoint_data["client_secret"]

    def test_last_token_encrypted_in_db(self, test_db, encryption_key):
        """Test that last_token is encrypted when stored"""
        endpoint_data = EndpointEncryptionDataFactory.sample_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        result = test_db.execute(
            text("SELECT last_token FROM endpoint WHERE id = :id"), {"id": str(endpoint.id)}
        ).fetchone()

        assert is_encrypted(result[0])
        test_db.refresh(endpoint)
        assert endpoint.last_token == endpoint_data["last_token"]

    def test_none_values_handled(self, test_db, encryption_key):
        """Test that None values work correctly"""
        endpoint_data = EndpointEncryptionDataFactory.minimal_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        test_db.refresh(endpoint)
        assert endpoint.auth_token is None
        assert endpoint.client_secret is None
        assert endpoint.last_token is None

    def test_update_encrypted_field(self, test_db, encryption_key):
        """Test updating encrypted fields"""
        endpoint_data = EndpointEncryptionDataFactory.sample_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        # Update token
        new_token = fake.sha256()
        endpoint.auth_token = new_token
        test_db.commit()

        # Verify still encrypted
        result = test_db.execute(
            text("SELECT auth_token FROM endpoint WHERE id = :id"), {"id": str(endpoint.id)}
        ).fetchone()

        assert is_encrypted(result[0])
        test_db.refresh(endpoint)
        assert endpoint.auth_token == new_token

    def test_client_id_not_encrypted(self, test_db, encryption_key):
        """Test that client_id is NOT encrypted (it's public)"""
        endpoint_data = EndpointEncryptionDataFactory.sample_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        result = test_db.execute(
            text("SELECT client_id FROM endpoint WHERE id = :id"), {"id": str(endpoint.id)}
        ).fetchone()

        assert result[0] == endpoint_data["client_id"]
        assert not is_encrypted(result[0])

    def test_all_encrypted_fields_together(self, test_db, encryption_key):
        """Test that all three encrypted fields work together"""
        endpoint_data = EndpointEncryptionDataFactory.sample_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        # Query all encrypted fields at once
        result = test_db.execute(
            text("SELECT auth_token, client_secret, last_token FROM endpoint WHERE id = :id"),
            {"id": str(endpoint.id)},
        ).fetchone()

        # All should be encrypted in DB
        assert is_encrypted(result[0])
        assert is_encrypted(result[1])
        assert is_encrypted(result[2])

        # All should decrypt correctly via ORM
        test_db.refresh(endpoint)
        assert endpoint.auth_token == endpoint_data["auth_token"]
        assert endpoint.client_secret == endpoint_data["client_secret"]
        assert endpoint.last_token == endpoint_data["last_token"]

    def test_empty_string_handled(self, test_db, encryption_key):
        """Test that empty strings are handled correctly"""
        endpoint_data = EndpointEncryptionDataFactory.minimal_data()
        endpoint_data["auth_token"] = ""
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        test_db.refresh(endpoint)
        assert endpoint.auth_token == ""

    def test_update_from_none_to_value(self, test_db, encryption_key):
        """Test updating a field from None to a value"""
        endpoint_data = EndpointEncryptionDataFactory.minimal_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        # Initially None
        assert endpoint.auth_token is None

        # Update to a value
        new_token = fake.sha256()
        endpoint.auth_token = new_token
        test_db.commit()

        # Verify encrypted and retrievable
        result = test_db.execute(
            text("SELECT auth_token FROM endpoint WHERE id = :id"), {"id": str(endpoint.id)}
        ).fetchone()

        assert is_encrypted(result[0])
        test_db.refresh(endpoint)
        assert endpoint.auth_token == new_token

    def test_update_from_value_to_none(self, test_db, encryption_key):
        """Test updating a field from a value to None"""
        endpoint_data = EndpointEncryptionDataFactory.sample_data()
        endpoint = Endpoint(**endpoint_data)
        test_db.add(endpoint)
        test_db.commit()

        # Initially has value
        assert endpoint.auth_token is not None

        # Update to None
        endpoint.auth_token = None
        test_db.commit()

        test_db.refresh(endpoint)
        assert endpoint.auth_token is None
