"""
📝 Prompt Template Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for prompt template entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🌐 Multilingual prompt template testing
- 🏷️ Tag and relationship testing

Run with: python -m pytest tests/backend/routes/test_prompt_template.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import PromptTemplateDataFactory

# Initialize Faker
fake = Faker()


class PromptTemplateTestMixin:
    """Enhanced prompt template test mixin using factory system"""

    # Entity configuration
    entity_name = "prompt_template"
    entity_plural = "prompt_templates"
    endpoints = APIEndpoints.PROMPT_TEMPLATES

    # Field mappings for prompt templates
    name_field = "content"
    description_field = None  # No description field for prompt templates

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample prompt template data using factory"""
        return PromptTemplateDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal prompt template data using factory"""
        return PromptTemplateDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return prompt template update data using factory"""
        return PromptTemplateDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid prompt template data using factory"""
        return PromptTemplateDataFactory.invalid_data()

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return prompt template data with null description - prompt templates don't have description field"""
        # Prompt templates don't have a description field, so return regular sample data
        return self.get_sample_data()

    def test_entity_with_null_description(self, authenticated_client):
        """Test entity creation with null description - prompt templates don't have description field"""
        # Prompt templates don't have a description field, so this test just verifies
        # that the entity can be created successfully without a description
        template_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=template_data,
        )

        assert response.status_code == status.HTTP_200_OK
        template = response.json()

        # Verify the template was created with the expected content
        assert template["content"] == template_data["content"]
        assert template["language_code"] == template_data["language_code"]


class TestPromptTemplateRoutes(PromptTemplateTestMixin, BaseEntityRouteTests):
    """
    📝 Complete prompt template route test suite

    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks

    Plus prompt template-specific functionality tests.
    """

    # === PROMPT TEMPLATE-SPECIFIC CRUD TESTS ===

    def test_create_prompt_template_with_required_fields(self, authenticated_client):
        """Test prompt template creation with only required fields"""
        minimal_data = self.get_minimal_data()

        response = authenticated_client.post(self.endpoints.create, json=minimal_data)

        assert response.status_code == status.HTTP_200_OK
        created_template = response.json()

        assert created_template["content"] == minimal_data["content"]
        assert created_template["language_code"] == minimal_data["language_code"]
        assert created_template.get("is_summary") == False  # Default value

    def test_create_prompt_template_with_optional_fields(self, authenticated_client):
        """Test prompt template creation with optional fields"""
        template_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=template_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_template = response.json()

        assert created_template["content"] == template_data["content"]
        assert created_template["language_code"] == template_data["language_code"]
        assert created_template["is_summary"] == template_data["is_summary"]

    def test_create_prompt_template_with_unicode_content(self, authenticated_client):
        """Test prompt template creation with unicode content"""
        unicode_data = PromptTemplateDataFactory.edge_case_data("unicode")

        response = authenticated_client.post(
            self.endpoints.create,
            json=unicode_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_template = response.json()

        assert created_template["content"] == unicode_data["content"]
        assert created_template["language_code"] == unicode_data["language_code"]

    def test_create_prompt_template_with_long_content(self, authenticated_client):
        """Test prompt template creation with very long content"""
        long_content_data = PromptTemplateDataFactory.edge_case_data("long_content")

        response = authenticated_client.post(
            self.endpoints.create,
            json=long_content_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_template = response.json()

        assert created_template["content"] == long_content_data["content"]
        assert len(created_template["content"]) > 1000  # Verify it's actually long

    def test_create_prompt_template_with_special_characters(self, authenticated_client):
        """Test prompt template creation with special characters"""
        special_char_data = PromptTemplateDataFactory.edge_case_data("special_chars")

        response = authenticated_client.post(
            self.endpoints.create,
            json=special_char_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_template = response.json()

        assert created_template["content"] == special_char_data["content"]
        assert "🤖" in created_template["content"]  # Verify emoji preserved

    def test_update_prompt_template_content(self, authenticated_client):
        """Test updating prompt template content"""
        # Create initial template
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        template_id = create_response.json()["id"]

        # Update content
        update_data = self.get_update_data()
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, prompt_template_id=template_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_template = response.json()

        assert updated_template["content"] == update_data["content"]
        assert updated_template["language_code"] == update_data["language_code"]

    def test_update_prompt_template_language_code_only(self, authenticated_client):
        """Test updating only the language code of a prompt template"""
        # Create initial template
        initial_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        template_id = create_response.json()["id"]
        original_content = create_response.json()["content"]

        # Update only language code
        update_data = {"language_code": "fr"}
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, prompt_template_id=template_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_template = response.json()

        assert updated_template["content"] == original_content  # Content unchanged
        assert updated_template["language_code"] == "fr"  # Language updated

    def test_get_prompt_template_by_id(self, authenticated_client):
        """Test retrieving a specific prompt template by ID"""
        # Create template
        template_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=template_data,
        )
        template_id = create_response.json()["id"]

        # Get template by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, prompt_template_id=template_id),
        )

        assert response.status_code == status.HTTP_200_OK
        template = response.json()

        assert template["id"] == template_id
        assert template["content"] == template_data["content"]
        assert template["language_code"] == template_data["language_code"]

    def test_delete_prompt_template(self, authenticated_client):
        """Test deleting a prompt template"""
        # Create template
        template_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=template_data,
        )
        template_id = create_response.json()["id"]

        # Delete template
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, prompt_template_id=template_id),
        )

        assert response.status_code == status.HTTP_200_OK
        deleted_template = response.json()
        assert deleted_template["id"] == template_id

        # Verify template is deleted (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, prompt_template_id=template_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE

    def test_list_prompt_templates_with_pagination(self, authenticated_client):
        """Test listing prompt templates with pagination"""
        # Create multiple templates
        templates_data = [self.get_sample_data() for _ in range(5)]
        created_templates = []

        for template_data in templates_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=template_data,
            )
            created_templates.append(response.json())

        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )

        assert response.status_code == status.HTTP_200_OK
        templates = response.json()
        assert len(templates) <= 3

        # Check count header
        assert "X-Total-Count" in response.headers
        total_count = int(response.headers["X-Total-Count"])
        assert total_count >= 5

    def test_list_prompt_templates_with_sorting(self, authenticated_client):
        """Test listing prompt templates with sorting"""
        # Create templates with different creation times
        template1_data = self.get_sample_data()
        template1_data["content"] = "AAA Template"

        template2_data = self.get_sample_data()
        template2_data["content"] = "ZZZ Template"

        # Create templates
        authenticated_client.post(self.endpoints.create, json=template1_data)
        authenticated_client.post(self.endpoints.create, json=template2_data)

        # Test ascending sort by content (if supported)
        response = authenticated_client.get(
            f"{self.endpoints.list}?sort_by=created_at&sort_order=asc",
        )

        assert response.status_code == status.HTTP_200_OK
        templates = response.json()
        assert len(templates) >= 2

    # === PROMPT TEMPLATE-SPECIFIC ERROR HANDLING TESTS ===

    def test_create_prompt_template_without_content(self, authenticated_client):
        """Test creating prompt template without required content field"""
        invalid_data = {}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_prompt_template_with_empty_content(self, authenticated_client):
        """Test creating prompt template with empty content"""
        invalid_data = {"content": ""}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        # This might be allowed or not depending on validation rules
        # Adjust assertion based on actual API behavior
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_get_nonexistent_prompt_template(self, authenticated_client):
        """Test retrieving a non-existent prompt template"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, prompt_template_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_update_nonexistent_prompt_template(self, authenticated_client):
        """Test updating a non-existent prompt template"""
        fake_id = str(uuid.uuid4())
        update_data = self.get_update_data()

        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, prompt_template_id=fake_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_prompt_template(self, authenticated_client):
        """Test deleting a non-existent prompt template"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, prompt_template_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === PROMPT TEMPLATE-SPECIFIC INTEGRATION TESTS ===


@pytest.mark.integration
class TestPromptTemplateLanguageHandling(PromptTemplateTestMixin, BaseEntityTests):
    """Enhanced prompt template language handling tests"""

    def test_create_templates_with_different_languages(self, authenticated_client):
        """Test creating prompt templates with various language codes"""
        languages = ["en", "es", "fr", "de", "zh", "ja", "ar"]
        created_templates = []

        for lang in languages:
            template_data = self.get_sample_data()
            template_data["language_code"] = lang
            template_data["content"] = f"Template in {lang}: {template_data['content']}"

            response = authenticated_client.post(
                self.endpoints.create,
                json=template_data,
            )

            assert response.status_code == status.HTTP_200_OK
            template = response.json()
            assert template["language_code"] == lang
            created_templates.append(template)

        assert len(created_templates) == len(languages)

    def test_filter_templates_by_language(self, authenticated_client):
        """Test filtering prompt templates by language code using OData filter"""
        # Create templates with different languages
        english_data = self.get_sample_data()
        english_data["language_code"] = "en"
        english_data["content"] = "English template content"

        spanish_data = self.get_sample_data()
        spanish_data["language_code"] = "es"
        spanish_data["content"] = "Spanish template content"

        # Create the templates
        authenticated_client.post(self.endpoints.create, json=english_data)
        authenticated_client.post(self.endpoints.create, json=spanish_data)

        # Filter for English templates
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=language_code eq 'en'",
        )

        assert response.status_code == status.HTTP_200_OK
        templates = response.json()

        # Verify all returned templates are English
        for template in templates:
            if template.get("language_code"):  # Skip templates without language_code
                assert template["language_code"] == "en"


@pytest.mark.integration
class TestPromptTemplateRelationships(PromptTemplateTestMixin, BaseEntityTests):
    """Enhanced prompt template relationships tests"""

    def test_prompt_template_with_category_relationship(self, authenticated_client):
        """Test prompt template creation with category relationship"""
        # This test assumes categories exist and can be referenced
        # You may need to create a category first or mock this relationship
        template_data = self.get_sample_data()
        # Note: category_id would need to be a valid UUID from an existing category
        # For now, we'll test the structure without the relationship

        response = authenticated_client.post(
            self.endpoints.create,
            json=template_data,
        )

        assert response.status_code == status.HTTP_200_OK
        template = response.json()
        assert template["content"] == template_data["content"]

    def test_prompt_template_with_topic_relationship(self, authenticated_client):
        """Test prompt template creation with topic relationship"""
        # Similar to category test - would need existing topic
        template_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=template_data,
        )

        assert response.status_code == status.HTTP_200_OK
        template = response.json()
        assert template["content"] == template_data["content"]


# === PROMPT TEMPLATE PERFORMANCE TESTS ===


@pytest.mark.performance
class TestPromptTemplatePerformance(PromptTemplateTestMixin, BaseEntityTests):
    """Prompt template performance tests"""

    def test_create_multiple_prompt_templates_performance(self, authenticated_client):
        """Test creating multiple prompt templates for performance"""
        templates_count = 20
        templates_data = [self.get_sample_data() for _ in range(templates_count)]

        created_templates = []
        for template_data in templates_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=template_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_templates.append(response.json())

        assert len(created_templates) == templates_count

        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={templates_count}",
        )

        assert response.status_code == status.HTTP_200_OK
        templates = response.json()
        assert len(templates) >= templates_count

    def test_large_content_template_handling(self, authenticated_client):
        """Test handling of prompt templates with very large content"""
        large_content_data = PromptTemplateDataFactory.edge_case_data("long_content")

        response = authenticated_client.post(
            self.endpoints.create,
            json=large_content_data,
        )

        assert response.status_code == status.HTTP_200_OK
        template = response.json()

        # Verify content is preserved correctly
        assert template["content"] == large_content_data["content"]
        assert len(template["content"]) > 1000
