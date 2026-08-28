"""CRUD operations for architect sessions and their messages.

Messages share this module because an ``ArchitectMessage`` only exists as part of a
session -- there is no standalone message endpoint. ``get_architect_messages`` builds a
raw ``db.query`` chain instead of going through ``QueryBuilder``, so it has to filter
``deleted_at`` itself; ``QueryBuilder`` would have added that automatically.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item,
    get_item_detail,
    get_items,
    update_item,
)
from rhesis.backend.app.utils.query_utils import include


def get_architect_session(
    db: Session,
    session_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.ArchitectSession]:
    return get_item(db, models.ArchitectSession, session_id, organization_id, user_id)


def get_architect_session_detail(
    db: Session,
    session_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.ArchitectSession]:
    """Get an architect session with its messages eagerly loaded."""
    return get_item_detail(
        db,
        models.ArchitectSession,
        session_id,
        organization_id=organization_id,
        user_id=user_id,
        related_fields=(include(models.ArchitectSession.messages),),
    )


def get_architect_sessions(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.ArchitectSession]:
    return get_items(
        db,
        models.ArchitectSession,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_architect_session(
    db: Session,
    session: schemas.ArchitectSessionCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.ArchitectSession:
    return create_item(db, models.ArchitectSession, session, organization_id, user_id)


def update_architect_session(
    db: Session,
    session_id: uuid.UUID,
    session: schemas.ArchitectSessionUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.ArchitectSession]:
    return update_item(db, models.ArchitectSession, session_id, session, organization_id, user_id)


def delete_architect_session(
    db: Session,
    session_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.ArchitectSession]:
    return delete_item(db, models.ArchitectSession, session_id, organization_id, user_id)


def get_architect_messages(
    db: Session,
    session_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.ArchitectMessage]:
    query = (
        db.query(models.ArchitectMessage)
        .filter(models.ArchitectMessage.session_id == session_id)
        .filter(models.ArchitectMessage.deleted_at.is_(None))
        .order_by(models.ArchitectMessage.created_at)
        .offset(skip)
        .limit(limit)
    )
    return query.all()


def create_architect_message(
    db: Session,
    message: schemas.ArchitectMessageCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.ArchitectMessage:
    return create_item(db, models.ArchitectMessage, message, organization_id, user_id)
