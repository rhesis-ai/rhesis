from rhesis.sdk.entities import Topic
from dotenv import load_dotenv
from tests.sdk.entities.base_entity_test import BaseEntityTest

load_dotenv()


class TestTopic(BaseEntityTest):
    entity_class = Topic
    entity_name = "topic"
    test_data = {
        "name": "Test Topic",
        "description": "This is a test topic",
        "parent_id": None,
        "entity_type_id": None,
        "status_id": None,
    }

    def test_create_with_parent(self, test_entity):
        """Test creating a topic with a parent"""
        child_data = {
            "name": "Child Topic",
            "description": "This is a child topic",
            "parent_id": str(test_entity["id"]),
            "entity_type_id": None,
            "status_id": None,
        }
        child_topic = self.entity_class(**child_data).save()
        assert child_topic["parent_id"] == test_entity["id"]

        # Clean up the child topic
        try:
            self.entity_class.from_id(child_topic["id"]).delete(child_topic["id"])
        except Exception:
            pass
