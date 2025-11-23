"""
🔄 Response Pattern Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for response pattern entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🧪 Behavior relationship testing
- 📝 Response type validation

Run with: python -m pytest tests/backend/routes/test_response_pattern.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import ResponsePatternDataFactory, BehaviorDataFactory

# Initialize Faker
fake = Faker()


class ResponsePatternTestMixin:
    """Enhanced response pattern test mixin using factory system"""

    # Entity configuration
    entity_name = "response_pattern"
    entity_plural = "response_patterns"
    endpoints = APIEndpoints.RESPONSE_PATTERNS

    # Field mappings for response patterns
    name_field = "text"
    description_field = None  # No description field for response patterns

    def _create_test_behavior(self, behavior_factory):
        """Create a behavior for this specific test using factory"""
        from .fixtures.data_factories import BehaviorDataFactory

        # Create a behavior using the factory (automatic cleanup)
        behavior = behavior_factory.create(BehaviorDataFactory.minimal_data())
        return behavior["id"]

    # Factory-based data methods
    def get_sample_data(self, behavior_factory=None) -> Dict[str, Any]:
        """Return sample response pattern data using factory"""
        data = ResponsePatternDataFactory.sample_data()
        # Always create a valid behavior_id - if no factory passed, try to get it from pytest context
        if behavior_factory:
            data["behavior_id"] = self._create_test_behavior(behavior_factory)
        else:
            # Called from base test - try to get behavior_factory from pytest context
            data["behavior_id"] = self._get_behavior_from_context()
        return data

    def get_minimal_data(self, behavior_factory=None) -> Dict[str, Any]:
        """Return minimal response pattern data using factory"""
        data = ResponsePatternDataFactory.minimal_data()
        # Always create a valid behavior_id - if no factory passed, try to get it from pytest context
        if behavior_factory:
            data["behavior_id"] = self._create_test_behavior(behavior_factory)
        else:
            # Called from base test - try to get behavior_factory from pytest context
            data["behavior_id"] = self._get_behavior_from_context()
        return data

    def get_update_data(self, behavior_factory=None) -> Dict[str, Any]:
        """Return response pattern update data using factory"""
        data = ResponsePatternDataFactory.update_data()
        # Always create a valid behavior_id - if no factory passed, try to get it from pytest context
        if behavior_factory:
            data["behavior_id"] = self._create_test_behavior(behavior_factory)
        else:
            # Called from base test - try to get behavior_factory from pytest context
            data["behavior_id"] = self._get_behavior_from_context()
        return data

    def _get_behavior_from_context(self):
        """Get behavior_id from pytest context when called from base tests"""
        import inspect
        from .fixtures.factories import create_behavior_factory
        from .fixtures.data_factories import BehaviorDataFactory

        # Look through the call stack to find the authenticated_client
        for frame_info in inspect.stack():
            frame_locals = frame_info.frame.f_locals
            if "authenticated_client" in frame_locals:
                authenticated_client = frame_locals["authenticated_client"]
                # Create a temporary behavior factory
                behavior_factory = create_behavior_factory(authenticated_client)
                behavior = behavior_factory.create(BehaviorDataFactory.minimal_data())
                return behavior["id"]

        # Check if this is an authentication test (uses unauthenticated client)
        for frame_info in inspect.stack():
            frame_locals = frame_info.frame.f_locals
            if (
                "client" in frame_locals
                and frame_info.function == "test_entity_routes_require_authentication"
            ):
                # For authentication tests, return a fake UUID since the request should fail anyway
                return "00000000-0000-0000-0000-000000000000"

        # If we can't find authenticated_client, return None since behavior_id is now optional
        return None

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid response pattern data using factory"""
        return ResponsePatternDataFactory.invalid_data()

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return response pattern data with null description - response patterns don't have description field"""
        # Response patterns don't have a description field, so return regular sample data
        return self.get_sample_data()

    def test_entity_with_null_description(self, authenticated_client):
        """Test entity creation with null description - response patterns don't have description field"""
        # Response patterns don't have a description field, so just test normal creation
        sample_data = self.get_sample_data()
        response = authenticated_client.post(self.endpoints.create, json=sample_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data[self.name_field] == sample_data[self.name_field]
        # No description field to check for response patterns


class TestResponsePatternRoutes(ResponsePatternTestMixin, BaseEntityRouteTests):
    """
    🔄 Complete response pattern route test suite

    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks

    Plus response pattern-specific functionality tests.
    """

    # === RESPONSE PATTERN-SPECIFIC CRUD TESTS ===

    def test_create_response_pattern_with_required_fields(
        self, authenticated_client, behavior_factory
    ):
        """Test response pattern creation with only required fields"""
        minimal_data = self.get_minimal_data(behavior_factory)

        response = authenticated_client.post(
            self.endpoints.create,
            json=minimal_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_pattern = response.json()

        assert created_pattern["text"] == minimal_data["text"]
        assert created_pattern["behavior_id"] == minimal_data["behavior_id"]
        assert created_pattern.get("response_pattern_type_id") is None  # Optional field

    def test_create_response_pattern_with_optional_fields(
        self, authenticated_client, behavior_factory
    ):
        """Test response pattern creation with optional fields"""
        pattern_data = self.get_sample_data(behavior_factory)

        response = authenticated_client.post(
            self.endpoints.create,
            json=pattern_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_pattern = response.json()

        assert created_pattern["text"] == pattern_data["text"]
        assert created_pattern["behavior_id"] == pattern_data["behavior_id"]
        assert (
            created_pattern.get("response_pattern_type_id") is None
        )  # Optional field, not included in sample data

    def _create_response_pattern_type_lookup(
        self, test_db, test_organization, type_value: str, description: str
    ):
        """Create a response pattern type lookup entry"""
        from rhesis.backend.app.models.type_lookup import TypeLookup

        # Create type lookup entry with organization context
        type_lookup = TypeLookup(
            type_name="ResponsePatternType",
            type_value=type_value,
            description=description,
            organization_id=test_organization.id,  # Use test organization
            user_id=None,  # System-level type
        )
        test_db.add(type_lookup)
        test_db.commit()
        test_db.refresh(type_lookup)
        return str(type_lookup.id)

    def test_create_response_pattern_with_different_response_types(
        self, authenticated_client, behavior_factory, test_db, test_organization
    ):
        """Test response pattern creation with different response types"""
        # Create type lookup entries for response pattern types
        response_types = [
            ("Refusal", "Response pattern type for refusals"),
            ("Compliance", "Response pattern type for compliance"),
            ("Warning", "Response pattern type for warnings"),
            ("Info", "Response pattern type for informational responses"),
        ]
        created_patterns = []

        for type_value, description in response_types:
            # Create the type lookup entry with proper org context
            type_lookup_id = self._create_response_pattern_type_lookup(
                test_db, test_organization, type_value, description
            )

            pattern_data = self.get_sample_data(behavior_factory)
            pattern_data["response_pattern_type_id"] = type_lookup_id
            pattern_data["text"] = f"Response pattern for {type_value} type"

            response = authenticated_client.post(
                self.endpoints.create,
                json=pattern_data,
            )

            assert response.status_code == status.HTTP_200_OK
            pattern = response.json()
            assert pattern["response_pattern_type_id"] == type_lookup_id
            assert f"{type_value} type" in pattern["text"]
            created_patterns.append(pattern)

        assert len(created_patterns) == len(response_types)

    def test_create_response_pattern_with_unicode_text(
        self, authenticated_client, behavior_factory
    ):
        """Test response pattern creation with unicode text"""
        unicode_data = ResponsePatternDataFactory.edge_case_data("special_chars")
        unicode_data["behavior_id"] = self._create_test_behavior(behavior_factory)

        response = authenticated_client.post(
            self.endpoints.create,
            json=unicode_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_pattern = response.json()

        assert created_pattern["text"] == unicode_data["text"]
        assert "🤖" in created_pattern["text"]  # Verify emoji preserved

    def test_create_response_pattern_with_long_text(self, authenticated_client, behavior_factory):
        """Test response pattern creation with very long text"""
        long_text_data = ResponsePatternDataFactory.edge_case_data("long_text")
        long_text_data["behavior_id"] = self._create_test_behavior(behavior_factory)

        response = authenticated_client.post(
            self.endpoints.create,
            json=long_text_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_pattern = response.json()

        assert created_pattern["text"] == long_text_data["text"]
        assert len(created_pattern["text"]) > 1000  # Verify it's actually long

    def test_update_response_pattern_text(self, authenticated_client):
        """Test updating response pattern text"""
        # Create initial pattern
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        pattern_id = create_response.json()["id"]

        # Update text
        update_data = self.get_update_data()
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, response_pattern_id=pattern_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_pattern = response.json()

        assert updated_pattern["text"] == update_data["text"]
        assert updated_pattern["behavior_id"] == update_data["behavior_id"]

    def test_update_response_pattern_behavior_id_only(self, authenticated_client, behavior_factory):
        """Test updating only the behavior_id of a response pattern"""
        # Create initial pattern
        initial_data = self.get_sample_data(behavior_factory)
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        pattern_id = create_response.json()["id"]
        original_text = create_response.json()["text"]

        # Create a new behavior for updating
        new_behavior_id = self._create_test_behavior(behavior_factory)
        update_data = {"behavior_id": new_behavior_id}
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, response_pattern_id=pattern_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_pattern = response.json()

        assert updated_pattern["text"] == original_text  # Text unchanged
        assert updated_pattern["behavior_id"] == new_behavior_id  # Behavior ID updated

    def test_get_response_pattern_by_id(self, authenticated_client):
        """Test retrieving a specific response pattern by ID"""
        # Create pattern
        pattern_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=pattern_data,
        )
        pattern_id = create_response.json()["id"]

        # Get pattern by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, response_pattern_id=pattern_id),
        )

        assert response.status_code == status.HTTP_200_OK
        pattern = response.json()

        assert pattern["id"] == pattern_id
        assert pattern["text"] == pattern_data["text"]
        assert pattern["behavior_id"] == pattern_data["behavior_id"]

    def test_delete_response_pattern(self, authenticated_client):
        """Test deleting a response pattern"""
        # Create pattern
        pattern_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=pattern_data,
        )
        pattern_id = create_response.json()["id"]

        # Delete pattern
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, response_pattern_id=pattern_id),
        )

        assert response.status_code == status.HTTP_200_OK
        deleted_pattern = response.json()
        assert deleted_pattern["id"] == pattern_id

        # Verify pattern is deleted (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, response_pattern_id=pattern_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE

    def test_list_response_patterns_with_pagination(self, authenticated_client):
        """Test listing response patterns with pagination"""
        # Create multiple patterns
        patterns_data = [self.get_sample_data() for _ in range(5)]
        created_patterns = []

        for pattern_data in patterns_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=pattern_data,
            )
            created_patterns.append(response.json())

        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )

        assert response.status_code == status.HTTP_200_OK
        patterns = response.json()
        assert len(patterns) <= 3

        # Check count header
        assert "X-Total-Count" in response.headers
        total_count = int(response.headers["X-Total-Count"])
        assert total_count >= 5

    def test_list_response_patterns_with_sorting(self, authenticated_client):
        """Test listing response patterns with sorting"""
        # Create patterns with different creation times
        pattern1_data = self.get_sample_data()
        pattern1_data["text"] = "AAA Pattern"

        pattern2_data = self.get_sample_data()
        pattern2_data["text"] = "ZZZ Pattern"

        # Create patterns
        authenticated_client.post(self.endpoints.create, json=pattern1_data)
        authenticated_client.post(self.endpoints.create, json=pattern2_data)

        # Test sorting by creation date
        response = authenticated_client.get(
            f"{self.endpoints.list}?sort_by=created_at&sort_order=asc",
        )

        assert response.status_code == status.HTTP_200_OK
        patterns = response.json()
        assert len(patterns) >= 2

    # === RESPONSE PATTERN-SPECIFIC ERROR HANDLING TESTS ===

    def test_create_response_pattern_without_text(self, authenticated_client):
        """Test creating response pattern without required text field"""
        invalid_data = {"behavior_id": 1}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_response_pattern_without_behavior_id(self, authenticated_client):
        """Test creating response pattern without behavior_id field (now optional)"""
        valid_data = {"text": "Some response text"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=valid_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_pattern = response.json()
        assert created_pattern["text"] == valid_data["text"]
        assert created_pattern["behavior_id"] is None

    def test_create_response_pattern_with_empty_text(self, authenticated_client):
        """Test creating response pattern with empty text"""
        invalid_data = {"text": "", "behavior_id": 1}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        # This might be allowed or not depending on validation rules
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_create_response_pattern_with_invalid_behavior_id(self, authenticated_client):
        """Test creating response pattern with invalid behavior_id type"""
        invalid_data = {"text": "Some response", "behavior_id": "not_an_integer"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_nonexistent_response_pattern(self, authenticated_client):
        """Test retrieving a non-existent response pattern"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, response_pattern_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_update_nonexistent_response_pattern(self, authenticated_client):
        """Test updating a non-existent response pattern"""
        fake_id = str(uuid.uuid4())
        update_data = self.get_update_data()

        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, response_pattern_id=fake_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_response_pattern(self, authenticated_client):
        """Test deleting a non-existent response pattern"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, response_pattern_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === RESPONSE PATTERN-SPECIFIC INTEGRATION TESTS ===


@pytest.mark.integration
class TestResponsePatternBehaviorRelationships(ResponsePatternTestMixin, BaseEntityRouteTests):
    """Enhanced response pattern behavior relationships tests"""

    def _create_response_pattern_type_lookup(
        self, test_db, test_organization, type_value: str, description: str
    ):
        """Create a response pattern type lookup entry"""
        from rhesis.backend.app.models.type_lookup import TypeLookup

        # Create type lookup entry with organization context
        type_lookup = TypeLookup(
            type_name="ResponsePatternType",
            type_value=type_value,
            description=description,
            organization_id=test_organization.id,  # Use test organization
            user_id=None,  # System-level type
        )
        test_db.add(type_lookup)
        test_db.commit()
        test_db.refresh(type_lookup)
        return str(type_lookup.id)

    def test_create_response_patterns_for_same_behavior(
        self, authenticated_client, behavior_factory
    ):
        """Test creating multiple response patterns for the same behavior"""
        # Create a single behavior for all patterns
        behavior_id = self._create_test_behavior(behavior_factory)
        patterns_count = 3
        created_patterns = []

        for i in range(patterns_count):
            pattern_data = self.get_sample_data(behavior_factory)
            pattern_data["behavior_id"] = behavior_id  # Use the same behavior for all patterns
            pattern_data["text"] = f"Response pattern {i + 1} for behavior {behavior_id}"

            response = authenticated_client.post(
                self.endpoints.create,
                json=pattern_data,
            )

            assert response.status_code == status.HTTP_200_OK
            pattern = response.json()
            assert pattern["behavior_id"] == behavior_id
            created_patterns.append(pattern)

        assert len(created_patterns) == patterns_count

    def test_filter_response_patterns_by_behavior_id(self, authenticated_client, behavior_factory):
        """Test filtering response patterns by behavior_id using OData filter"""
        # Create patterns with different behavior IDs
        behavior_id_1 = self._create_test_behavior(behavior_factory)
        behavior_id_2 = self._create_test_behavior(behavior_factory)

        pattern1_data = self.get_sample_data(behavior_factory)
        pattern1_data["behavior_id"] = behavior_id_1
        pattern1_data["text"] = f"Pattern for behavior {behavior_id_1}"

        pattern2_data = self.get_sample_data(behavior_factory)
        pattern2_data["behavior_id"] = behavior_id_2
        pattern2_data["text"] = f"Pattern for behavior {behavior_id_2}"

        # Create the patterns
        authenticated_client.post(self.endpoints.create, json=pattern1_data)
        authenticated_client.post(self.endpoints.create, json=pattern2_data)

        # Filter for patterns with behavior_id_1
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=behavior_id eq {behavior_id_1}",
        )

        assert response.status_code == status.HTTP_200_OK
        patterns = response.json()

        # Verify all returned patterns have the correct behavior_id
        for pattern in patterns:
            assert pattern["behavior_id"] == behavior_id_1

    def test_response_pattern_types_distribution(
        self, authenticated_client, behavior_factory, test_db, test_organization
    ):
        """Test creating response patterns with different response types"""
        response_types = [
            ("Success", "Successful response pattern"),
            ("Error", "Error response pattern"),
            ("Warning", "Warning response pattern"),
            ("Info", "Informational response pattern"),
        ]
        # Create a single behavior for all patterns
        behavior_id = self._create_test_behavior(behavior_factory)
        created_patterns = []
        created_type_ids = []

        for type_value, description in response_types:
            # Create type lookup entry
            type_lookup_id = self._create_response_pattern_type_lookup(
                test_db, test_organization, type_value, description
            )
            created_type_ids.append(type_lookup_id)

            pattern_data = self.get_sample_data(behavior_factory)
            pattern_data["behavior_id"] = behavior_id
            pattern_data["response_pattern_type_id"] = type_lookup_id
            pattern_data["text"] = f"Response pattern of type {type_value}"

            response = authenticated_client.post(
                self.endpoints.create,
                json=pattern_data,
            )

            assert response.status_code == status.HTTP_200_OK
            pattern = response.json()
            created_patterns.append(pattern)

        # Verify we have patterns of each type
        created_pattern_types = [p["response_pattern_type_id"] for p in created_patterns]
        assert set(created_pattern_types) == set(created_type_ids)


@pytest.mark.integration
class TestResponsePatternFiltering(ResponsePatternTestMixin, BaseEntityRouteTests):
    """Enhanced response pattern filtering tests"""

    def _create_response_pattern_type_lookup(
        self, test_db, test_organization, type_value: str, description: str
    ):
        """Create a response pattern type lookup entry"""
        from rhesis.backend.app.models.type_lookup import TypeLookup

        # Create type lookup entry with organization context
        type_lookup = TypeLookup(
            type_name="ResponsePatternType",
            type_value=type_value,
            description=description,
            organization_id=test_organization.id,  # Use test organization
            user_id=None,  # System-level type
        )
        test_db.add(type_lookup)
        test_db.commit()
        test_db.refresh(type_lookup)
        return str(type_lookup.id)

    def test_filter_response_patterns_by_response_type(
        self, authenticated_client, behavior_factory, test_db, test_organization
    ):
        """Test filtering response patterns by response type"""
        # Create type lookup entries
        success_type_id = self._create_response_pattern_type_lookup(
            test_db, test_organization, "Success", "Success response pattern type"
        )
        error_type_id = self._create_response_pattern_type_lookup(
            test_db, test_organization, "Error", "Error response pattern type"
        )

        # Create patterns with different response types
        success_data = self.get_sample_data(behavior_factory)
        success_data["response_pattern_type_id"] = success_type_id
        success_data["text"] = "Success response pattern"

        error_data = self.get_sample_data(behavior_factory)
        error_data["response_pattern_type_id"] = error_type_id
        error_data["text"] = "Error response pattern"

        # Create the patterns
        authenticated_client.post(self.endpoints.create, json=success_data)
        authenticated_client.post(self.endpoints.create, json=error_data)

        # Filter for success patterns
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=response_pattern_type_id eq {success_type_id}",
        )

        assert response.status_code == status.HTTP_200_OK
        patterns = response.json()

        # Verify all returned patterns are success type
        for pattern in patterns:
            if pattern.get("response_pattern_type_id"):  # Skip patterns without response_type
                assert pattern["response_pattern_type_id"] == success_type_id

    def test_complex_filtering_behavior_and_type(
        self, authenticated_client, behavior_factory, test_db, test_organization
    ):
        """Test complex filtering by both behavior_id and response_type"""
        # Create a behavior and type lookups
        behavior_id = self._create_test_behavior(behavior_factory)
        success_type_id = self._create_response_pattern_type_lookup(
            test_db, test_organization, "Success", "Success response pattern type"
        )
        error_type_id = self._create_response_pattern_type_lookup(
            test_db, test_organization, "Error", "Error response pattern type"
        )

        # Create patterns with same behavior but different types
        success_data = self.get_sample_data(behavior_factory)
        success_data["behavior_id"] = behavior_id
        success_data["response_pattern_type_id"] = success_type_id

        error_data = self.get_sample_data(behavior_factory)
        error_data["behavior_id"] = behavior_id
        error_data["response_pattern_type_id"] = error_type_id

        # Create the patterns
        authenticated_client.post(self.endpoints.create, json=success_data)
        authenticated_client.post(self.endpoints.create, json=error_data)

        # Filter for success patterns of specific behavior
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=behavior_id eq {behavior_id} and response_pattern_type_id eq {success_type_id}",
        )

        assert response.status_code == status.HTTP_200_OK
        patterns = response.json()

        # Verify all returned patterns match both criteria
        for pattern in patterns:
            assert pattern["behavior_id"] == behavior_id
            if pattern.get("response_pattern_type_id"):
                assert pattern["response_pattern_type_id"] == success_type_id


# === RESPONSE PATTERN PERFORMANCE TESTS ===


@pytest.mark.performance
class TestResponsePatternPerformance(ResponsePatternTestMixin, BaseEntityTests):
    """Response pattern performance tests"""

    def test_create_multiple_response_patterns_performance(self, authenticated_client):
        """Test creating multiple response patterns for performance"""
        patterns_count = 25
        patterns_data = [self.get_sample_data() for _ in range(patterns_count)]

        created_patterns = []
        for pattern_data in patterns_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=pattern_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_patterns.append(response.json())

        assert len(created_patterns) == patterns_count

        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={patterns_count}",
        )

        assert response.status_code == status.HTTP_200_OK
        patterns = response.json()
        assert len(patterns) >= patterns_count

    def test_large_text_pattern_handling(self, authenticated_client, behavior_factory):
        """Test handling of response patterns with very large text"""
        large_text_data = ResponsePatternDataFactory.edge_case_data("long_text")
        large_text_data["behavior_id"] = self._create_test_behavior(behavior_factory)

        response = authenticated_client.post(
            self.endpoints.create,
            json=large_text_data,
        )

        assert response.status_code == status.HTTP_200_OK
        pattern = response.json()

        # Verify text is preserved correctly
        assert pattern["text"] == large_text_data["text"]
        assert len(pattern["text"]) > 1000

    def test_bulk_update_response_patterns(self, authenticated_client):
        """Test bulk updating multiple response patterns"""
        # Create multiple patterns
        patterns_count = 10
        created_patterns = []

        for i in range(patterns_count):
            pattern_data = self.get_sample_data()
            pattern_data["text"] = f"Original pattern {i + 1}"

            response = authenticated_client.post(
                self.endpoints.create,
                json=pattern_data,
            )
            created_patterns.append(response.json())

        # Update all patterns
        updated_patterns = []
        for i, pattern in enumerate(created_patterns):
            update_data = {"text": f"Updated pattern {i + 1}"}

            response = authenticated_client.put(
                self.endpoints.format_path(
                    self.endpoints.update, response_pattern_id=pattern["id"]
                ),
                json=update_data,
            )

            assert response.status_code == status.HTTP_200_OK
            updated_pattern = response.json()
            assert updated_pattern["text"] == f"Updated pattern {i + 1}"
            updated_patterns.append(updated_pattern)

        assert len(updated_patterns) == patterns_count
