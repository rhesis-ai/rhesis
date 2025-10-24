import pytest
from typing import Any, Dict, Type
from rhesis.sdk.entities import BaseEntity
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class BaseEntityTest:
    """Base class for entity tests."""

    entity_class: Type[BaseEntity]
    entity_name: str
    test_data: Dict[str, Any]

    @pytest.fixture
    def test_entity(self):
        """Fixture that creates and returns a test entity"""
        try:
            logger.info(f"Creating new {self.entity_name} with data: {self.test_data}")
            entity = self.entity_class(**self.test_data).save()
            logger.info(f"Created {self.entity_name} response: {entity}")

            # Verify the save was successful
            assert entity is not None, f"Failed to create test {self.entity_name}"
            assert "id" in entity, f"Created {self.entity_name} missing ID"

            yield entity

            # Cleanup
            try:
                if self.entity_class.exists(entity["id"]):
                    self.entity_class.from_id(entity["id"]).delete(entity["id"])
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

        except Exception as e:
            logger.error(f"Error in test_entity fixture: {e}")
            if hasattr(e, "response"):
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.content}")
                logger.error(f"Request URL: {e.response.request.url}")
                logger.error(f"Request method: {e.response.request.method}")
                logger.error(f"Request headers: {e.response.request.headers}")
                logger.error(f"Request body: {e.response.request.body}")
            raise

    def assert_valid_entity_fields(self, entity):
        """Helper function to check entity fields"""
        assert "id" in entity
        for key, value in self.test_data.items():
            assert entity[key] == value

    def test_create_entity(self, test_entity):
        """Test entity creation"""
        self.assert_valid_entity_fields(test_entity)

    def test_read_entity_by_id(self, test_entity):
        """Test reading entity by ID"""
        entity = self.entity_class.from_id(test_entity["id"])
        self.assert_valid_entity_fields(entity.fields)

    def test_read_entities(self, test_entity):
        """Test reading all entities"""
        logger.info("Attempting to fetch all entities")
        entities = self.entity_class.all()

        # Basic validation that we got a response
        assert entities is not None, "Failed to fetch entities list"
        assert isinstance(
            entities, list
        ), f"Expected list response, got {type(entities)}"

        # Log the result
        logger.info(f"Successfully retrieved {len(entities)} entities")

    def test_update_entity(self, test_entity):
        """Test updating entity"""
        # First verify we can fetch the entity
        entity = self.entity_class.from_id(test_entity["id"])
        if entity is None:
            pytest.fail(
                f"Could not fetch {self.entity_name} with ID {test_entity['id']}"
            )

        # Update the name
        updated_name = f"{self.test_data['name']} Updated"
        logger.info(f"Original entity fields: {entity.fields}")

        # Create a new fields dictionary with only the expected fields
        updated_fields = {
            "id": test_entity["id"],  # Include the ID in the update
            "name": updated_name,
            "description": entity.fields["description"],
            "parent_id": None,
            "entity_type": None,
            "status_id": None,
        }
        entity.fields = updated_fields  # Replace fields instead of updating
        logger.info(f"Updated entity fields: {entity.fields}")

        # Try to save
        logger.info(
            f"Attempting to update {self.entity_name} with ID {test_entity['id']}"
        )
        updated_entity = entity.save()
        if updated_entity is None:
            logger.error(
                f"Update failed for {self.entity_name} with ID {test_entity['id']}"
            )
            # Try to fetch the entity again to see its current state
            current = self.entity_class.from_id(test_entity["id"])
            if current:
                logger.info(f"Current entity state: {current.fields}")

        assert updated_entity is not None, f"Failed to update {self.entity_name}"

        # Verify the update
        assert updated_entity["name"] == updated_name, (
            f"Updated {self.entity_name} name does not match. "
            f"Expected: {updated_name}, Got: {updated_entity['name']}"
        )

    def test_delete_entity(self, test_entity):
        """Test deleting entity"""
        entity_id = test_entity["id"]
        entity = self.entity_class.from_id(entity_id)
        if entity is None:
            pytest.fail(f"Could not fetch {self.entity_name} with ID {entity_id}")

        logger.info(f"Attempting to delete {self.entity_name} with ID {entity_id}")
        success = entity.delete(entity_id)
        assert success is not None, f"Delete operation failed for {self.entity_name}"
        assert success, f"Failed to delete {self.entity_name}"

        # Verify deletion
        exists = self.entity_class.exists(entity_id)
        assert not exists, f"{self.entity_name} still exists after deletion"
