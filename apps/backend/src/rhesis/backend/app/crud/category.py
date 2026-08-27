"""CRUD operations for categories."""

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


def get_category(
    db: Session, category_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Category]:
    """Get a single category by ID."""
    return get_item(db, models.Category, category_id, organization_id, user_id)


def get_categories(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Category]:
    return get_items(
        db,
        models.Category,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_category(
    db: Session, category: schemas.CategoryCreate, organization_id: str = None, user_id: str = None
) -> models.Category:
    """Create category."""
    return create_item(db, models.Category, category, organization_id, user_id)


def update_category(
    db: Session,
    category_id: uuid.UUID,
    category: schemas.CategoryUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Category]:
    """Update category."""
    return update_item(db, models.Category, category_id, category, organization_id, user_id)


def delete_category(
    db: Session, category_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Category]:
    return delete_item(
        db, models.Category, category_id, organization_id=organization_id, user_id=user_id
    )
