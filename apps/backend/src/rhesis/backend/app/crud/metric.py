"""CRUD operations for metrics and their behavior/test-set associations.

Split out of ``crud/__init__.py``. Import the functions directly::

    from rhesis.backend.app.crud.metric import get_metrics
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

logger = logging.getLogger(__name__)


# Metric CRUD
# Relationships serialized by schemas.MetricDetail. with_related picks joinedload
# for many-to-one (metric_type, ...) and selectinload for the many-to-many
# (behaviors) -- joinedload on an M2M would cartesian-product the rows.
# status/assignee/owner/user/organization/project/test_sets: unused, excluded.
_METRIC_RELATED_FIELDS = (
    include(models.Metric.metric_type),
    include(models.Metric.model),
    include(models.Metric.backend_type),
    # behaviors serializes as BehaviorReference, which reads counts/tags;
    # with_default_derived_field_loads only cascades those into many-to-one
    # relations, so these chains are explicit to avoid an N+1 per behavior.
    include(models.Metric.behaviors),
    include(models.Metric.behaviors, models.Behavior.comments),
    include(models.Metric.behaviors, models.Behavior.tasks),
    include(models.Metric.behaviors, models.Behavior._tags_relationship, models.TaggedItem.tag),
)


def get_metric(
    db: Session, metric_id: uuid.UUID, organization_id: str, user_id: str = None
) -> Optional[models.Metric]:
    """Get a specific metric by ID with its related objects, including many-to-many relationships"""
    return (
        QueryBuilder(db, models.Metric)
        .with_related(*_METRIC_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_custom_filter(lambda q: q.filter(models.Metric.id == metric_id))
        .first()
    )


def _apply_metric_scope_filter(builder: QueryBuilder, metric_scope: str | None) -> None:
    """Parse a comma-separated metric_scope string and apply a JSONB @> filter."""
    if not metric_scope:
        return
    from sqlalchemy import or_
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
    from sqlalchemy.sql.expression import cast

    scopes = [s.strip() for s in metric_scope.split(",") if s.strip()]
    if scopes:
        builder.query = builder.query.filter(
            or_(*[models.Metric.metric_scope.op("@>")(cast([s], PG_JSONB)) for s in scopes])
        )


def get_metrics(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    metric_scope: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Metric]:
    """Get all metrics with their related objects, including many-to-many relationships.

    Runs as two queries, mirroring crud_utils.get_items_detail: a joinless
    query picks the page's IDs (filter + sort + LIMIT/OFFSET), then a second
    query eager-loads the metric relationships scoped to just those IDs.
    Without this split, Postgres has to build all nine _METRIC_RELATED_FIELDS
    joins for every matching row across the org before it can sort and cut
    down to `limit`, so cost scales with total matching rows rather than
    page size.
    """
    builder = (
        QueryBuilder(db, models.Metric)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
    )

    _apply_metric_scope_filter(builder, metric_scope)

    ordered_ids = builder.ids()
    if not ordered_ids:
        return []

    items = (
        QueryBuilder(db, models.Metric)
        .with_related(*_METRIC_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .query.filter(models.Metric.id.in_(ordered_ids))
        .all()
    )

    # WHERE id IN (...) does not preserve order -- re-apply the phase-1 sort.
    items_by_id = {item.id: item for item in items}
    return [items_by_id[item_id] for item_id in ordered_ids if item_id in items_by_id]


def _preprocess_metric_data(
    db: Session,
    metric: Union[schemas.MetricCreate, schemas.MetricUpdate],
    organization_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Preprocess metric data from SDK to convert string types to IDs."""
    from rhesis.backend.app.constants import EntityType
    from rhesis.backend.app.utils.crud_utils import get_or_create_status, get_or_create_type_lookup

    try:
        # Convert to dict.  For updates exclude both unset and None-valued
        # fields so that null values from the frontend don't overwrite existing
        # data (mirrors how update_item handles Pydantic models).
        is_update = isinstance(metric, schemas.MetricUpdate)
        if hasattr(metric, "model_dump"):
            metric_dict = metric.model_dump(exclude_unset=is_update, exclude_none=is_update)
        else:
            metric_dict = metric.dict(exclude_unset=is_update, exclude_none=is_update)
    except Exception as e:
        logger.error(f"Failed to convert metric to dict: {e}")
        raise

    try:
        # Handle backend_type string -> backend_type_id (SDK approach)
        # Only convert if string is provided AND ID is not already set
        if (
            "backend_type" in metric_dict
            and metric_dict["backend_type"]
            and not metric_dict.get("backend_type_id")
        ):
            backend_type = get_or_create_type_lookup(
                db=db,
                type_name="BackendType",
                type_value=metric_dict["backend_type"],
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )
            metric_dict["backend_type_id"] = backend_type.id

        # Always remove the string field to avoid conflicts with the database model
        if "backend_type" in metric_dict:
            del metric_dict["backend_type"]

        # Handle metric_type string -> metric_type_id (SDK approach)
        # Only convert if string is provided AND ID is not already set
        if (
            "metric_type" in metric_dict
            and metric_dict["metric_type"]
            and not metric_dict.get("metric_type_id")
        ):
            metric_type = get_or_create_type_lookup(
                db=db,
                type_name="MetricType",
                type_value=metric_dict["metric_type"],
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )
            metric_dict["metric_type_id"] = metric_type.id

        # Always remove the string field to avoid conflicts with the database model
        if "metric_type" in metric_dict:
            del metric_dict["metric_type"]

        # Only set defaults for creates, not updates
        if not is_update:
            # Set class_name based on score_type if not provided
            if not metric_dict.get("class_name"):
                score_type = metric_dict.get("score_type")
                if score_type == "numeric":
                    metric_dict["class_name"] = "NumericJudge"
                elif score_type == "categorical":
                    metric_dict["class_name"] = "CategoricalJudge"

            # Ensure we have a status_id if not provided
            if not metric_dict.get("status_id"):
                status = get_or_create_status(
                    db=db,
                    name="Active",  # Default status
                    entity_type=EntityType.METRIC,
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )
                metric_dict["status_id"] = status.id

        return metric_dict

    except Exception as e:
        logger.error(f"Error during metric preprocessing: {e}", exc_info=True)
        raise


def create_metric(
    db: Session, metric: schemas.MetricCreate, organization_id: str = None, user_id: str = None
) -> models.Metric:
    """Create a new metric."""

    try:
        # Preprocess SDK data: convert string types to IDs
        metric_data = _preprocess_metric_data(db, metric, organization_id, user_id)

        # Create the metric
        result = create_item(db, models.Metric, metric_data, organization_id, user_id)
        return result

    except Exception as e:
        logger.error(
            f"Failed to create metric '{getattr(metric, 'name', 'Unknown')}': {e}", exc_info=True
        )
        raise


def update_metric(
    db: Session,
    metric_id: uuid.UUID,
    metric: schemas.MetricUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Metric]:
    """Update a metric."""
    metric_data = _preprocess_metric_data(db, metric, organization_id, user_id)
    return update_item(db, models.Metric, metric_id, metric_data, organization_id, user_id)


def delete_metric(
    db: Session, metric_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Metric]:
    """Delete a metric"""
    return delete_item(
        db, models.Metric, metric_id, organization_id=organization_id, user_id=user_id
    )


def add_behavior_to_metric(
    db: Session, metric_id: UUID, behavior_id: UUID, user_id: UUID, organization_id: UUID
) -> bool:
    """Add a behavior to a metric.

    Args:
        db: Database session
        metric_id: ID of the metric
        behavior_id: ID of the behavior to add
        user_id: ID of the user performing the operation
        organization_id: ID of the organization

    Returns:
        bool: True if the behavior was added, False if it was already associated
    """
    # Verify the metric exists AND belongs to the organization (SECURITY CRITICAL)
    metric = (
        db.query(models.Metric)
        .filter(models.Metric.id == metric_id, models.Metric.organization_id == organization_id)
        .first()
    )
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found or not accessible")

    # Verify the behavior exists AND belongs to the organization (SECURITY CRITICAL)
    behavior = (
        db.query(models.Behavior)
        .filter(
            models.Behavior.id == behavior_id, models.Behavior.organization_id == organization_id
        )
        .first()
    )
    if not behavior:
        raise ValueError(f"Behavior with id {behavior_id} not found or not accessible")

    # Check if the association already exists
    existing = (
        db.query(models.behavior_metric_association)
        .filter(
            models.behavior_metric_association.c.metric_id == metric_id,
            models.behavior_metric_association.c.behavior_id == behavior_id,
            models.behavior_metric_association.c.organization_id == organization_id,
        )
        .first()
    )

    if existing:
        return False

    # Create the association
    db.execute(
        models.behavior_metric_association.insert().values(
            metric_id=metric_id,
            behavior_id=behavior_id,
            user_id=user_id,
            organization_id=organization_id,
        )
    )

    # Transaction commit is handled by the session context manager
    return True


def remove_behavior_from_metric(
    db: Session, metric_id: UUID, behavior_id: UUID, organization_id: UUID
) -> bool:
    """Remove a behavior from a metric.

    Args:
        db: Database session
        metric_id: ID of the metric
        behavior_id: ID of the behavior to remove
        organization_id: ID of the organization

    Returns:
        bool: True if the behavior was removed, False if it wasn't associated
    """
    # Verify the metric exists AND belongs to the organization (SECURITY CRITICAL)
    metric = (
        db.query(models.Metric)
        .filter(models.Metric.id == metric_id, models.Metric.organization_id == organization_id)
        .first()
    )
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found or not accessible")

    # Verify the behavior exists AND belongs to the organization (SECURITY CRITICAL)
    behavior = (
        db.query(models.Behavior)
        .filter(
            models.Behavior.id == behavior_id, models.Behavior.organization_id == organization_id
        )
        .first()
    )
    if not behavior:
        raise ValueError(f"Behavior with id {behavior_id} not found or not accessible")

    result = (
        db.query(models.behavior_metric_association)
        .filter(
            models.behavior_metric_association.c.metric_id == metric_id,
            models.behavior_metric_association.c.behavior_id == behavior_id,
            models.behavior_metric_association.c.organization_id == organization_id,
        )
        .delete()
    )

    # Transaction commit is handled by the session context manager
    return result > 0


def get_metric_behaviors(
    db: Session,
    metric_id: UUID,
    organization_id: str,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Behavior]:
    """Get all behaviors associated with a metric.

    Args:
        db: Database session
        metric_id: ID of the metric
        organization_id: ID of the organization (SECURITY CRITICAL)
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string

    Returns:
        List of behaviors associated with the metric
    """
    # Verify the metric exists AND belongs to the organization (SECURITY CRITICAL)
    metric = (
        db.query(models.Metric)
        .filter(
            models.Metric.id == metric_id, models.Metric.organization_id == UUID(organization_id)
        )
        .first()
    )
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found or not accessible")

    return (
        QueryBuilder(db, models.Behavior)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.join(models.behavior_metric_association).filter(
                models.behavior_metric_association.c.metric_id == metric_id
            )
        )
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def get_behavior_metrics(
    db: Session,
    behavior_id: UUID,
    organization_id: str,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Metric]:
    """Get all metrics associated with a behavior.

    Args:
        db: Database session
        behavior_id: ID of the behavior
        organization_id: ID of the organization (SECURITY CRITICAL)
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string

    Returns:
        List of metrics associated with the behavior
    """
    # Verify the behavior exists AND belongs to the organization (SECURITY CRITICAL)
    behavior = (
        db.query(models.Behavior)
        .filter(
            models.Behavior.id == behavior_id,
            models.Behavior.organization_id == UUID(organization_id),
        )
        .first()
    )
    if not behavior:
        raise ValueError(f"Behavior with id {behavior_id} not found or not accessible")

    return (
        QueryBuilder(db, models.Metric)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.join(models.behavior_metric_association).filter(
                models.behavior_metric_association.c.behavior_id == behavior_id
            )
        )
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


# Test Set Metric CRUD
def add_metric_to_test_set(
    db: Session, test_set_id: UUID, metric_id: UUID, user_id: UUID, organization_id: UUID
) -> bool:
    """Add a metric to a test set.

    Args:
        db: Database session
        test_set_id: ID of the test set
        metric_id: ID of the metric to add
        user_id: ID of the user performing the operation
        organization_id: ID of the organization

    Returns:
        bool: True if the metric was added, False if it was already associated
    """
    # Verify the test set exists AND belongs to the organization (SECURITY CRITICAL)
    test_set = (
        db.query(models.TestSet)
        .filter(models.TestSet.id == test_set_id, models.TestSet.organization_id == organization_id)
        .first()
    )
    if not test_set:
        raise ValueError(f"Test set with id {test_set_id} not found or not accessible")

    # Verify the metric exists AND belongs to the organization (SECURITY CRITICAL)
    metric = (
        db.query(models.Metric)
        .filter(models.Metric.id == metric_id, models.Metric.organization_id == organization_id)
        .first()
    )
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found or not accessible")

    # Check if the association already exists
    existing = (
        db.query(models.test_set_metric_association)
        .filter(
            models.test_set_metric_association.c.test_set_id == test_set_id,
            models.test_set_metric_association.c.metric_id == metric_id,
            models.test_set_metric_association.c.organization_id == organization_id,
        )
        .first()
    )

    if existing:
        return False

    # Create the association
    db.execute(
        models.test_set_metric_association.insert().values(
            test_set_id=test_set_id,
            metric_id=metric_id,
            user_id=user_id,
            organization_id=organization_id,
        )
    )

    # Transaction commit is handled by the session context manager
    return True


def remove_metric_from_test_set(
    db: Session, test_set_id: UUID, metric_id: UUID, organization_id: UUID
) -> bool:
    """Remove a metric from a test set.

    Args:
        db: Database session
        test_set_id: ID of the test set
        metric_id: ID of the metric to remove
        organization_id: ID of the organization

    Returns:
        bool: True if the metric was removed, False if it wasn't associated
    """
    # Verify the test set exists AND belongs to the organization (SECURITY CRITICAL)
    test_set = (
        db.query(models.TestSet)
        .filter(models.TestSet.id == test_set_id, models.TestSet.organization_id == organization_id)
        .first()
    )
    if not test_set:
        raise ValueError(f"Test set with id {test_set_id} not found or not accessible")

    # Verify the metric exists AND belongs to the organization (SECURITY CRITICAL)
    metric = (
        db.query(models.Metric)
        .filter(models.Metric.id == metric_id, models.Metric.organization_id == organization_id)
        .first()
    )
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found or not accessible")

    result = db.execute(
        models.test_set_metric_association.delete().where(
            models.test_set_metric_association.c.test_set_id == test_set_id,
            models.test_set_metric_association.c.metric_id == metric_id,
            models.test_set_metric_association.c.organization_id == organization_id,
        )
    )

    # Transaction commit is handled by the session context manager
    return result.rowcount > 0
