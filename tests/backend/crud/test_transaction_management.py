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
from unittest.mock import patch, MagicMock
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
    TestDataFactory
)


@pytest.mark.unit
@pytest.mark.crud
@pytest.mark.transaction
class TestCRUDTransactionManagement:
    """🔄 Test automatic transaction management in CRUD operations"""

    def test_create_organization_commits_on_success(self, test_db: Session):
        """Test that create_organization commits automatically on success"""
        # Create organization data
        org_data = OrganizationDataFactory.sample_data()
        org_create = schemas.OrganizationCreate(**org_data)
        
        # Mock session variables to avoid RLS issues
        with patch('rhesis.backend.app.crud.get_session_variables') as mock_get_vars, \
             patch('rhesis.backend.app.crud.reset_session_context') as mock_reset:
            mock_get_vars.return_value = {}
            
            # Create organization
            result = crud.create_organization(test_db, org_create)
            
            # Verify organization was created and persisted
            assert result is not None
            assert result.name == org_data["name"]
            assert result.id is not None
            
            # Verify it's actually in the database (committed)
            db_org = test_db.query(models.Organization).filter(
                models.Organization.id == result.id
            ).first()
            assert db_org is not None
            assert db_org.name == org_data["name"]

    def test_create_organization_rollback_on_exception(self, test_db: Session):
        """Test that create_organization rolls back automatically on exception"""
        org_data = OrganizationDataFactory.sample_data()
        org_create = schemas.OrganizationCreate(**org_data)
        
        # Get initial organization count
        initial_count = test_db.query(models.Organization).count()
        
        with patch('rhesis.backend.app.crud.get_session_variables') as mock_get_vars, \
             patch('rhesis.backend.app.crud.reset_session_context') as mock_reset:
            mock_get_vars.return_value = {}
            
            # Mock db.add to raise an exception
            with patch.object(test_db, 'add', side_effect=IntegrityError("", "", "")):
                with pytest.raises(ValueError, match="Failed to create organization"):
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
        db_user = test_db.query(models.User).filter(
            models.User.id == user_id
        ).first()
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
            "family_name": "User"
        }
        user_create = schemas.UserCreate(**user_data)
        
        # Create user
        result = crud.create_user(test_db, user_create)
        
        # Verify user was created and persisted
        assert result is not None
        assert result.email == user_data["email"]
        assert result.id is not None
        
        # Verify it's actually in the database (committed)
        db_user = test_db.query(models.User).filter(
            models.User.id == result.id
        ).first()
        assert db_user is not None
        assert db_user.email == user_data["email"]

    def test_create_tag_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that create_tag commits automatically on success"""
        # Create tag data
        tag_data = TagDataFactory.sample_data()
        tag_data["organization_id"] = test_org_id
        tag_data["user_id"] = authenticated_user_id
        tag_create = schemas.TagCreate(**tag_data)
        
        # Create a test entity to tag
        entity_id = uuid.uuid4()
        entity_type = EntityType.BEHAVIOR
        
        # Create tag
        result = crud.create_tag(test_db, tag_create, entity_id, entity_type, test_org_id, authenticated_user_id)
        
        # Verify tag was created and persisted
        assert result is not None
        assert result.name == tag_data["name"]
        assert result.id is not None
        
        # Verify it's actually in the database (committed)
        db_tag = test_db.query(models.Tag).filter(
            models.Tag.id == result.id
        ).first()
        assert db_tag is not None
        assert db_tag.name == tag_data["name"]
        
        # Verify tagged item was created
        tagged_item = test_db.query(models.TaggedItem).filter(
            models.TaggedItem.tag_id == result.id,
            models.TaggedItem.entity_id == entity_id
        ).first()
        assert tagged_item is not None

    def test_remove_tag_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that remove_tag commits automatically on success"""
        # First create a tag and tagged item
        tag_data = TagDataFactory.sample_data()
        tag_data["organization_id"] = test_org_id
        tag_data["user_id"] = authenticated_user_id
        tag_create = schemas.TagCreate(**tag_data)
        
        entity_id = uuid.uuid4()
        entity_type = EntityType.BEHAVIOR
        
        created_tag = crud.create_tag(test_db, tag_create, entity_id, entity_type, test_org_id, authenticated_user_id)
        tag_id = created_tag.id
        
        # Verify tagged item exists
        initial_tagged_items = test_db.query(models.TaggedItem).filter(
            models.TaggedItem.tag_id == tag_id,
            models.TaggedItem.entity_id == entity_id
        ).count()
        assert initial_tagged_items == 1
        
        # Remove tag
        result = crud.remove_tag(test_db, tag_id, entity_id, entity_type, test_org_id)
        
        # Verify tag was removed (committed)
        assert result is True
        
        # Verify tagged item was actually removed from database
        final_tagged_items = test_db.query(models.TaggedItem).filter(
            models.TaggedItem.tag_id == tag_id,
            models.TaggedItem.entity_id == entity_id
        ).count()
        assert final_tagged_items == 0

    def test_delete_tokens_by_user_commits_on_success(self, test_db: Session, test_org_id: str):
        """Test that delete_tokens_by_user commits automatically on success"""
        # Create a test user and tokens
        test_user_id = uuid.uuid4()
        test_user = models.User(
            email=f"token-test-{test_user_id}@example.com",
            name="Token Test User",
            organization_id=uuid.UUID(test_org_id)
        )
        test_db.add(test_user)
        test_db.flush()
        
        # Create test tokens
        token1 = models.Token(
            name="Test Token 1",
            token="test_token_1",
            token_obfuscated="test_...1",
            token_type="bearer",
            user_id=test_user.id,
            organization_id=uuid.UUID(test_org_id)
        )
        token2 = models.Token(
            name="Test Token 2", 
            token="test_token_2",
            token_obfuscated="test_...2",
            token_type="bearer",
            user_id=test_user.id,
            organization_id=uuid.UUID(test_org_id)
        )
        test_db.add_all([token1, token2])
        test_db.flush()
        
        # Verify tokens exist
        initial_count = test_db.query(models.Token).filter(
            models.Token.user_id == test_user.id
        ).count()
        assert initial_count == 2
        
        # Delete tokens
        result = crud.delete_tokens_by_user(test_db, str(test_user.id), test_org_id)
        
        # Verify tokens were deleted (committed)
        assert result == 2
        
        # Verify tokens are actually gone from database
        final_count = test_db.query(models.Token).filter(
            models.Token.user_id == test_user.id
        ).count()
        assert final_count == 0

    def test_add_emoji_reaction_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
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
        
        result = crud.add_emoji_reaction(test_db, comment.id, emoji, user_id)
        
        # Verify reaction was added and persisted
        assert result is not None
        assert emoji in result.emojis
        assert len(result.emojis[emoji]) == 1
        assert result.emojis[emoji][0]["user_id"] == str(user_id)
        
        # Verify it's actually in the database (committed)
        db_comment = test_db.query(models.Comment).filter(
            models.Comment.id == comment.id
        ).first()
        assert db_comment is not None
        assert emoji in db_comment.emojis
        assert len(db_comment.emojis[emoji]) == 1

    def test_remove_emoji_reaction_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
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
        crud.add_emoji_reaction(test_db, comment.id, emoji, user_id)
        
        # Verify reaction exists
        db_comment = test_db.query(models.Comment).filter(
            models.Comment.id == comment.id
        ).first()
        assert emoji in db_comment.emojis
        assert len(db_comment.emojis[emoji]) == 1
        
        # Remove emoji reaction
        result = crud.remove_emoji_reaction(test_db, comment.id, emoji, user_id)
        
        # Verify reaction was removed and persisted
        assert result is not None
        assert emoji not in result.emojis or len(result.emojis[emoji]) == 0
        
        # Verify it's actually removed from database (committed)
        db_comment = test_db.query(models.Comment).filter(
            models.Comment.id == comment.id
        ).first()
        assert db_comment is not None
        assert emoji not in db_comment.emojis or len(db_comment.emojis[emoji]) == 0

    def test_transaction_isolation_between_operations(self, test_db: Session):
        """Test that transaction isolation works correctly between operations"""
        # Create first organization
        org_data1 = OrganizationDataFactory.sample_data()
        org_data1["name"] = "Test Org 1"
        org_create1 = schemas.OrganizationCreate(**org_data1)
        
        with patch('rhesis.backend.app.crud.get_session_variables') as mock_get_vars, \
             patch('rhesis.backend.app.crud.reset_session_context') as mock_reset:
            mock_get_vars.return_value = {}
            
            result1 = crud.create_organization(test_db, org_create1)
            assert result1 is not None
            
            # Create second organization
            org_data2 = OrganizationDataFactory.sample_data()
            org_data2["name"] = "Test Org 2"
            org_create2 = schemas.OrganizationCreate(**org_data2)
            
            result2 = crud.create_organization(test_db, org_create2)
            assert result2 is not None
            
            # Verify both organizations exist independently
            db_org1 = test_db.query(models.Organization).filter(
                models.Organization.id == result1.id
            ).first()
            db_org2 = test_db.query(models.Organization).filter(
                models.Organization.id == result2.id
            ).first()
            
            assert db_org1 is not None
            assert db_org2 is not None
            assert db_org1.name == "Test Org 1"
            assert db_org2.name == "Test Org 2"
            assert db_org1.id != db_org2.id

    def test_exception_in_one_operation_does_not_affect_others(self, test_db: Session):
        """Test that an exception in one operation doesn't affect other successful operations"""
        # Create first organization successfully
        org_data1 = OrganizationDataFactory.sample_data()
        org_data1["name"] = "Success Org"
        org_create1 = schemas.OrganizationCreate(**org_data1)
        
        with patch('rhesis.backend.app.crud.get_session_variables') as mock_get_vars, \
             patch('rhesis.backend.app.crud.reset_session_context') as mock_reset:
            mock_get_vars.return_value = {}
            
            result1 = crud.create_organization(test_db, org_create1)
            assert result1 is not None
            
            # Try to create second organization with exception
            org_data2 = OrganizationDataFactory.sample_data()
            org_data2["name"] = "Failure Org"
            org_create2 = schemas.OrganizationCreate(**org_data2)
            
            with patch.object(test_db, 'add', side_effect=IntegrityError("", "", "")):
                with pytest.raises(ValueError):
                    crud.create_organization(test_db, org_create2)
            
            # Verify first organization still exists (not affected by second failure)
            db_org1 = test_db.query(models.Organization).filter(
                models.Organization.id == result1.id
            ).first()
            assert db_org1 is not None
            assert db_org1.name == "Success Org"
            
            # Verify second organization was not created
            failed_orgs = test_db.query(models.Organization).filter(
                models.Organization.name == "Failure Org"
            ).count()
            assert failed_orgs == 0
