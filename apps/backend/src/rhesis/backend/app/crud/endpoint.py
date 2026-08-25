"""CRUD operations for endpoints.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched -- see ``apps/backend/AGENTS.md``'s crud-layout rule.
"""

import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    bulk_delete_by_ids,
    create_item,
    delete_item,
    get_item_detail,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import include

_ENDPOINT_RELATED_FIELDS = (
    include(models.Endpoint.status),
    include(models.Endpoint.user),
    include(models.Endpoint.project),
)


def get_endpoint(
    db: Session,
    endpoint_id: uuid.UUID,
    organization_id: str,
    user_id: str,
    project_id: str = None,
) -> Optional[models.Endpoint]:
    """Get endpoint with relationships eagerly loaded."""
    return get_item_detail(
        db,
        models.Endpoint,
        endpoint_id,
        organization_id,
        user_id,
        project_id=project_id,
        related_fields=_ENDPOINT_RELATED_FIELDS,
    )


def get_endpoints(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Endpoint]:
    return get_items_detail(
        db,
        models.Endpoint,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_ENDPOINT_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_endpoint(
    db: Session, endpoint: schemas.EndpointCreate, organization_id: str, user_id: str
) -> models.Endpoint:
    """Create endpoint."""
    return create_item(db, models.Endpoint, endpoint, organization_id, user_id)


def update_endpoint(
    db: Session,
    endpoint_id: uuid.UUID,
    endpoint: schemas.EndpointUpdate,
    organization_id: str,
    user_id: str,
) -> Optional[models.Endpoint]:
    """Update endpoint."""
    return update_item(db, models.Endpoint, endpoint_id, endpoint, organization_id, user_id)


def delete_endpoint(
    db: Session, endpoint_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Endpoint]:
    return delete_item(
        db, models.Endpoint, endpoint_id, organization_id=organization_id, user_id=user_id
    )


def bulk_delete_endpoints(
    db: Session,
    endpoint_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """Soft delete multiple endpoints in one transaction.

    No owner-only rule on endpoint delete, so this is a direct wrapper around
    the generic bulk helper.
    """
    return bulk_delete_by_ids(
        db,
        models.Endpoint,
        endpoint_ids,
        organization_id=organization_id,
        user_id=user_id,
    )
