"""CRUD operations for behaviors.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

``_BEHAVIOR_RELATED_FIELDS`` covers exactly what ``BehaviorWithMetricsSchema`` in
``routers/behavior.py`` serializes -- tags, user, and each metric with its metric_type,
backend_type and tags. Status, organization and project are left out because nothing reads
them. The nested ``metrics.tags`` entry has to be listed on its own: ``selectinload``'s
default cascade skips many-to-many relations, so without it every metric in the response
lazy-loads its own tags.

``get_behaviors`` is the plain list and loads none of that -- only ``get_behaviors_detail``
eager-loads the relationships, which is why the list endpoint calls the detail variant.
``get_behaviors_detail`` runs as two queries, mirroring ``get_metrics`` and
``crud_utils.get_items_detail``: a joinless query picks the page's IDs (filter + sort +
LIMIT/OFFSET), then a second query eager-loads the relationships for just those IDs.
Without the split, Postgres would build every join for every matching row in the
organization before it could sort and cut down to ``limit``. The second query's
``WHERE id IN (...)`` does not preserve order, so the phase-1 sort is re-applied in Python
-- dropping that step silently returns the right page in the wrong order.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_items,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

_BEHAVIOR_RELATED_FIELDS = (
    include(models.Behavior.user),
    include(models.Behavior._tags_relationship, models.TaggedItem.tag),
    include(models.Behavior.metrics),
    include(models.Behavior.metrics, models.Metric.metric_type),
    include(models.Behavior.metrics, models.Metric.backend_type),
    include(models.Behavior.metrics, models.Metric._tags_relationship, models.TaggedItem.tag),
)


def get_behavior(
    db: Session, behavior_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Behavior]:
    """Get behavior with relationships eagerly loaded."""
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.Behavior)
        .with_deleted()
        .with_related(*_BEHAVIOR_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .filter_by_id(behavior_id)
    )
    return _check_and_raise_if_deleted(item, models.Behavior, behavior_id, False)


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
    ordered_ids = (
        QueryBuilder(db, models.Behavior)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .ids()
    )
    if not ordered_ids:
        return []

    items = (
        QueryBuilder(db, models.Behavior)
        .with_related(*_BEHAVIOR_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .query.filter(models.Behavior.id.in_(ordered_ids))
        .all()
    )

    # WHERE id IN (...) does not preserve order -- re-apply the phase-1 sort.
    items_by_id = {item.id: item for item in items}
    return [items_by_id[item_id] for item_id in ordered_ids if item_id in items_by_id]


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
