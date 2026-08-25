"""CRUD operations for topics.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched -- see ``apps/backend/AGENTS.md``'s crud-layout rule.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item,
    get_items,
    update_item,
)


def get_topic(
    db: Session, topic_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Topic]:
    """Get a single topic by ID."""
    return get_item(db, models.Topic, topic_id, organization_id, user_id)


def get_topics(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Topic]:
    return get_items(
        db,
        models.Topic,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_topic(
    db: Session, topic: schemas.TopicCreate, organization_id: str = None, user_id: str = None
) -> models.Topic:
    """Create topic."""
    return create_item(db, models.Topic, topic, organization_id, user_id)


def update_topic(
    db: Session,
    topic_id: uuid.UUID,
    topic: schemas.TopicUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Topic]:
    """Update topic."""
    return update_item(db, models.Topic, topic_id, topic, organization_id, user_id)


def delete_topic(
    db: Session, topic_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Topic]:
    """Delete topic."""
    return delete_item(db, models.Topic, topic_id, organization_id, user_id)
