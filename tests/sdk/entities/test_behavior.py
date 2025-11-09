from rhesis.sdk.entities import Behavior
from tests.sdk.entities.base_entity_test import BaseEntityTest


class TestBehavior(BaseEntityTest):
    entity_class = Behavior
    entity_name = "behavior"
    test_data = {"name": "Test Behavior", "description": "This is a test behavior"}

    def test_update_status(self, test_entity, test_status):
        """Test updating behavior status"""
        behavior = self.entity_class.from_id(test_entity["id"])
        behavior.fields["status_id"] = test_status["id"]
        updated_behavior = behavior.save()
        assert updated_behavior["status_id"] == test_status["id"]
