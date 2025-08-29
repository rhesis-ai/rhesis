"""
Tests for the Comment API endpoints
"""

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.backend.routes.fixtures.data_factories import get_factory


class TestCommentAPI:
    """Test cases for Comment API endpoints"""

    def test_create_comment(self, client: TestClient, db_session):
        """Test creating a new comment"""
        # First create a test user and organization
        user_factory = get_factory("user")
        test_user = user_factory.create()

        # Create a test entity (test) to comment on
        test_factory = get_factory("test")
        test_entity = test_factory.create()

        comment_data = {
            "comment_text": "This is a test comment",
            "emojis": {"👍": 1},
            "entity_id": str(test_entity["id"]),
            "entity_type": "test",
        }

        response = client.post("/comments/", json=comment_data)
        assert response.status_code == 200

        comment = response.json()
        assert comment["comment_text"] == comment_data["comment_text"]
        assert comment["entity_id"] == comment_data["entity_id"]
        assert comment["entity_type"] == comment_data["entity_type"]
        assert "id" in comment
        assert "created_at" in comment

    def test_get_comment(self, client: TestClient, db_session):
        """Test getting a specific comment by ID"""
        # First create a comment
        user_factory = get_factory("user")
        test_user = user_factory.create()

        test_factory = get_factory("test")
        test_entity = test_factory.create()

        comment_data = {
            "comment_text": "Test comment for retrieval",
            "entity_id": str(test_entity["id"]),
            "entity_type": "test",
        }

        create_response = client.post("/comments/", json=comment_data)
        assert create_response.status_code == 200

        comment_id = create_response.json()["id"]

        # Now get the comment
        response = client.get(f"/comments/{comment_id}")
        assert response.status_code == 200

        comment = response.json()
        assert comment["id"] == comment_id
        assert comment["comment_text"] == comment_data["comment_text"]

    def test_update_comment(self, client: TestClient, db_session):
        """Test updating a comment"""
        # First create a comment
        user_factory = get_factory("user")
        test_user = user_factory.create()

        test_factory = get_factory("test")
        test_entity = test_factory.create()

        comment_data = {
            "comment_text": "Original comment text",
            "entity_id": str(test_entity["id"]),
            "entity_type": "test",
        }

        create_response = client.post("/comments/", json=comment_data)
        assert create_response.status_code == 200

        comment_id = create_response.json()["id"]

        # Update the comment
        update_data = {
            "comment_text": "Updated comment text",
            "emojis": {"❤️": 2, "👍": 1},
        }

        response = client.put(f"/comments/{comment_id}", json=update_data)
        assert response.status_code == 200

        comment = response.json()
        assert comment["comment_text"] == update_data["comment_text"]
        assert comment["emojis"] == update_data["emojis"]

    def test_delete_comment(self, client: TestClient, db_session):
        """Test deleting a comment"""
        # First create a comment
        user_factory = get_factory("user")
        test_user = user_factory.create()

        test_factory = get_factory("test")
        test_entity = test_factory.create()

        comment_data = {
            "comment_text": "Comment to be deleted",
            "entity_id": str(test_entity["id"]),
            "entity_type": "test",
        }

        create_response = client.post("/comments/", json=comment_data)
        assert create_response.status_code == 200

        comment_id = create_response.json()["id"]

        # Delete the comment
        response = client.delete(f"/comments/{comment_id}")
        assert response.status_code == 200

        # Verify it's deleted
        get_response = client.get(f"/comments/{comment_id}")
        assert get_response.status_code == 404

    def test_get_comments_by_entity(self, client: TestClient, db_session):
        """Test getting comments for a specific entity"""
        # First create a test entity
        test_factory = get_factory("test")
        test_entity = test_factory.create()

        # Create multiple comments
        user_factory = get_factory("user")
        test_user = user_factory.create()

        comments_data = [
            {
                "comment_text": "First comment",
                "entity_id": str(test_entity["id"]),
                "entity_type": "test",
            },
            {
                "comment_text": "Second comment",
                "entity_id": str(test_entity["id"]),
                "entity_type": "test",
            },
            {
                "comment_text": "Third comment",
                "entity_id": str(test_entity["id"]),
                "entity_type": "test",
            },
        ]

        for comment_data in comments_data:
            response = client.post("/comments/", json=comment_data)
            assert response.status_code == 200

        # Get comments for the entity
        response = client.get(f"/comments/entity/test/{test_entity['id']}")
        assert response.status_code == 200

        comments = response.json()
        assert len(comments) == 3
        assert all(
            comment["entity_id"] == str(test_entity["id"]) for comment in comments
        )
        assert all(comment["entity_type"] == "test" for comment in comments)

    def test_invalid_entity_type(self, client: TestClient, db_session):
        """Test that invalid entity types are rejected"""
        response = client.get("/comments/entity/invalid_type/123")
        assert response.status_code == 400
        assert "Invalid entity_type" in response.json()["detail"]

    def test_comment_not_found(self, client: TestClient, db_session):
        """Test getting a non-existent comment"""
        fake_id = str(uuid4())
        response = client.get(f"/comments/{fake_id}")
        assert response.status_code == 404
        assert "Comment not found" in response.json()["detail"]
