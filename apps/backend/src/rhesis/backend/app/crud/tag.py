"""CRUD operations for tags and their assignment to entities.

``assign_tag`` and ``remove_tag`` link a tag to any kind of entity through the
``TaggedItem`` table, which stores the target as an ``entity_id`` plus an ``entity_type``
string rather than a foreign key. The entity type drives the lookup of the ORM class:
every ``EntityType`` member's value is the model class name, so ``getattr(models,
entity_type.value)`` resolves it, and a model only becomes taggable once it is listed in
``schemas.tag.EntityType``.

Because there is no foreign key, nothing at the database level stops a link pointing at a
row from another organization or at a row that no longer exists. Both functions therefore
look the entity up first and raise ``ValueError`` if it isn't there, and both re-apply the
organization filter by hand on top of the ambient scope filter -- guarded by ``hasattr``,
since not every taggable model has an ``organization_id`` column.

``assign_tag`` behaves like an upsert: it creates the tag when no tag of that name exists
in the organization, and returns the existing tag untouched when the link is already there.
"""

import logging
import uuid
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.schemas.tag import EntityType
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item,
    get_items,
    update_item,
)

logger = logging.getLogger(__name__)


def get_tag(
    db: Session, tag_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Tag]:
    """Get tag."""
    return get_item(db, models.Tag, tag_id, organization_id, user_id)


def get_tags(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Tag]:
    return get_items(
        db,
        models.Tag,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_tag(
    db: Session, tag: schemas.TagCreate, organization_id: str, user_id: str
) -> models.Tag:
    """Create tag."""
    return create_item(db, models.Tag, tag, organization_id, user_id)


def update_tag(
    db: Session,
    tag_id: uuid.UUID,
    tag: schemas.TagUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Tag]:
    """Update tag."""
    return update_item(db, models.Tag, tag_id, tag, organization_id, user_id)


def delete_tag(
    db: Session, tag_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Tag]:
    """Delete tag."""
    return delete_item(db, models.Tag, tag_id, organization_id, user_id)


def assign_tag(
    db: Session,
    tag: schemas.TagCreate,
    entity_id: UUID,
    entity_type: EntityType,
    organization_id: str = None,
    user_id: str = None,
) -> models.Tag:
    """Create a tag if it doesn't exist and link it to an entity with organization filtering"""

    logger.info(
        f"assign_tag called: tag.name={tag.name}, entity_id={entity_id}, entity_type={entity_type}"
    )

    # Get the actual model class based on entity_type
    model_class = getattr(models, entity_type.value)

    # Verify the entity exists with organization filtering (SECURITY CRITICAL)
    entity_query = db.query(model_class).filter(model_class.id == entity_id)

    # Apply organization filtering if the model supports it
    if organization_id and hasattr(model_class, "organization_id"):
        entity_query = entity_query.filter(model_class.organization_id == UUID(organization_id))

    entity = entity_query.first()
    if not entity:
        raise ValueError(f"{entity_type.value} with id {entity_id} not found or not accessible")

    # Check if tag already exists (keep organization filter for double security)
    db_tag = (
        db.query(models.Tag)
        .filter(models.Tag.name == tag.name, models.Tag.organization_id == tag.organization_id)
        .first()
    )

    logger.info(f"Tag lookup: found={db_tag is not None}, tag_id={db_tag.id if db_tag else 'None'}")

    # If tag doesn't exist, create it
    if not db_tag:
        logger.info(f"Creating new tag: {tag.name}")
        db_tag = create_tag(db=db, tag=tag, organization_id=organization_id, user_id=user_id)
        logger.info(f"Tag created successfully: tag_id={db_tag.id}")

    # Check if the tag is already assigned
    existing_assignment = (
        db.query(models.TaggedItem)
        .filter(
            models.TaggedItem.tag_id == db_tag.id,
            models.TaggedItem.entity_id == entity_id,
            models.TaggedItem.entity_type == entity_type.value,
            models.TaggedItem.organization_id
            == tag.organization_id,  # Add organization filter here too
        )
        .first()
    )

    logger.info(f"Assignment lookup: found={existing_assignment is not None}")

    if existing_assignment:
        logger.info(f"Tag already assigned, returning existing tag: tag_id={db_tag.id}")
        return db_tag

    # Create the tagged_item relationship
    logger.info(f"Creating new tag assignment: tag_id={db_tag.id}, entity_id={entity_id}")
    tagged_item = models.TaggedItem(
        tag_id=db_tag.id,
        entity_id=entity_id,
        entity_type=entity_type.value,
        organization_id=tag.organization_id,
        user_id=tag.user_id,
    )
    db.add(tagged_item)
    db.flush()  # Force flush to ensure the TaggedItem is persisted
    logger.info(f"Tag assignment created successfully: tagged_item_id={tagged_item.id}")

    # Transaction commit is handled by the session context manager
    db.refresh(db_tag)

    logger.info(f"assign_tag completed successfully: tag_id={db_tag.id}")
    return db_tag


def remove_tag(
    db: Session, tag_id: UUID, entity_id: UUID, entity_type: EntityType, organization_id: str = None
) -> bool:
    """Remove a tag from an entity by deleting the tagged_item relationship"""
    # Get the tag with organization filtering (SECURITY CRITICAL)
    tag_query = db.query(models.Tag).filter(models.Tag.id == tag_id)
    if organization_id:
        tag_query = tag_query.filter(models.Tag.organization_id == UUID(organization_id))

    db_tag = tag_query.first()
    if not db_tag:
        raise ValueError("Tag not found or not accessible")

    # Verify the entity exists with organization filtering (SECURITY CRITICAL)
    model_class = getattr(models, entity_type.value)
    entity_query = db.query(model_class).filter(model_class.id == entity_id)

    # Apply organization filtering if the model supports it
    if organization_id and hasattr(model_class, "organization_id"):
        entity_query = entity_query.filter(model_class.organization_id == UUID(organization_id))

    entity = entity_query.first()
    if not entity:
        raise ValueError(f"{entity_type.value} with id {entity_id} not found or not accessible")

    result = (
        db.query(models.TaggedItem)
        .filter(
            models.TaggedItem.tag_id == tag_id,
            models.TaggedItem.entity_id == entity_id,
            models.TaggedItem.entity_type == entity_type.value,
            models.TaggedItem.organization_id == db_tag.organization_id,  # Add organization filter
        )
        .delete()
    )

    # Transaction commit is handled by the session context manager
    return result > 0
