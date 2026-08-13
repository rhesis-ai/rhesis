"""CRUD operations for behaviors.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

``_BEHAVIOR_RELATED_FIELDS`` covers exactly what ``BehaviorWithMetricsSchema`` in
``routers/behavior.py`` serializes -- user, and each metric with its metric_type,
backend_type and tags. Status, organization and project are left out because nothing reads
them. Behavior's own tags load via ``with_default_derived_field_loads`` (``TagsMixin``), same
as every other entity -- only the nested ``metrics.tags`` needs to be listed explicitly here,
since that cascade only covers many-to-one relations and ``metrics`` is many-to-many.

``get_behaviors`` is the plain list and loads none of that -- only ``get_behaviors_detail``
eager-loads the relationships, which is why the list endpoint calls the detail variant.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    get_items,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import include

_BEHAVIOR_RELATED_FIELDS = (
    include(models.Behavior.user),
    include(models.Behavior.metrics),
    include(models.Behavior.metrics, models.Metric.metric_type),
    include(models.Behavior.metrics, models.Metric.backend_type),
    include(models.Behavior.metrics, models.Metric._tags_relationship, models.TaggedItem.tag),
)


def get_behavior(
    db: Session, behavior_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Behavior]:
    """Get behavior with relationships eagerly loaded."""
    return get_item_detail(
        db,
        models.Behavior,
        behavior_id,
        organization_id,
        user_id,
        related_fields=_BEHAVIOR_RELATED_FIELDS,
    )


def get_behaviors(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Behavior]:
    """Get behaviors."""
    return get_items(
        db, models.Behavior, skip, limit, sort_by, sort_order, filter, organization_id, user_id
    )


def get_behaviors_detail(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Behavior]:
    """Get behaviors with related objects for BehaviorWithMetricsSchema, including metrics."""
    return get_items_detail(
        db,
        models.Behavior,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_BEHAVIOR_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_behavior(
    db: Session, behavior: schemas.BehaviorCreate, organization_id: str = None, user_id: str = None
) -> models.Behavior:
    """Create behavior."""
    return create_item(db, models.Behavior, behavior, organization_id, user_id)


def update_behavior(
    db: Session,
    behavior_id: uuid.UUID,
    behavior: schemas.BehaviorUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Behavior]:
    """Update behavior."""
    return update_item(db, models.Behavior, behavior_id, behavior, organization_id, user_id)


def delete_behavior(
    db: Session, behavior_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Behavior]:
    """Delete behavior."""
    return delete_item(db, models.Behavior, behavior_id, organization_id, user_id)
