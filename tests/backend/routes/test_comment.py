"""
💬 Comment Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for comment entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and emoji reaction testing.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using CommentDataFactory
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 😀 Comprehensive emoji reaction testing

Run with: python -m pytest tests/backend/routes/test_comment.py -v
"""

import uuid
from typing import Dict, Any
from urllib.parse import quote

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import CommentDataFactory, BehaviorDataFactory

# Initialize Faker
fake = Faker()


class CommentTestMixin:
    """Enhanced comment test mixin using factory system"""

    # Entity configuration
    entity_name = "comment"
    entity_plural = "comments"
    endpoints = APIEndpoints.COMMENTS
    name_field = "content"  # Comments use 'content' instead of 'name'

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample comment data using factory"""
        return CommentDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal comment data using factory"""
        return CommentDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return comment update data using factory"""
        return CommentDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid comment data using factory"""
        return CommentDataFactory.invalid_data()

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case comment data using factory"""
        return CommentDataFactory.edge_case_data(case_type)


# Standard entity tests - gets ALL tests from base classes
class TestCommentStandardRoutes(CommentTestMixin, BaseEntityRouteTests):
    """Complete standard comment route tests using base classes"""

    def test_delete_entity_success(self, authenticated_client: TestClient):
        """🧩🔥 Test successful entity deletion - now consistent with other routes"""
        created_entity = self.create_entity(authenticated_client)
        entity_id = created_entity[self.id_field]

        response = authenticated_client.delete(self.endpoints.remove(entity_id))

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # Comment delete now returns the deleted entity (consistent with other routes)
        assert data[self.id_field] == entity_id
        
        # Verify entity is soft-deleted by trying to get it (should return 410 GONE)
        get_response = authenticated_client.get(self.endpoints.get(entity_id))
        assert get_response.status_code == status.HTTP_410_GONE

    def test_entity_with_null_description(self, authenticated_client: TestClient):
        """🧩 Test entity with null description - skip for comments (no description field)"""
        # Comments don't have a description field, so this test is not applicable
        pytest.skip("Comments don't have a description field")

    def test_update_entity_invalid_user_id(self, authenticated_client: TestClient):
        """🧩 Test updating entity with invalid user ID - comment specific"""
        # Comments don't have user_id fields that can be updated, so skip this test
        pytest.skip("Comments don't have updatable user_id fields")


# === COMMENT-SPECIFIC TESTS (Enhanced with Factories) ===

@pytest.mark.integration
class TestCommentEntityRelationships(CommentTestMixin, BaseEntityTests):
    """Enhanced comment-entity relationship tests using factories"""

    def test_create_comment_for_behavior_entity(self, comment_factory, behavior_factory):
        """💬 Test creating comment for behavior entity (using factories)"""
        # Create behavior entity using factory (automatic cleanup)
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        behavior_id = behavior["id"]

        # Create comment for the behavior
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior_id,
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)

        assert comment["entity_id"] == behavior_id
        assert comment["entity_type"] == "Behavior"
        assert comment["content"] == comment_data["content"]
        assert comment["id"] is not None
        assert comment["user_id"] is not None

    def test_get_comments_by_entity(self, comment_factory, behavior_factory):
        """💬 Test getting comments for specific entity"""
        # Create behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        behavior_id = behavior["id"]

        # Create multiple comments for the behavior
        comment_data_1 = CommentDataFactory.sample_data(
            entity_id=behavior_id,
            entity_type="Behavior"
        )
        comment_data_2 = CommentDataFactory.sample_data(
            entity_id=behavior_id,
            entity_type="Behavior"
        )

        comment1 = comment_factory.create(comment_data_1)
        comment2 = comment_factory.create(comment_data_2)

        # Get comments by entity
        response = comment_factory.client.get(
            self.endpoints.by_entity("Behavior", behavior_id)
        )

        assert response.status_code == status.HTTP_200_OK
        comments = response.json()
        assert isinstance(comments, list)
        assert len(comments) == 2

        # Verify all comments belong to the behavior
        comment_ids = {c["id"] for c in comments}
        assert comment1["id"] in comment_ids
        assert comment2["id"] in comment_ids

        for comment in comments:
            assert comment["entity_id"] == behavior_id
            assert comment["entity_type"] == "Behavior"

    def test_get_comments_by_entity_empty(self, comment_factory, behavior_factory):
        """💬 Test getting comments for entity with no comments"""
        # Create behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        behavior_id = behavior["id"]

        # Get comments by entity (should be empty)
        response = comment_factory.client.get(
            self.endpoints.by_entity("Behavior", behavior_id)
        )

        assert response.status_code == status.HTTP_200_OK
        comments = response.json()
        assert isinstance(comments, list)
        assert len(comments) == 0

    def test_get_comments_by_invalid_entity_type(self, comment_factory):
        """💬 Test getting comments with invalid entity type"""
        fake_entity_id = str(uuid.uuid4())

        response = comment_factory.client.get(
            self.endpoints.by_entity("InvalidEntity", fake_entity_id)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_data = response.json()
        assert "Invalid entity_type" in error_data["detail"]
        assert "Must be one of:" in error_data["detail"]


@pytest.mark.integration
class TestCommentEmojiReactions(CommentTestMixin, BaseEntityTests):
    """Enhanced comment emoji reaction tests using factories"""

    def test_add_emoji_reaction(self, comment_factory, behavior_factory):
        """😀 Test adding emoji reaction to comment"""
        # Create behavior and comment
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior["id"],
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)
        comment_id = comment["id"]

        # Add emoji reaction
        emoji = "🚀"
        response = comment_factory.client.post(
            self.endpoints.add_emoji_reaction(comment_id, emoji)
        )

        assert response.status_code == status.HTTP_200_OK
        updated_comment = response.json()

        # Verify emoji was added
        assert "emojis" in updated_comment
        assert emoji in updated_comment["emojis"]
        assert len(updated_comment["emojis"][emoji]) == 1

        # Verify user info in emoji reaction
        reaction = updated_comment["emojis"][emoji][0]
        assert "user_id" in reaction
        assert "user_name" in reaction
        assert reaction["user_id"] is not None

    def test_add_multiple_emoji_reactions(self, comment_factory, behavior_factory):
        """😀 Test adding multiple emoji reactions to comment"""
        # Create behavior and comment
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior["id"],
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)
        comment_id = comment["id"]

        # Add multiple emoji reactions
        emojis = ["🚀", "👍", "❤️"]
        for emoji in emojis:
            response = comment_factory.client.post(
                self.endpoints.add_emoji_reaction(comment_id, emoji)
            )
            assert response.status_code == status.HTTP_200_OK

        # Get final comment state
        response = comment_factory.client.get(self.endpoints.get(comment_id))
        assert response.status_code == status.HTTP_200_OK
        final_comment = response.json()

        # Verify all emojis were added
        assert "emojis" in final_comment
        for emoji in emojis:
            assert emoji in final_comment["emojis"]
            assert len(final_comment["emojis"][emoji]) == 1

    def test_add_emoji_reaction_duplicate_user(self, comment_factory, behavior_factory):
        """😀 Test adding same emoji reaction twice (should not duplicate)"""
        # Create behavior and comment
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior["id"],
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)
        comment_id = comment["id"]

        emoji = "🚀"

        # Add emoji reaction first time
        response1 = comment_factory.client.post(
            self.endpoints.add_emoji_reaction(comment_id, emoji)
        )
        assert response1.status_code == status.HTTP_200_OK

        # Add same emoji reaction second time
        response2 = comment_factory.client.post(
            self.endpoints.add_emoji_reaction(comment_id, emoji)
        )
        assert response2.status_code == status.HTTP_200_OK

        updated_comment = response2.json()

        # Verify only one reaction exists (no duplicates)
        assert emoji in updated_comment["emojis"]
        assert len(updated_comment["emojis"][emoji]) == 1

    def test_remove_emoji_reaction(self, comment_factory, behavior_factory):
        """😀 Test removing emoji reaction from comment"""
        # Create behavior and comment
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior["id"],
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)
        comment_id = comment["id"]

        emoji = "🚀"

        # Add emoji reaction
        response = comment_factory.client.post(
            self.endpoints.add_emoji_reaction(comment_id, emoji)
        )
        assert response.status_code == status.HTTP_200_OK

        # Remove emoji reaction
        response = comment_factory.client.delete(
            self.endpoints.remove_emoji_reaction(comment_id, emoji)
        )
        assert response.status_code == status.HTTP_200_OK

        updated_comment = response.json()

        # Verify emoji was removed
        if "emojis" in updated_comment and emoji in updated_comment["emojis"]:
            assert len(updated_comment["emojis"][emoji]) == 0

    def test_add_emoji_reaction_to_nonexistent_comment(self, comment_factory):
        """😀 Test adding emoji reaction to non-existent comment"""
        fake_comment_id = str(uuid.uuid4())
        emoji = "🚀"

        response = comment_factory.client.post(
            self.endpoints.add_emoji_reaction(fake_comment_id, emoji)
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error_data = response.json()
        assert "Comment not found" in error_data["detail"]

    def test_remove_emoji_reaction_from_nonexistent_comment(self, comment_factory):
        """😀 Test removing emoji reaction from non-existent comment"""
        fake_comment_id = str(uuid.uuid4())
        emoji = "🚀"

        response = comment_factory.client.delete(
            self.endpoints.remove_emoji_reaction(fake_comment_id, emoji)
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error_data = response.json()
        assert "Comment not found" in error_data["detail"]

    def test_emoji_reaction_with_special_characters(self, comment_factory, behavior_factory):
        """😀 Test emoji reactions with special Unicode characters"""
        # Create behavior and comment
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior["id"],
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)
        comment_id = comment["id"]

        # Test various emoji types
        emojis = ["🎉", "🔥", "💯", "👨‍💻", "🚀"]

        for emoji in emojis:
            # URL encode the emoji for the API call
            encoded_emoji = quote(emoji, safe='')
            response = comment_factory.client.post(
                f"/comments/{comment_id}/emoji/{encoded_emoji}"
            )
            assert response.status_code == status.HTTP_200_OK

            updated_comment = response.json()
            assert emoji in updated_comment["emojis"]


@pytest.mark.integration
class TestCommentValidationAndEdgeCases(CommentTestMixin, BaseEntityTests):
    """Enhanced comment validation and edge case tests using factories"""

    def test_create_comment_with_long_content(self, comment_factory, behavior_factory):
        """💬 Test creating comment with long content"""
        # Create behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

        # Create comment with long content
        comment_data = CommentDataFactory.edge_case_data("long_content")
        comment_data["entity_id"] = behavior["id"]
        comment_data["entity_type"] = "Behavior"

        comment = comment_factory.create(comment_data)

        assert comment["content"] == comment_data["content"]
        assert len(comment["content"]) > 1000  # Verify it's actually long

    def test_create_comment_with_special_characters(self, comment_factory, behavior_factory):
        """💬 Test creating comment with special characters and emojis"""
        # Create behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

        # Create comment with special characters
        comment_data = CommentDataFactory.edge_case_data("special_chars")
        comment_data["entity_id"] = behavior["id"]
        comment_data["entity_type"] = "Behavior"

        comment = comment_factory.create(comment_data)

        assert comment["content"] == comment_data["content"]
        assert "💬" in comment["content"]
        assert "émojis" in comment["content"]

    def test_create_comment_with_unicode_content(self, comment_factory, behavior_factory):
        """💬 Test creating comment with Unicode content"""
        # Create behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

        # Create comment with Unicode content
        comment_data = CommentDataFactory.edge_case_data("unicode")
        comment_data["entity_id"] = behavior["id"]
        comment_data["entity_type"] = "Behavior"

        comment = comment_factory.create(comment_data)

        assert comment["content"] == comment_data["content"]
        assert "测试" in comment["content"]
        assert "тест" in comment["content"]
        assert "テスト" in comment["content"]

    def test_create_comment_with_empty_content(self, comment_factory, behavior_factory):
        """💬 Test creating comment with empty content (currently allows empty strings)"""
        # Create behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

        # Try to create comment with empty content
        comment_data = CommentDataFactory.edge_case_data("empty_content")
        comment_data["entity_id"] = behavior["id"]
        comment_data["entity_type"] = "Behavior"

        # Currently the backend allows empty content (Pydantic doesn't validate empty strings)
        # This test documents the current behavior - if validation is added later, update this test
        response = comment_factory.client.post(comment_factory.endpoints.create, json=comment_data)
        assert response.status_code == status.HTTP_200_OK

        # Verify empty content was saved
        comment = response.json()
        assert comment["content"] == ""

    def test_create_comment_with_invalid_entity_type(self, comment_factory):
        """💬 Test creating comment with invalid entity type"""
        comment_data = CommentDataFactory.sample_data()
        comment_data["entity_type"] = "InvalidEntityType"

        response = comment_factory.client.post(comment_factory.endpoints.create, json=comment_data)
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]

    def test_create_comment_with_nonexistent_entity_id(self, comment_factory):
        """💬 Test creating comment for non-existent entity"""
        comment_data = CommentDataFactory.sample_data()
        comment_data["entity_id"] = str(uuid.uuid4())  # Non-existent entity
        comment_data["entity_type"] = "Behavior"

        # This might succeed in creation but the entity won't exist
        # The behavior depends on whether the system validates entity existence
        comment = comment_factory.create(comment_data)
        assert comment["entity_id"] == comment_data["entity_id"]

    def test_update_comment_authorization(self, comment_factory, behavior_factory):
        """💬 Test comment update authorization (users can only update their own comments)"""
        # Create behavior and comment
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior["id"],
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)

        # Update comment (should work since same user)
        update_data = CommentDataFactory.update_data()
        updated_comment = comment_factory.update(comment["id"], update_data)

        assert updated_comment["content"] == update_data["content"]
        assert updated_comment["id"] == comment["id"]

    def test_delete_comment_authorization(self, comment_factory, behavior_factory):
        """💬 Test comment delete authorization (users can only delete their own comments)"""
        # Create behavior and comment
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior["id"],
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)

        # Delete comment (should work since same user)
        result = comment_factory.delete(comment["id"])

        # Verify deletion returns the deleted comment (consistent with other routes)
        assert result["id"] == comment["id"]
        assert result["content"] == comment["content"]


@pytest.mark.integration
class TestCommentPerformance(CommentTestMixin, BaseEntityTests):
    """Enhanced comment performance tests using factories"""

    def test_create_multiple_comments_performance(self, comment_factory, behavior_factory):
        """💬 Test creating multiple comments for performance"""
        # Create behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

        # Create batch of comments with consistent data
        comment_data_batch = CommentDataFactory.batch_data(
            count=10,
            variation=False,  # Use consistent data to avoid random entity types
            entity_type="Behavior"
        )

        comments = []
        for comment_data in comment_data_batch:
            comment_data["entity_id"] = behavior["id"]
            comment = comment_factory.create(comment_data)
            comments.append(comment)

        assert len(comments) == 10
        for comment in comments:
            assert comment["entity_id"] == behavior["id"]
            assert comment["entity_type"] == "Behavior"

    def test_comment_pagination_performance(self, comment_factory, behavior_factory):
        """💬 Test comment pagination with large datasets"""
        # Create behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

        # Create multiple comments with consistent entity type
        comment_count = 25
        comment_data_batch = CommentDataFactory.batch_data(
            count=comment_count,
            variation=False,  # Don't vary entity types - use consistent data
            entity_type="Behavior"
        )

        for comment_data in comment_data_batch:
            comment_data["entity_id"] = behavior["id"]
            comment_data["entity_type"] = "Behavior"  # Ensure consistent entity type
            comment_factory.create(comment_data)

        # Test pagination
        response = comment_factory.client.get(
            self.endpoints.by_entity("Behavior", behavior["id"]),
            params={"limit": 10, "skip": 0}
        )

        assert response.status_code == status.HTTP_200_OK
        first_page = response.json()
        assert len(first_page) == 10

        # Get second page
        response = comment_factory.client.get(
            self.endpoints.by_entity("Behavior", behavior["id"]),
            params={"limit": 10, "skip": 10}
        )

        assert response.status_code == status.HTTP_200_OK
        second_page = response.json()
        assert len(second_page) == 10

        # Verify no overlap
        first_page_ids = {c["id"] for c in first_page}
        second_page_ids = {c["id"] for c in second_page}
        assert len(first_page_ids.intersection(second_page_ids)) == 0

    def test_emoji_reaction_performance(self, comment_factory, behavior_factory):
        """😀 Test emoji reaction performance with multiple reactions"""
        # Create behavior and comment
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior["id"],
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)
        comment_id = comment["id"]

        # Add many different emoji reactions
        emojis = ["🚀", "👍", "❤️", "🎉", "🔥", "💯", "✨", "⭐", "👏", "🙌"]

        for emoji in emojis:
            response = comment_factory.client.post(
                self.endpoints.add_emoji_reaction(comment_id, emoji)
            )
            assert response.status_code == status.HTTP_200_OK

        # Verify all reactions were added
        response = comment_factory.client.get(self.endpoints.get(comment_id))
        assert response.status_code == status.HTTP_200_OK
        final_comment = response.json()

        assert len(final_comment["emojis"]) == len(emojis)
        for emoji in emojis:
            assert emoji in final_comment["emojis"]

    def test_delete_comment_clears_task_references(self, comment_factory, behavior_factory, authenticated_client):
        """🗑️ Test that deleting a comment clears comment_id from associated tasks"""
        # Create a behavior entity
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        behavior_id = behavior["id"]

        # Create a comment for the behavior
        comment_data = CommentDataFactory.sample_data(
            entity_id=behavior_id,
            entity_type="Behavior"
        )
        comment = comment_factory.create(comment_data)
        comment_id = comment["id"]

        # Get a default status for the task
        status_response = authenticated_client.get("/statuses/")
        assert status_response.status_code == status.HTTP_200_OK
        statuses = status_response.json()
        assert len(statuses) > 0
        default_status_id = statuses[0]["id"]

        # Create a task that references this comment in task_metadata
        task_data = {
            "title": "Test task with comment reference",
            "description": "This task references a comment",
            "status_id": default_status_id,
            "entity_id": behavior_id,
            "entity_type": "Behavior",
            "task_metadata": {
                "comment_id": comment_id,
                "some_other_field": "should remain"
            }
        }

        task_response = authenticated_client.post("/tasks/", json=task_data)
        assert task_response.status_code == status.HTTP_200_OK
        task = task_response.json()
        task_id = task["id"]

        # Verify the task has the comment_id in metadata
        assert task["task_metadata"]["comment_id"] == comment_id
        assert task["task_metadata"]["some_other_field"] == "should remain"

        # Delete the comment
        delete_response = comment_factory.client.delete(
            self.endpoints.remove(comment_id)
        )
        assert delete_response.status_code == status.HTTP_200_OK

        # Retrieve the task and verify comment_id is cleared from task_metadata
        task_response = authenticated_client.get(f"/tasks/{task_id}")
        assert task_response.status_code == status.HTTP_200_OK
        updated_task = task_response.json()

        # The comment_id should be removed, but other fields should remain
        assert "comment_id" not in updated_task["task_metadata"]
        assert updated_task["task_metadata"]["some_other_field"] == "should remain"
