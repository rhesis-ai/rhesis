"""
🏭 Entity Factory System for Test Data Management

This module provides a factory-based approach for creating and cleaning up test entities.
It ensures proper lifecycle management and prevents test pollution.

Usage:
    @pytest.fixture
    def behavior_factory(authenticated_client: TestClient):
        factory = EntityFactory(authenticated_client, APIEndpoints.BEHAVIORS)
        yield factory
        factory.cleanup()

    def test_behavior_creation(behavior_factory):
        behavior = behavior_factory.create({"name": "Test Behavior"})
        # Automatic cleanup happens after test
"""

import pytest
from typing import Dict, Any, List, Optional, Protocol
from fastapi.testclient import TestClient
from fastapi import status
import uuid

from ..endpoints import APIEndpoints


class EndpointProtocol(Protocol):
    """Protocol for endpoint objects"""

    create: str

    def get(self, entity_id: str) -> str: ...
    def put(self, entity_id: str) -> str: ...
    def remove(self, entity_id: str) -> str: ...


class EntityFactory:
    """
    Factory for creating and cleaning up test entities

    This class provides a clean way to create test entities with automatic
    cleanup to prevent test pollution and ensure isolation.
    """

    def __init__(self, client: TestClient, endpoints: EndpointProtocol, id_field: str = "id"):
        """
        Initialize entity factory

        Args:
            client: Authenticated test client
            endpoints: Endpoint configuration object
            id_field: Name of the ID field in entity responses
        """
        self.client = client
        self.endpoints = endpoints
        self.id_field = id_field
        self.created_entities: List[str] = []
        self._cleanup_errors: List[str] = []

    def create(
        self, data: Dict[str, Any], expect_status: int = status.HTTP_200_OK
    ) -> Dict[str, Any]:
        """
        Create entity and track for cleanup

        Args:
            data: Entity data to create
            expect_status: Expected HTTP status code

        Returns:
            Created entity data

        Raises:
            AssertionError: If creation fails or returns unexpected status
        """
        response = self.client.post(self.endpoints.create, json=data)

        if response.status_code != expect_status:
            raise AssertionError(
                f"Entity creation failed. Expected {expect_status}, got {response.status_code}. "
                f"Response: {response.text}"
            )

        entity = response.json()
        entity_id = entity.get(self.id_field)

        if not entity_id:
            raise AssertionError(f"Created entity missing {self.id_field} field: {entity}")

        self.created_entities.append(entity_id)
        return entity

    def create_batch(
        self, data_list: List[Dict[str, Any]], expect_status: int = status.HTTP_200_OK
    ) -> List[Dict[str, Any]]:
        """
        Create multiple entities in batch

        Args:
            data_list: List of entity data to create
            expect_status: Expected HTTP status code for each creation

        Returns:
            List of created entity data
        """
        entities = []
        for data in data_list:
            entity = self.create(data, expect_status)
            entities.append(entity)
        return entities

    def get(self, entity_id: str, expect_status: int = status.HTTP_200_OK) -> Dict[str, Any]:
        """
        Get entity by ID

        Args:
            entity_id: ID of entity to retrieve
            expect_status: Expected HTTP status code

        Returns:
            Entity data

        Raises:
            AssertionError: If retrieval fails or returns unexpected status
        """
        response = self.client.get(self.endpoints.get(entity_id))

        if response.status_code != expect_status:
            raise AssertionError(
                f"Entity retrieval failed. Expected {expect_status}, got {response.status_code}. "
                f"Response: {response.text}"
            )

        return response.json()

    def update(
        self, entity_id: str, data: Dict[str, Any], expect_status: int = status.HTTP_200_OK
    ) -> Dict[str, Any]:
        """
        Update entity by ID

        Args:
            entity_id: ID of entity to update
            data: Update data
            expect_status: Expected HTTP status code

        Returns:
            Updated entity data

        Raises:
            AssertionError: If update fails or returns unexpected status
        """
        response = self.client.put(self.endpoints.put(entity_id), json=data)

        if response.status_code != expect_status:
            raise AssertionError(
                f"Entity update failed. Expected {expect_status}, got {response.status_code}. "
                f"Response: {response.text}"
            )

        return response.json()

    def delete(self, entity_id: str, expect_status: int = status.HTTP_200_OK) -> Dict[str, Any]:
        """
        Delete entity by ID

        Args:
            entity_id: ID of entity to delete
            expect_status: Expected HTTP status code

        Returns:
            Deleted entity data

        Raises:
            AssertionError: If deletion fails or returns unexpected status
        """
        response = self.client.delete(self.endpoints.remove(entity_id))

        if response.status_code != expect_status:
            raise AssertionError(
                f"Entity deletion failed. Expected {expect_status}, got {response.status_code}. "
                f"Response: {response.text}"
            )

        # Remove from tracking since it's explicitly deleted
        if entity_id in self.created_entities:
            self.created_entities.remove(entity_id)

        return response.json()

    def get_created_ids(self) -> List[str]:
        """Get list of all created entity IDs"""
        return self.created_entities.copy()

    def cleanup(self) -> None:
        """
        Clean up all created entities

        Attempts to delete all entities created by this factory.
        Errors are collected but don't stop the cleanup process.
        """
        self._cleanup_errors.clear()

        # Clean up in reverse order (LIFO) to handle dependencies
        for entity_id in reversed(self.created_entities):
            try:
                delete_endpoint = self.endpoints.remove(entity_id)
                response = self.client.delete(delete_endpoint)

                # Don't fail on 404 - entity might already be deleted
                if response.status_code not in [
                    status.HTTP_200_OK,
                    status.HTTP_204_NO_CONTENT,
                    status.HTTP_404_NOT_FOUND,
                ]:
                    self._cleanup_errors.append(
                        f"Failed to delete entity {entity_id}: {response.status_code} - {response.text}"
                    )
            except Exception as e:
                self._cleanup_errors.append(f"Exception deleting entity {entity_id}: {str(e)}")

        self.created_entities.clear()

        # Log cleanup errors for debugging but don't fail tests
        if self._cleanup_errors:
            print(f"⚠️  Cleanup errors (non-fatal): {self._cleanup_errors}")

    def force_cleanup(self) -> None:
        """
        Force cleanup with more aggressive retry logic

        Use this for stubborn entities that might have dependencies.
        """
        import time

        max_retries = 3
        for retry in range(max_retries):
            if not self.created_entities:
                break

            self.cleanup()

            if self.created_entities and retry < max_retries - 1:
                time.sleep(0.1)  # Brief pause before retry

    def __len__(self) -> int:
        """Return number of created entities"""
        return len(self.created_entities)

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()


class BehaviorFactory(EntityFactory):
    """Specialized factory for behaviors"""

    def __init__(self, client: TestClient):
        super().__init__(client, APIEndpoints.BEHAVIORS)

    def create_with_metrics(
        self, behavior_data: Dict[str, Any], metric_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Create behavior and associate with metrics

        Args:
            behavior_data: Behavior creation data
            metric_ids: List of metric IDs to associate

        Returns:
            Created behavior data
        """
        behavior = self.create(behavior_data)
        behavior_id = behavior[self.id_field]

        # Associate metrics
        for metric_id in metric_ids:
            response = self.client.post(
                self.endpoints.add_metric_to_behavior(behavior_id, metric_id)
            )
            if response.status_code not in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
                print(f"⚠️  Failed to associate metric {metric_id} with behavior {behavior_id}")

        return behavior


class TopicFactory(EntityFactory):
    """Specialized factory for topics"""

    def __init__(self, client: TestClient):
        super().__init__(client, APIEndpoints.TOPICS)

    def create_hierarchy(
        self, parent_data: Dict[str, Any], children_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create topic hierarchy (parent with children)

        Args:
            parent_data: Parent topic data
            children_data: List of child topic data

        Returns:
            Dict with parent and children data
        """
        parent = self.create(parent_data)
        parent_id = parent[self.id_field]

        children = []
        for child_data in children_data:
            child_data["parent_id"] = parent_id
            child = self.create(child_data)
            children.append(child)

        return {"parent": parent, "children": children}


# Convenience factory creation functions
def create_behavior_factory(client: TestClient) -> BehaviorFactory:
    """Create a behavior factory instance"""
    return BehaviorFactory(client)


def create_topic_factory(client: TestClient) -> TopicFactory:
    """Create a topic factory instance"""
    return TopicFactory(client)


def create_generic_factory(client: TestClient, endpoints: EndpointProtocol) -> EntityFactory:
    """Create a generic entity factory"""
    return EntityFactory(client, endpoints)


# Export main classes
__all__ = [
    "EntityFactory",
    "BehaviorFactory",
    "TopicFactory",
    "create_behavior_factory",
    "create_topic_factory",
    "create_generic_factory",
]
