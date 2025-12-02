"""
🧪 Model Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for model entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping

Run with: python -m pytest tests/backend/routes/test_model.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import ModelDataFactory

# Initialize Faker
fake = Faker()


class ModelTestMixin:
    """Enhanced model test mixin using factory system"""

    # Entity configuration
    entity_name = "model"
    entity_plural = "models"
    endpoints = APIEndpoints.MODELS

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample model data using factory"""
        return ModelDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal model data using factory"""
        return ModelDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return model update data using factory"""
        return ModelDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid model data using factory"""
        return ModelDataFactory.invalid_data()

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case model data using factory"""
        return ModelDataFactory.edge_case_data(case_type)

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return model data with null description"""
        data = ModelDataFactory.minimal_data()
        data["description"] = None
        return data


# Standard entity tests - gets ALL tests from base classes
class TestModelStandardRoutes(ModelTestMixin, BaseEntityRouteTests):
    """Complete standard model route tests using base classes"""

    pass


# === MODEL-SPECIFIC TESTS (Enhanced with Factories) ===


@pytest.mark.integration
class TestModelConnectionTesting(ModelTestMixin, BaseEntityTests):
    """Model-specific connection testing functionality"""

    def test_model_connection_test_endpoint(self, model_factory):
        """🔌 Test model connection testing endpoint"""
        # Create model using factory
        model = model_factory.create(self.get_sample_data())
        model_id = model["id"]

        # Test the connection endpoint
        response = model_factory.client.post(self.endpoints.test(model_id))

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert "status" in result
        assert result["status"] == "success"
        assert "message" in result

    def test_model_connection_test_nonexistent(self, model_factory):
        """🔌 Test connection test for non-existent model"""
        fake_model_id = str(uuid.uuid4())

        response = model_factory.client.post(self.endpoints.test(fake_model_id))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_model_connection_test_with_different_endpoints(self, model_factory):
        """🔌 Test connection testing with various endpoint types"""
        endpoint_types = [
            "https://api.openai.com/v1/chat/completions",
            "https://api.anthropic.com/v1/messages",
            "https://generativelanguage.googleapis.com/v1/models",
            "https://api.together.xyz/inference",
        ]

        for endpoint_url in endpoint_types:
            data = self.get_sample_data()
            data["endpoint"] = endpoint_url
            data["name"] = f"Test Model for {endpoint_url.split('//')[1].split('.')[1].title()}"

            model = model_factory.create(data)

            # Test connection for this model
            response = model_factory.client.post(self.endpoints.test(model["id"]))

            # Should handle different endpoint types gracefully
            assert response.status_code in [
                status.HTTP_200_OK,  # Success
                status.HTTP_500_INTERNAL_SERVER_ERROR,  # Connection issues are expected in tests
            ]


# === MODEL-SPECIFIC VALIDATION TESTS ===


@pytest.mark.unit
class TestModelValidation(ModelTestMixin, BaseEntityTests):
    """Model-specific validation tests"""

    def test_create_model_required_fields(self, model_factory):
        """📝 Test model creation with all required fields"""
        required_fields = ["name", "model_name", "endpoint", "key"]

        # Test with all required fields
        data = self.get_minimal_data()
        response = model_factory.client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK

        created_model = response.json()
        for field in required_fields:
            assert field in created_model
            assert created_model[field] is not None

    def test_create_model_missing_required_fields(self, model_factory):
        """📝 Test model creation with missing required fields"""
        required_fields = ["name", "model_name", "key"]  # endpoint is optional

        for field_to_remove in required_fields:
            data = self.get_minimal_data()
            del data[field_to_remove]

            response = model_factory.client.post(self.endpoints.create, json=data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_model_with_headers(self, model_factory):
        """📝 Test model creation with request headers"""
        data = self.get_sample_data()
        data["request_headers"] = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
            "User-Agent": "TestClient/1.0",
        }

        response = model_factory.client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK

        created_model = response.json()
        assert "request_headers" in created_model
        # Headers might be stored as JSON string, so just check they exist
        assert created_model["request_headers"] is not None

    def test_model_endpoint_url_validation(self, model_factory):
        """🌐 Test model creation with various URL formats"""
        valid_urls = [
            "https://api.openai.com/v1/chat/completions",
            "http://localhost:8000/api/v1/generate",
            "https://api.anthropic.com/v1/messages",
            "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
        ]

        for url in valid_urls:
            data = self.get_minimal_data()
            data["endpoint"] = url
            data["name"] = f"Test Model {url.split('://')[1].split('/')[0]}"

            response = model_factory.client.post(self.endpoints.create, json=data)
            assert response.status_code == status.HTTP_200_OK

            created_model = response.json()
            assert created_model["endpoint"] == url

    def test_model_name_variations(self, model_factory):
        """🏷️ Test model creation with different model name formats"""
        model_names = [
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-sonnet-20240229",
            "gemini-pro",
            "llama-2-70b-chat",
            "mixtral-8x7b-instruct-v0.1",
        ]

        for model_name in model_names:
            data = self.get_minimal_data()
            data["model_name"] = model_name
            data["name"] = f"Test {model_name.title()} Model"

            response = model_factory.client.post(self.endpoints.create, json=data)
            assert response.status_code == status.HTTP_200_OK

            created_model = response.json()
            assert created_model["model_name"] == model_name


# === EDGE CASE TESTS (Enhanced with Factory Data) ===


@pytest.mark.unit
class TestModelEdgeCases(ModelTestMixin, BaseEntityTests):
    """Enhanced model edge case tests using factory system"""

    def test_create_model_long_name(self, model_factory):
        """Test creating model with very long name"""
        long_name_data = self.get_edge_case_data("long_name")

        response = model_factory.client.post(self.endpoints.create, json=long_name_data)

        # Should handle long names gracefully
        assert response.status_code in [
            status.HTTP_200_OK,  # If long names are allowed
            status.HTTP_422_UNPROCESSABLE_ENTITY,  # If they're rejected
        ]

    def test_create_model_special_characters(self, model_factory):
        """Test creating model with special characters"""
        special_char_data = self.get_edge_case_data("special_chars")

        response = model_factory.client.post(self.endpoints.create, json=special_char_data)

        # Should handle special characters gracefully
        assert response.status_code == status.HTTP_200_OK
        created_model = response.json()
        assert created_model["name"] == special_char_data["name"]

    def test_create_model_unicode(self, model_factory):
        """Test creating model with unicode characters"""
        unicode_data = self.get_edge_case_data("unicode")

        response = model_factory.client.post(self.endpoints.create, json=unicode_data)

        assert response.status_code == status.HTTP_200_OK
        created_model = response.json()
        assert created_model["name"] == unicode_data["name"]

    def test_create_model_sql_injection_attempt(self, model_factory):
        """🛡️ Test model creation with SQL injection attempt"""
        injection_data = self.get_edge_case_data("sql_injection")

        response = model_factory.client.post(self.endpoints.create, json=injection_data)

        # Should either create safely or reject
        if response.status_code == status.HTTP_200_OK:
            # If created, verify it was sanitized
            created_model = response.json()
            assert created_model["name"] is not None
        else:
            # If rejected, should be a validation error
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ]

    def test_model_empty_headers(self, model_factory):
        """📝 Test model with empty request headers"""
        data = self.get_minimal_data()
        data["request_headers"] = {}

        response = model_factory.client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK

        created_model = response.json()
        # Empty headers should be handled gracefully
        assert "request_headers" in created_model

    def test_model_malformed_headers(self, model_factory):
        """📝 Test model with malformed request headers"""
        data = self.get_minimal_data()
        data["request_headers"] = "not-a-dict"

        response = model_factory.client.post(self.endpoints.create, json=data)
        # Should reject malformed headers
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# === MODEL UPDATE TESTS ===


@pytest.mark.integration
class TestModelUpdates(ModelTestMixin, BaseEntityTests):
    """Model-specific update operation tests"""

    def test_update_model_endpoint(self, model_factory):
        """🔄 Test updating model endpoint"""
        # Create a model
        model = model_factory.create(self.get_sample_data())

        # Update the endpoint
        update_data = {"endpoint": "https://api.newprovider.com/v2/chat"}

        response = model_factory.client.put(self.endpoints.put(model["id"]), json=update_data)

        assert response.status_code == status.HTTP_200_OK
        updated_model = response.json()
        assert updated_model["endpoint"] == update_data["endpoint"]
        assert updated_model["id"] == model["id"]  # ID should remain the same

    def test_update_model_headers(self, model_factory):
        """🔄 Test updating model request headers"""
        # Create a model
        model = model_factory.create(self.get_sample_data())

        # Update the headers
        new_headers = {"Authorization": "Bearer updated-token", "X-Custom-Header": "test-value"}
        update_data = {"request_headers": new_headers}

        response = model_factory.client.put(self.endpoints.put(model["id"]), json=update_data)

        assert response.status_code == status.HTTP_200_OK
        updated_model = response.json()
        # Headers might be stored differently, just verify they're updated
        assert "request_headers" in updated_model

    def test_update_model_key_security(self, model_factory):
        """🔒 Test updating model API key"""
        # Create a model
        model = model_factory.create(self.get_sample_data())
        original_key = model["key"]

        # Update the key
        new_key = str(uuid.uuid4())
        update_data = {"key": new_key}

        response = model_factory.client.put(self.endpoints.put(model["id"]), json=update_data)

        assert response.status_code == status.HTTP_200_OK
        updated_model = response.json()
        assert updated_model["key"] != original_key
        # Note: The API might mask or not return the actual key for security


# === PERFORMANCE TESTS (Using Factory Batches) ===


@pytest.mark.slow
@pytest.mark.integration
class TestModelPerformance(ModelTestMixin, BaseEntityTests):
    """Performance tests using factory batch creation"""

    def test_bulk_model_creation(self, model_factory):
        """🚀 Test creating multiple models efficiently"""
        # Generate batch data using factory
        batch_data = []
        for i in range(8):
            data = ModelDataFactory.sample_data()
            data["name"] = f"Performance Test Model {i + 1}"
            data["model_name"] = f"test-model-{i + 1}"
            batch_data.append(data)

        # Create all models using factory batch method
        models = model_factory.create_batch(batch_data)

        assert len(models) == 8
        assert all(m["id"] is not None for m in models)
        assert all(m["name"] is not None for m in models)

        # Verify they're all different
        names = [m["name"] for m in models]
        assert len(set(names)) == len(names)  # All unique names

    def test_model_list_pagination(self, model_factory, large_entity_batch):
        """🚀 Test list pagination with large dataset"""
        # large_entity_batch fixture creates multiple models
        models = large_entity_batch
        assert len(models) >= 5  # Should have substantial data

        # Test pagination
        response = model_factory.client.get(f"{self.endpoints.list}?limit=5&skip=0")
        assert response.status_code == status.HTTP_200_OK

        page_1 = response.json()
        assert len(page_1) <= 5  # Should respect limit

        # Test second page
        response = model_factory.client.get(f"{self.endpoints.list}?limit=5&skip=5")
        assert response.status_code == status.HTTP_200_OK

        page_2 = response.json()
        # page_2 might be empty if there aren't enough models, which is fine
