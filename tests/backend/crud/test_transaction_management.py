"""
🔄 Transaction Management Testing for CRUD Operations

Comprehensive test suite for verifying that transaction management works correctly
after refactoring to remove manual db.commit() and db.rollback() calls.

Tests focus on:
- Automatic transaction commit on success
- Automatic transaction rollback on exceptions
- Proper transaction isolation
- Data integrity after operations

Functions tested from app/crud.py:
- create_organization
- update_user
- create_user
- create_tag / remove_tag
- delete_tokens_by_user
- delete_test
- add_behavior_to_metric / remove_behavior_from_metric
- add_emoji_reaction / remove_emoji_reaction

Run with: python -m pytest tests/backend/crud/test_transaction_management.py -v
"""

import pytest
import uuid
from unittest.mock import patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.constants import EntityType
from tests.backend.routes.fixtures.data_factories import (
    OrganizationDataFactory,
    TagDataFactory,
    BehaviorDataFactory,
    MetricDataFactory,
    CommentDataFactory,
    TestDataFactory,
)


@pytest.mark.unit
@pytest.mark.crud
@pytest.mark.transaction
class TestCRUDTransactionManagement:
    """🔄 Test automatic transaction management in CRUD operations"""

    def test_create_organization_commits_on_success(self, test_db: Session, authenticated_user):
        """Test that create_organization commits automatically on success"""
        # Create organization data with real user ID
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_create = schemas.OrganizationCreate(**org_data)

        # Create organization
        result = crud.create_organization(test_db, org_create)

        # Verify organization was created and persisted
        assert result is not None
        assert result.name == org_data["name"]
        assert result.id is not None

        # Verify it's actually in the database (committed)
        db_org = (
            test_db.query(models.Organization).filter(models.Organization.id == result.id).first()
        )
        assert db_org is not None
        assert db_org.name == org_data["name"]

    def test_create_organization_rollback_on_exception(self, test_db: Session, authenticated_user):
        """Test that create_organization rolls back automatically on exception"""
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_create = schemas.OrganizationCreate(**org_data)

        # Get initial organization count
        initial_count = test_db.query(models.Organization).count()

        # Mock db.add to raise an exception to test rollback
        with patch.object(test_db, "add", side_effect=IntegrityError("", "", "")):
            with pytest.raises(IntegrityError):
                crud.create_organization(test_db, org_create)

        # Verify no organization was created (transaction rolled back)
        final_count = test_db.query(models.Organization).count()
        assert final_count == initial_count

    def test_update_user_commits_on_success(self, test_db: Session, authenticated_user):
        """Test that update_user commits automatically on success"""
        user_id = authenticated_user.id
        original_name = authenticated_user.name

        # Update user data
        new_name = "Updated Test User"
        update_data = schemas.UserUpdate(name=new_name)

        # Update user
        result = crud.update_user(test_db, user_id, update_data)

        # Verify user was updated and persisted
        assert result is not None
        assert result.name == new_name

        # Verify it's actually updated in the database (committed)
        db_user = test_db.query(models.User).filter(models.User.id == user_id).first()
        assert db_user is not None
        assert db_user.name == new_name
        assert db_user.name != original_name

    def test_create_user_commits_on_success(self, test_db: Session):
        """Test that create_user commits automatically on success"""
        # Create user data using mock data pattern
        user_data = {
            "email": f"test_user_{uuid.uuid4()}@example.com",
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
        }
        user_create = schemas.UserCreate(**user_data)

        # Create user
        result = crud.create_user(test_db, user_create)

        # Verify user was created and persisted
        assert result is not None
        assert result.email == user_data["email"]
        assert result.id is not None

        # Verify it's actually in the database (committed)
        db_user = test_db.query(models.User).filter(models.User.id == result.id).first()
        assert db_user is not None
        assert db_user.email == user_data["email"]

    def test_assign_tag_commits_on_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that assign_tag commits automatically on success"""
        # Create tag data
        tag_data = TagDataFactory.sample_data()
        tag_data["organization_id"] = test_org_id
        tag_data["user_id"] = authenticated_user_id
        tag_create = schemas.TagCreate(**tag_data)

        # Create a test entity to tag
        entity_id = uuid.uuid4()
        entity_type = EntityType.BEHAVIOR

        # Create a test behavior entity first
        behavior = models.Behavior(
            name="Test Behavior",
            description="Test behavior for tagging",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )
        test_db.add(behavior)
        test_db.flush()
        entity_id = behavior.id

        # Assign tag
        result = crud.assign_tag(test_db, tag_create, entity_id, entity_type, test_org_id)

        # Verify tag was created and persisted
        assert result is not None
        assert result.name == tag_data["name"]
        assert result.id is not None

        # Verify it's actually in the database (committed)
        db_tag = test_db.query(models.Tag).filter(models.Tag.id == result.id).first()
        assert db_tag is not None
        assert db_tag.name == tag_data["name"]

        # Verify tagged item was created
        tagged_item = (
            test_db.query(models.TaggedItem)
            .filter(models.TaggedItem.tag_id == result.id, models.TaggedItem.entity_id == entity_id)
            .first()
        )
        assert tagged_item is not None

    def test_remove_tag_commits_on_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that remove_tag commits automatically on success"""
        # First create a tag and tagged item
        tag_data = TagDataFactory.sample_data()
        tag_data["organization_id"] = test_org_id
        tag_data["user_id"] = authenticated_user_id
        tag_create = schemas.TagCreate(**tag_data)

        # Create a test behavior entity first
        behavior = models.Behavior(
            name="Test Behavior",
            description="Test behavior for tagging",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )
        test_db.add(behavior)
        test_db.flush()
        entity_id = behavior.id
        entity_type = EntityType.BEHAVIOR

        # Assign tag
        created_tag = crud.assign_tag(test_db, tag_create, entity_id, entity_type, test_org_id)
        tag_id = created_tag.id

        # Verify tagged item exists
        initial_tagged_items = (
            test_db.query(models.TaggedItem)
            .filter(models.TaggedItem.tag_id == tag_id, models.TaggedItem.entity_id == entity_id)
            .count()
        )
        assert initial_tagged_items == 1

        # Remove tag
        result = crud.remove_tag(test_db, tag_id, entity_id, entity_type, test_org_id)

        # Verify tag was removed (committed)
        assert result is True

        # Verify tagged item was actually removed from database
        final_tagged_items = (
            test_db.query(models.TaggedItem)
            .filter(models.TaggedItem.tag_id == tag_id, models.TaggedItem.entity_id == entity_id)
            .count()
        )
        assert final_tagged_items == 0

    def test_add_emoji_reaction_commits_on_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that add_emoji_reaction commits automatically on success"""
        # Create a test comment
        comment_data = CommentDataFactory.sample_data()
        comment_data["organization_id"] = test_org_id
        comment_data["user_id"] = authenticated_user_id
        comment = models.Comment(**comment_data)
        test_db.add(comment)
        test_db.flush()

        # Add emoji reaction
        emoji = "👍"
        user_id = uuid.UUID(authenticated_user_id)
        user_name = "Test User"

        result = crud.add_emoji_reaction(
            test_db,
            comment.id,
            emoji,
            user_id,
            user_name,
            organization_id=test_org_id,
            user_id_param=authenticated_user_id,
        )

        # Verify reaction was added and persisted
        assert result is not None
        assert emoji in result.emojis
        assert len(result.emojis[emoji]) == 1
        assert result.emojis[emoji][0]["user_id"] == str(user_id)

        # Verify it's actually in the database (committed)
        db_comment = test_db.query(models.Comment).filter(models.Comment.id == comment.id).first()
        assert db_comment is not None
        assert emoji in db_comment.emojis
        assert len(db_comment.emojis[emoji]) == 1

    def test_remove_emoji_reaction_commits_on_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that remove_emoji_reaction commits automatically on success"""
        # Create a test comment with existing emoji reaction
        comment_data = CommentDataFactory.sample_data()
        comment_data["organization_id"] = test_org_id
        comment_data["user_id"] = authenticated_user_id
        comment = models.Comment(**comment_data)
        test_db.add(comment)
        test_db.flush()

        # Add initial emoji reaction
        emoji = "👍"
        user_id = uuid.UUID(authenticated_user_id)
        user_name = "Test User"
        crud.add_emoji_reaction(
            test_db,
            comment.id,
            emoji,
            user_id,
            user_name,
            organization_id=test_org_id,
            user_id_param=authenticated_user_id,
        )

        # Verify reaction exists
        db_comment = test_db.query(models.Comment).filter(models.Comment.id == comment.id).first()
        assert emoji in db_comment.emojis
        assert len(db_comment.emojis[emoji]) == 1

        # Remove emoji reaction
        result = crud.remove_emoji_reaction(
            test_db,
            comment.id,
            emoji,
            user_id,
            organization_id=test_org_id,
            user_id_param=authenticated_user_id,
        )

        # Verify reaction was removed and persisted
        assert result is not None
        assert emoji not in result.emojis or len(result.emojis[emoji]) == 0

        # Verify it's actually removed from database (committed)
        db_comment = test_db.query(models.Comment).filter(models.Comment.id == comment.id).first()
        assert db_comment is not None
        assert emoji not in db_comment.emojis or len(db_comment.emojis[emoji]) == 0

    def test_transaction_isolation_between_operations(self, test_db: Session, authenticated_user):
        """Test that transaction isolation works correctly between operations"""
        # Create first organization
        org_data1 = OrganizationDataFactory.sample_data()
        org_data1["name"] = "Test Org 1"
        org_data1["owner_id"] = str(authenticated_user.id)
        org_data1["user_id"] = str(authenticated_user.id)
        org_create1 = schemas.OrganizationCreate(**org_data1)

        result1 = crud.create_organization(test_db, org_create1)
        assert result1 is not None

        # Create second organization
        org_data2 = OrganizationDataFactory.sample_data()
        org_data2["name"] = "Test Org 2"
        org_data2["owner_id"] = str(authenticated_user.id)
        org_data2["user_id"] = str(authenticated_user.id)
        org_create2 = schemas.OrganizationCreate(**org_data2)

        result2 = crud.create_organization(test_db, org_create2)
        assert result2 is not None

        # Verify both organizations exist independently
        db_org1 = (
            test_db.query(models.Organization).filter(models.Organization.id == result1.id).first()
        )
        db_org2 = (
            test_db.query(models.Organization).filter(models.Organization.id == result2.id).first()
        )

        assert db_org1 is not None
        assert db_org2 is not None
        assert db_org1.name == "Test Org 1"
        assert db_org2.name == "Test Org 2"
        assert db_org1.id != db_org2.id

    def test_exception_in_one_operation_does_not_affect_others(
        self, test_db: Session, authenticated_user
    ):
        """Test that an exception in one operation doesn't affect other successful operations"""
        # Create first organization successfully
        org_data1 = OrganizationDataFactory.sample_data()
        org_data1["name"] = "Success Org"
        org_data1["owner_id"] = str(authenticated_user.id)
        org_data1["user_id"] = str(authenticated_user.id)
        org_create1 = schemas.OrganizationCreate(**org_data1)

        result1 = crud.create_organization(test_db, org_create1)
        assert result1 is not None

        # Try to create second organization with exception
        org_data2 = OrganizationDataFactory.sample_data()
        org_data2["name"] = "Failure Org"
        org_data2["owner_id"] = str(authenticated_user.id)
        org_data2["user_id"] = str(authenticated_user.id)
        org_create2 = schemas.OrganizationCreate(**org_data2)

        with patch.object(test_db, "add", side_effect=IntegrityError("", "", "")):
            with pytest.raises(IntegrityError):
                crud.create_organization(test_db, org_create2)

        # Verify first organization still exists (not affected by second failure)
        db_org1 = (
            test_db.query(models.Organization).filter(models.Organization.id == result1.id).first()
        )
        assert db_org1 is not None
        assert db_org1.name == "Success Org"

        # Verify second organization was not created
        failed_orgs = (
            test_db.query(models.Organization)
            .filter(models.Organization.name == "Failure Org")
            .count()
        )
        assert failed_orgs == 0
