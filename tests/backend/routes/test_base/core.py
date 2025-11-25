"""
🧪 Core Base Test Classes

This module provides the abstract base class and core functionality for all entity route tests.
Contains the essential structure and common helper methods used by all test classes.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from ..endpoints import APIEndpoints
from ..faker_utils import TestDataGenerator
from ..fixtures.data_factories import get_factory, generate_test_data

# Initialize Faker
fake = Faker()


class BaseEntityTests(ABC):
    """Abstract base class for all entity route tests"""

    # Must be overridden by subclasses
    entity_name: str = ""  # e.g., "behavior", "topic"
    entity_plural: str = ""  # e.g., "behaviors", "topics"
    endpoints = None  # e.g., APIEndpoints.BEHAVIORS
    data_generator = None  # e.g., TestDataGenerator method (LEGACY)

    # Optional overrides
    id_field: str = "id"
    name_field: str = "name"
    description_field: str = "description"

    # User relationship fields (override in subclasses if present, or auto-detected)
    user_id_field: Optional[str] = None  # e.g., "user_id"
    owner_id_field: Optional[str] = None  # e.g., "owner_id"
    assignee_id_field: Optional[str] = None  # e.g., "assignee_id"

    # NEW: Factory integration
    @property
    def data_factory(self):
        """Get data factory for this entity type"""
        try:
            return get_factory(self.entity_name)
        except KeyError:
            # Fallback to legacy data generation if no factory exists
            return None

    def __init_subclass__(cls, **kwargs):
        """Auto-detect user relationship fields when subclass is created"""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "entity_name") and cls.entity_name:
            cls._perform_auto_detection()

    @abstractmethod
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample data for entity creation"""
        pass

    @abstractmethod
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal data for entity creation"""
        pass

    @abstractmethod
    def get_update_data(self) -> Dict[str, Any]:
        """Return data for entity updates"""
        pass

    # NEW: Factory-based helper methods
    def get_factory_sample_data(self) -> Dict[str, Any]:
        """Get sample data using factory (preferred over get_sample_data)"""
        if self.data_factory:
            return self.data_factory.sample_data()
        return self.get_sample_data()  # Fallback to abstract method

    def get_factory_minimal_data(self) -> Dict[str, Any]:
        """Get minimal data using factory (preferred over get_minimal_data)"""
        if self.data_factory:
            return self.data_factory.minimal_data()
        return self.get_minimal_data()  # Fallback to abstract method

    def get_factory_update_data(self) -> Dict[str, Any]:
        """Get update data using factory (preferred over get_update_data)"""
        if self.data_factory:
            return self.data_factory.update_data()
        return self.get_update_data()  # Fallback to abstract method

    def get_invalid_data(self) -> Dict[str, Any]:
        """Get invalid data for negative testing"""
        if self.data_factory:
            return self.data_factory.invalid_data()
        return {}  # Empty data is universally invalid

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Get edge case data for boundary testing"""
        if self.data_factory:
            return self.data_factory.edge_case_data(case_type)
        return self.get_sample_data()  # Fallback

    def create_entity(
        self, client: TestClient, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create test entity using factory data if available

        Args:
            client: Test client
            data: Optional custom data (uses factory default if None)

        Returns:
            Created entity data
        """
        if data is None:
            data = self.get_factory_sample_data()

        response = client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK, (
            f"Entity creation failed: {response.text}"
        )

        return response.json()

    def get_long_name_data(self) -> Dict[str, Any]:
        """Return data with very long name for edge testing"""
        return {
            self.name_field: fake.text(max_nb_chars=1000).replace("\n", " "),
            self.description_field: fake.text(max_nb_chars=50),
        }

    def get_special_chars_data(self) -> Dict[str, Any]:
        """Return data with special characters for edge testing"""
        return {
            self.name_field: f"{fake.word()} 🧪 with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}",
            self.description_field: f"Déscription with spëcial characters: {fake.text(max_nb_chars=50)} & symbols: @#$%^&*()",
        }

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return data with null description"""
        return {self.name_field: fake.catch_phrase(), self.description_field: None}

    def create_entity(self, client: TestClient, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Helper to create an entity and return response data"""
        if data is None:
            data = self.get_sample_data()
        response = client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK
        return response.json()

    def create_multiple_entities(self, client: TestClient, count: int) -> list:
        """Helper to create multiple entities for testing"""
        entities = []
        for i in range(count):
            data = self.get_sample_data()
            data[self.name_field] = f"{fake.word().title()} Test {self.entity_name.title()} {i}"
            entity = self.create_entity(client, data)
            entities.append(entity)
        return entities

    def get_user_fields(self) -> list[str]:
        """Get list of user relationship fields for this entity"""
        fields = []
        if self.user_id_field:
            fields.append(self.user_id_field)
        if self.owner_id_field:
            fields.append(self.owner_id_field)
        if self.assignee_id_field:
            fields.append(self.assignee_id_field)
        return fields

    def has_user_relationships(self) -> bool:
        """Check if this entity has any user relationship fields"""
        return bool(self.get_user_fields())

    def get_user_update_data(self, user_id: str = None) -> Dict[str, Any]:
        """Get data for updating user relationship fields"""
        if not self.has_user_relationships():
            return {}

        if user_id is None:
            user_id = str(uuid.uuid4())  # Generate a test user ID

        update_data = {}

        # Update each user field that exists
        if self.user_id_field:
            update_data[self.user_id_field] = user_id
        if self.owner_id_field:
            update_data[self.owner_id_field] = user_id
        if self.assignee_id_field:
            # Use a different user ID for assignee to test different user assignments
            update_data[self.assignee_id_field] = str(uuid.uuid4())

        return update_data

    def get_sample_data_with_users(
        self, user_id: str = None, owner_id: str = None, assignee_id: str = None
    ) -> Dict[str, Any]:
        """Get sample data with user relationship fields populated"""
        data = self.get_sample_data()

        if user_id and self.user_id_field:
            data[self.user_id_field] = user_id
        if owner_id and self.owner_id_field:
            data[self.owner_id_field] = owner_id
        if assignee_id and self.assignee_id_field:
            data[self.assignee_id_field] = assignee_id

        return data

    @classmethod
    def _perform_auto_detection(cls):
        """
        🔍 Auto-detect user relationship fields using multiple strategies

        Attempts to automatically discover user_id, owner_id, and assignee_id fields
        without requiring manual configuration. Uses several detection methods:

        1. Model introspection (if available)
        2. Common naming patterns
        3. Schema introspection via sample data (if available)
        """
        # Skip auto-detection if fields are already manually configured
        if any([cls.user_id_field, cls.owner_id_field, cls.assignee_id_field]):
            return

        # Import auto-detection logic to avoid circular imports
        from .user_detection import UserFieldDetector

        detected_fields = UserFieldDetector.detect_user_fields(cls)

        # Set detected fields
        if "user_id" in detected_fields:
            cls.user_id_field = "user_id"
        if "owner_id" in detected_fields:
            cls.owner_id_field = "owner_id"
        if "assignee_id" in detected_fields:
            cls.assignee_id_field = "assignee_id"

    def _auto_detect_user_fields(self):
        """Instance method to trigger auto-detection if not done at class level"""
        if not any([self.user_id_field, self.owner_id_field, self.assignee_id_field]):
            self.__class__._perform_auto_detection()

    def get_detected_user_fields_info(self) -> Dict[str, Any]:
        """Get information about detected user fields for debugging"""
        return {
            "entity_name": self.entity_name,
            "user_id_field": self.user_id_field,
            "owner_id_field": self.owner_id_field,
            "assignee_id_field": self.assignee_id_field,
            "has_user_relationships": self.has_user_relationships(),
            "all_user_fields": self.get_user_fields(),
        }
