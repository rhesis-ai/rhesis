"""
🏷️ Tag CRUD Operations Testing

Comprehensive test suite for tag-related CRUD operations.
Tests focus on tag assignment and removal operations while ensuring proper tenant
isolation and data integrity.

Functions tested:
- assign_tag: Assign tags to entities
- remove_tag: Remove tags from entities

Run with: python -m pytest tests/backend/crud/test_tag_crud.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.constants import EntityType


@pytest.mark.unit
@pytest.mark.crud
class TestTagOperations:
    """🏷️ Test tag CRUD operations"""

    def test_assign_tag_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, db_prompt
    ):
        """Test successful tag assignment to entity"""
        # Use existing database fixture instead of creating manually
        db_entity = db_prompt

        # Create tag schema for assignment
        tag_create_schema = schemas.TagCreate(
            name="test-tag",
            icon_unicode="🏷️",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )

        # Test tag assignment
        result = crud.assign_tag(
            db=test_db,
            tag=tag_create_schema,
            entity_id=db_entity.id,
            entity_type=EntityType.PROMPT,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Verify the result
        assert result is not None
        assert result.name == tag_create_schema.name
        assert result.organization_id == uuid.UUID(test_org_id)

        # Verify tagged_item relationship was created
        tagged_item = (
            test_db.query(models.TaggedItem)
            .filter(
                models.TaggedItem.tag_id == result.id,
                models.TaggedItem.entity_id == db_entity.id,
                models.TaggedItem.entity_type == EntityType.PROMPT.value,
                models.TaggedItem.organization_id == uuid.UUID(test_org_id),
            )
            .first()
        )

        assert tagged_item is not None
        assert tagged_item.organization_id == uuid.UUID(test_org_id)
        assert tagged_item.user_id == uuid.UUID(authenticated_user_id)

    def test_assign_tag_entity_not_found(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test tag assignment fails with non-existent entity"""
        fake_entity_id = uuid.uuid4()

        tag_create_schema = schemas.TagCreate(
            name="test-tag",
            icon_unicode="🏷️",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )

        with pytest.raises(ValueError, match="Prompt with id .* not found"):
            crud.assign_tag(
                db=test_db,
                tag=tag_create_schema,
                entity_id=fake_entity_id,
                entity_type=EntityType.PROMPT,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

    def test_remove_tag_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, db_prompt
    ):
        """Test successful tag removal from entity"""
        # Create tag using data factory
        from tests.backend.routes.fixtures.data_factories import TagDataFactory
        import uuid

        tag_data = TagDataFactory.sample_data()
        tag_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_tag = models.Tag(**tag_data)
        db_entity = db_prompt
        test_db.add(db_tag)
        test_db.flush()

        # Create tagged_item relationship
        tagged_item_data = {
            "tag_id": db_tag.id,
            "entity_id": db_entity.id,
            "entity_type": EntityType.PROMPT.value,
            "organization_id": uuid.UUID(test_org_id),
            "user_id": uuid.UUID(authenticated_user_id),
        }
        db_tagged_item = models.TaggedItem(**tagged_item_data)
        test_db.add(db_tagged_item)
        test_db.flush()

        # Test tag removal
        result = crud.remove_tag(
            db=test_db,
            tag_id=db_tag.id,
            entity_id=db_entity.id,
            entity_type=EntityType.PROMPT,
            organization_id=test_org_id,
        )

        # Verify removal was successful
        assert result is True

        # Verify tagged_item was deleted
        tagged_item = (
            test_db.query(models.TaggedItem)
            .filter(
                models.TaggedItem.tag_id == db_tag.id, models.TaggedItem.entity_id == db_entity.id
            )
            .first()
        )
        assert tagged_item is None

    def test_remove_tag_not_found(self, test_db: Session, test_org_id: str):
        """Test tag removal fails with non-existent tag"""
        fake_tag_id = uuid.uuid4()
        fake_entity_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Tag not found"):
            crud.remove_tag(
                db=test_db,
                tag_id=fake_tag_id,
                entity_id=fake_entity_id,
                entity_type=EntityType.PROMPT,
                organization_id=test_org_id,
            )
