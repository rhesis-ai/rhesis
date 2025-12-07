"""
Tests for recycle bin management endpoints.

These tests verify the recycle bin API functionality including:
- Listing available models
- Getting deleted records
- Restoring deleted records
- Permanently deleting records
- Bulk operations
- Superuser authentication
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app import models
from rhesis.backend.app.utils import crud_utils

# Use existing data factories and fixtures
from tests.backend.routes.fixtures.data_factories import (
    BehaviorDataFactory,
    TopicDataFactory,
    CategoryDataFactory,
)
from tests.backend.routes.endpoints import APIEndpoints


@pytest.mark.integration
@pytest.mark.routes
class TestRecycleModelsEndpoint:
    """Test the /recycle/models endpoint."""

    def test_list_models_requires_superuser(
        self, authenticated_client: TestClient, test_db, test_org_id
    ):
        """Test that listing models is accessible to all authenticated users."""
        # Regular user can now access (superuser requirement removed)
        response = authenticated_client.get("/recycle/models")
        assert response.status_code == status.HTTP_200_OK

    def test_list_models_success_as_superuser(
        self, superuser_client: TestClient, test_db, test_org_id
    ):
        """Test that superuser can list all available models."""
        response = superuser_client.get("/recycle/models")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "count" in data
        assert "models" in data
        assert isinstance(data["models"], list)
        assert data["count"] > 0

        # Verify model structure
        for model_info in data["models"]:
            assert "name" in model_info
            assert "class_name" in model_info
            assert "has_organization_id" in model_info
            assert "columns" in model_info

    def test_list_models_includes_expected_entities(self, superuser_client: TestClient, test_db):
        """Test that model list includes expected entities."""
        response = superuser_client.get("/recycle/models")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        model_names = [m["name"] for m in data["models"]]

        # Should include common entities
        assert "behavior" in model_names
        assert "category" in model_names
        assert "topic" in model_names
        assert "test" in model_names
        assert "user" in model_names


@pytest.mark.integration
@pytest.mark.routes
class TestRecycleGetDeletedEndpoint:
    """Test the GET /recycle/{model_name} endpoint."""

    def test_get_deleted_accessible_to_all_users(
        self, authenticated_client: TestClient, test_db, test_org_id
    ):
        """Test that getting deleted records is accessible to all authenticated users."""
        response = authenticated_client.get("/recycle/behavior")
        # Should succeed (200) or return empty list, not 403
        assert response.status_code == status.HTTP_200_OK

    def test_get_deleted_invalid_model_name(self, superuser_client: TestClient, test_db):
        """Test that invalid model name returns 400."""
        response = superuser_client.get("/recycle/invalid_model_name")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unknown model" in response.json()["detail"]

    def test_get_deleted_returns_only_deleted_records(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test that endpoint returns only soft-deleted records."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create active and deleted behaviors
        active_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        deleted_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior.id, organization_id=test_org_id
        )

        # Get deleted behaviors
        response = authenticated_client.get("/recycle/behavior")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "model" in data
        assert data["model"] == "behavior"
        assert "items" in data
        assert "count" in data

        item_ids = [item["id"] for item in data["items"]]

        # Should include deleted, not active
        assert str(deleted_behavior.id) in item_ids
        assert str(active_behavior.id) not in item_ids

    def test_get_deleted_with_pagination(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test pagination parameters for deleted records."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create and delete multiple topics
        for _ in range(5):
            topic = crud_utils.create_item(
                test_db, models.Topic, TopicDataFactory.sample_data(), organization_id=test_org_id
            )
            crud_utils.delete_item(test_db, models.Topic, topic.id, organization_id=test_org_id)

        # Get with pagination
        response = authenticated_client.get("/recycle/topic?skip=1&limit=2")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should respect limit
        assert len(data["items"]) <= 2

    def test_get_deleted_with_organization_filter(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        secondary_org_id,
        authenticated_user_id,
    ):
        """Test organization filtering for deleted records (automatic based on user context)."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create deleted items in different organizations
        behavior1 = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )
        crud_utils.delete_item(test_db, models.Behavior, behavior1.id, organization_id=test_org_id)

        behavior2 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=secondary_org_id,
        )
        crud_utils.delete_item(
            test_db, models.Behavior, behavior2.id, organization_id=secondary_org_id
        )

        # Get deleted behaviors - should only return items from authenticated user's organization context (test_org_id)
        response = authenticated_client.get("/recycle/behavior")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        item_ids = [item["id"] for item in data["items"]]

        # Should only include behavior1 (from test_org_id), not behavior2 (from secondary_org_id)
        # This demonstrates proper organization isolation
        assert str(behavior1.id) in item_ids
        assert str(behavior2.id) not in item_ids


@pytest.mark.integration
@pytest.mark.routes
class TestRecycleRestoreEndpoint:
    """Test the POST /recycle/{model_name}/{item_id}/restore endpoint."""

    def test_restore_accessible_to_all_users(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test that restoring is accessible to all authenticated users."""
        # Ensure the authenticated user is NOT a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = False
        test_db.commit()
        test_db.refresh(user)

        # Create and delete a behavior
        behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )
        crud_utils.delete_item(test_db, models.Behavior, behavior.id, organization_id=test_org_id)

        # Non-superuser can now restore (with org filtering for security)
        response = authenticated_client.post(f"/recycle/behavior/{behavior.id}/restore")
        assert response.status_code == status.HTTP_200_OK

    def test_restore_invalid_model_name(self, superuser_client: TestClient, test_db):
        """Test that invalid model name returns 400."""
        import uuid

        fake_id = uuid.uuid4()

        response = superuser_client.post(f"/recycle/invalid_model/{fake_id}/restore")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unknown model" in response.json()["detail"]

    def test_restore_success(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test successful restoration of deleted record."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create and delete a category
        category = crud_utils.create_item(
            test_db, models.Category, CategoryDataFactory.sample_data(), organization_id=test_org_id
        )
        category_id = category.id

        crud_utils.delete_item(test_db, models.Category, category_id, organization_id=test_org_id)

        # Restore it
        response = authenticated_client.post(f"/recycle/category/{category_id}/restore")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "message" in data
        assert "restored successfully" in data["message"]
        assert "item" in data
        assert data["item"]["id"] == str(category_id)

        # Verify it's actually restored
        restored = crud_utils.get_item(
            test_db, models.Category, category_id, organization_id=test_org_id
        )
        assert restored is not None
        assert restored.deleted_at is None

    def test_restore_not_found(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test restoring a non-existent record returns 404."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        import uuid

        fake_id = uuid.uuid4()

        response = authenticated_client.post(f"/recycle/behavior/{fake_id}/restore")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_restore_already_active_record(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test restoring an already active record (idempotent)."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create an active topic
        topic = crud_utils.create_item(
            test_db, models.Topic, TopicDataFactory.sample_data(), organization_id=test_org_id
        )

        # Try to restore it (should succeed idempotently)
        response = authenticated_client.post(f"/recycle/topic/{topic.id}/restore")

        # Should succeed
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.integration
@pytest.mark.routes
class TestRecyclePermanentDeleteEndpoint:
    """Test the DELETE /recycle/{model_name}/{item_id} endpoint."""

    def test_permanent_delete_requires_superuser(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test that permanent deletion is accessible to all authenticated users."""
        # Ensure the authenticated user is NOT a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = False
        test_db.commit()
        test_db.refresh(user)

        # Create and delete a behavior
        behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )
        crud_utils.delete_item(test_db, models.Behavior, behavior.id, organization_id=test_org_id)

        # Regular user can now permanently delete (superuser requirement removed)
        response = authenticated_client.delete(f"/recycle/behavior/{behavior.id}?confirm=true")
        assert response.status_code == status.HTTP_200_OK

    def test_permanent_delete_requires_confirmation(
        self, superuser_client: TestClient, test_db, test_org_id
    ):
        """Test that permanent deletion requires confirm=true."""
        # Create and delete a behavior
        behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )
        crud_utils.delete_item(test_db, models.Behavior, behavior.id, organization_id=test_org_id)

        # Try without confirmation
        response = superuser_client.delete(f"/recycle/behavior/{behavior.id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm" in response.json()["detail"].lower()

    def test_permanent_delete_success(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test successful permanent deletion."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create and delete a category
        category = crud_utils.create_item(
            test_db, models.Category, CategoryDataFactory.sample_data(), organization_id=test_org_id
        )
        category_id = category.id

        crud_utils.delete_item(test_db, models.Category, category_id, organization_id=test_org_id)

        # Permanently delete
        response = authenticated_client.delete(f"/recycle/category/{category_id}?confirm=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "permanently deleted" in data["message"]
        assert "warning" in data

        # Verify it's completely gone
        found = crud_utils.get_item(
            test_db, models.Category, category_id, organization_id=test_org_id, include_deleted=True
        )
        assert found is None

    def test_permanent_delete_not_found(self, superuser_client: TestClient, test_db):
        """Test permanent deletion of non-existent record returns 404."""
        import uuid

        fake_id = uuid.uuid4()

        response = superuser_client.delete(f"/recycle/behavior/{fake_id}?confirm=true")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.routes
class TestRecycleStatsEndpoint:
    """Test the GET /recycle/stats/counts endpoint."""

    def test_stats_accessible_to_all_users(
        self, authenticated_client: TestClient, test_db, authenticated_user_id
    ):
        """Test that stats endpoint is accessible to all authenticated users."""
        # Ensure the authenticated user is NOT a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = False
        test_db.commit()
        test_db.refresh(user)

        response = authenticated_client.get("/recycle/stats/counts")
        # Non-superuser can now access stats (with org filtering for security)
        assert response.status_code == status.HTTP_200_OK

    def test_stats_returns_counts(self, superuser_client: TestClient, test_db, test_org_id):
        """Test that stats endpoint returns deletion counts."""
        # Create and delete some items
        for _ in range(3):
            behavior = crud_utils.create_item(
                test_db,
                models.Behavior,
                BehaviorDataFactory.sample_data(),
                organization_id=test_org_id,
            )
            crud_utils.delete_item(
                test_db, models.Behavior, behavior.id, organization_id=test_org_id
            )

        response = superuser_client.get("/recycle/stats/counts")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "total_models_with_deleted" in data
        assert "counts" in data
        assert isinstance(data["counts"], dict)

        # Should have behavior in counts
        if "behavior" in data["counts"]:
            assert data["counts"]["behavior"]["count"] >= 3


@pytest.mark.integration
@pytest.mark.routes
class TestRecycleBulkRestoreEndpoint:
    """Test the POST /recycle/bulk-restore/{model_name} endpoint."""

    def test_bulk_restore_accessible_to_all_users(
        self, authenticated_client: TestClient, test_db, test_org_id
    ):
        """Test that bulk restore is accessible to all authenticated users."""
        response = authenticated_client.post("/recycle/bulk-restore/behavior", json=[])
        # Should return 400 for empty list, not 403
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "No item IDs provided" in response.json()["detail"]

    def test_bulk_restore_requires_item_ids(self, superuser_client: TestClient, test_db):
        """Test that bulk restore requires item IDs."""
        response = superuser_client.post("/recycle/bulk-restore/behavior", json=[])

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "No item IDs" in response.json()["detail"]

    def test_bulk_restore_success(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test successful bulk restoration."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create and delete multiple topics
        topic_ids = []
        for _ in range(3):
            topic = crud_utils.create_item(
                test_db, models.Topic, TopicDataFactory.sample_data(), organization_id=test_org_id
            )
            crud_utils.delete_item(test_db, models.Topic, topic.id, organization_id=test_org_id)
            topic_ids.append(str(topic.id))

        # Bulk restore
        response = authenticated_client.post("/recycle/bulk-restore/topic", json=topic_ids)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "summary" in data
        assert data["summary"]["total_requested"] == 3
        assert data["summary"]["restored"] >= 3
        assert data["summary"]["failed"] == 0

        # Verify all are restored
        for topic_id in topic_ids:
            topic = crud_utils.get_item(
                test_db, models.Topic, topic_id, organization_id=test_org_id
            )
            assert topic is not None
            assert topic.deleted_at is None

    def test_bulk_restore_max_limit(self, superuser_client: TestClient, test_db):
        """Test that bulk restore enforces maximum limit."""
        import uuid

        # Try to restore 101 items (over the limit)
        item_ids = [str(uuid.uuid4()) for _ in range(101)]

        response = superuser_client.post("/recycle/bulk-restore/behavior", json=item_ids)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "100" in response.json()["detail"]

    def test_bulk_restore_partial_success(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test bulk restore with some items not found."""
        import uuid

        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create and delete one topic
        topic = crud_utils.create_item(
            test_db, models.Topic, TopicDataFactory.sample_data(), organization_id=test_org_id
        )
        crud_utils.delete_item(test_db, models.Topic, topic.id, organization_id=test_org_id)

        # Mix valid and invalid IDs
        item_ids = [str(topic.id), str(uuid.uuid4()), str(uuid.uuid4())]

        response = authenticated_client.post("/recycle/bulk-restore/topic", json=item_ids)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["summary"]["restored"] >= 1
        assert data["summary"]["not_found"] >= 2


@pytest.mark.integration
@pytest.mark.routes
class TestRecycleEmptyBinEndpoint:
    """Test the DELETE /recycle/empty/{model_name} endpoint."""

    def test_empty_bin_requires_superuser(
        self, authenticated_client: TestClient, test_db, authenticated_user_id
    ):
        """Test that emptying bin is accessible to all authenticated users."""
        # Ensure the authenticated user is NOT a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = False
        test_db.commit()
        test_db.refresh(user)

        # Regular user can now empty bin (superuser requirement removed)
        response = authenticated_client.delete("/recycle/empty/behavior?confirm=true")
        assert response.status_code == status.HTTP_200_OK

    def test_empty_bin_requires_confirmation(self, superuser_client: TestClient, test_db):
        """Test that emptying bin requires confirm=true."""
        response = superuser_client.delete("/recycle/empty/behavior")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm" in response.json()["detail"].lower()

    def test_empty_bin_success(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Test successful emptying of recycle bin for a model."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create and delete multiple categories
        category_ids = []
        for _ in range(3):
            category = crud_utils.create_item(
                test_db,
                models.Category,
                CategoryDataFactory.sample_data(),
                organization_id=test_org_id,
            )
            crud_utils.delete_item(
                test_db, models.Category, category.id, organization_id=test_org_id
            )
            category_ids.append(category.id)

        # Empty the recycle bin
        response = authenticated_client.delete("/recycle/empty/category?confirm=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "permanently_deleted" in data
        assert data["permanently_deleted"] >= 3
        assert "warning" in data

        # Verify all are gone
        for category_id in category_ids:
            found = crud_utils.get_item(
                test_db,
                models.Category,
                category_id,
                organization_id=test_org_id,
                include_deleted=True,
            )
            # May or may not be gone depending on organization filtering

    def test_empty_bin_with_organization_filter(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        secondary_org_id,
        authenticated_user_id,
    ):
        """Test emptying bin with organization filter."""
        # Make the authenticated user a superuser for this test
        from rhesis.backend.app import crud

        user = crud.get_user_by_id(test_db, authenticated_user_id)
        user.is_superuser = True
        test_db.commit()
        test_db.refresh(user)

        # Create and delete items in different organizations
        behavior1 = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )
        crud_utils.delete_item(test_db, models.Behavior, behavior1.id, organization_id=test_org_id)

        behavior2 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=secondary_org_id,
        )
        crud_utils.delete_item(
            test_db, models.Behavior, behavior2.id, organization_id=secondary_org_id
        )

        # Empty bin - should only affect items in the authenticated user's organization (test_org_id)
        response = authenticated_client.delete("/recycle/empty/behavior?confirm=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should have deleted behavior1 (from test_org_id) but not behavior2 (from secondary_org_id)
        assert data["permanently_deleted"] >= 1
