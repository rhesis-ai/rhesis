"""CRUD operations for type lookups.

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
from rhesis.backend.app.utils.query_utils import QueryBuilder


def get_type_lookup(
    db: Session, type_lookup_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TypeLookup]:
    """Get type_lookup."""
    return get_item(db, models.TypeLookup, type_lookup_id, organization_id, user_id)


def get_type_lookups(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.TypeLookup]:
    return get_items(
        db,
        models.TypeLookup,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_type_lookup(
    db: Session,
    type_lookup: schemas.TypeLookupCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.TypeLookup:
    """Create type_lookup."""
    return create_item(db, models.TypeLookup, type_lookup, organization_id, user_id)


def update_type_lookup(
    db: Session,
    type_lookup_id: uuid.UUID,
    type_lookup: schemas.TypeLookupUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TypeLookup]:
    """Update type_lookup."""
    return update_item(db, models.TypeLookup, type_lookup_id, type_lookup, organization_id, user_id)


def delete_type_lookup(
    db: Session, type_lookup_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.TypeLookup]:
    """Delete type lookup."""
    return delete_item(db, models.TypeLookup, type_lookup_id, organization_id, user_id)


def get_type_lookup_by_name_and_value(
    db: Session, type_name: str, type_value: str, organization_id: str, user_id: str = None
) -> Optional[models.TypeLookup]:
    """Get a type lookup by its type_name and type_value"""
    return (
        QueryBuilder(db, models.TypeLookup)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(
                models.TypeLookup.type_name == type_name, models.TypeLookup.type_value == type_value
            )
        )
        .first()
    )
