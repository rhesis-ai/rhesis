"""CRUD operations for requirements.

``_REQUIREMENT_RELATED_FIELDS`` covers exactly what ``RequirementWithMetricsSchema`` in
``routers/requirement.py`` serializes -- user, and each metric with its metric_type,
backend_type and tags. Status, organization and project are left out because nothing reads
them. Requirement's own tags load via ``with_default_derived_field_loads`` (``TagsMixin``), same
as every other entity -- only the nested ``metrics.tags`` needs to be listed explicitly here,
since that cascade only covers many-to-one relations and ``metrics`` is many-to-many.

``get_requirements`` is the plain list and loads none of that -- only ``get_requirements_detail``
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

_REQUIREMENT_RELATED_FIELDS = (
    include(models.Requirement.user),
    include(models.Requirement.metrics),
    include(models.Requirement.metrics, models.Metric.metric_type),
    include(models.Requirement.metrics, models.Metric.backend_type),
    include(models.Requirement.metrics, models.Metric._tags_relationship, models.TaggedItem.tag),
)


def get_requirement(
    db: Session, requirement_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Requirement]:
    """Get requirement with relationships eagerly loaded."""
    return get_item_detail(
        db,
        models.Requirement,
        requirement_id,
        organization_id,
        user_id,
        related_fields=_REQUIREMENT_RELATED_FIELDS,
    )


def get_requirements(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Requirement]:
    """Get requirements."""
    return get_items(
        db, models.Requirement, skip, limit, sort_by, sort_order, filter, organization_id, user_id
    )


def get_requirements_detail(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Requirement]:
    """Get requirements with related objects for RequirementWithMetricsSchema, including metrics."""
    return get_items_detail(
        db,
        models.Requirement,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_REQUIREMENT_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_requirement(
    db: Session,
    requirement: schemas.RequirementCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.Requirement:
    """Create requirement."""
    return create_item(db, models.Requirement, requirement, organization_id, user_id)


def update_requirement(
    db: Session,
    requirement_id: uuid.UUID,
    requirement: schemas.RequirementUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Requirement]:
    """Update requirement."""
    return update_item(
        db, models.Requirement, requirement_id, requirement, organization_id, user_id
    )


def delete_requirement(
    db: Session, requirement_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Requirement]:
    """Delete requirement."""
    return delete_item(db, models.Requirement, requirement_id, organization_id, user_id)
