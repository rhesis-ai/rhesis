import pytest

from rhesis.sdk.entities import Behavior, Status

from .base_entity_test import BaseEntityTest


class TestBehavior(BaseEntityTest):
    entity_class = Behavior
    entity_name = "behavior"
    test_data = {"name": "Test Behavior", "description": "This is a test behavior"}

    @pytest.fixture
    def test_status(self):
        """Fixture that creates and returns a test Status entity"""
        # Create a test status
        status = Status(name="Test Status", description="Test status for behavior").save()
        yield status

        # Cleanup
        try:
            if Status.exists(status["id"]):
                Status.from_id(status["id"]).delete(status["id"])
        except Exception:
            pass

    def test_update_status(self, test_entity, test_status):
        """Test updating behavior status"""
        behavior = self.entity_class.from_id(test_entity["id"])
        behavior.fields["status_id"] = test_status["id"]
        updated_behavior = behavior.save()
        assert updated_behavior["status_id"] == test_status["id"]
