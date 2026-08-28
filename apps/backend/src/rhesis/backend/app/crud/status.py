"""CRUD operations for statuses."""

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


def get_status(
    db: Session, status_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Status]:
    """Get a single status by ID."""
    return get_item(db, models.Status, status_id, organization_id, user_id)


def get_statuses(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Status]:
    return get_items(
        db,
        models.Status,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_status(
    db: Session, status: schemas.StatusCreate, organization_id: str = None, user_id: str = None
) -> models.Status:
    """Create status."""
    return create_item(db, models.Status, status, organization_id, user_id)


def update_status(
    db: Session,
    status_id: uuid.UUID,
    status: schemas.StatusUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Status]:
    """Update status."""
    return update_item(db, models.Status, status_id, status, organization_id, user_id)


def delete_status(
    db: Session, status_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Status]:
    """Delete status."""
    return delete_item(db, models.Status, status_id, organization_id, user_id)
