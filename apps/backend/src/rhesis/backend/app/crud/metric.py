"""CRUD operations for metrics and their requirement/test-set associations.

Import the functions directly::

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
    get_item,
    get_item_detail,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

logger = logging.getLogger(__name__)


# Metric CRUD
# Relationships serialized by schemas.MetricDetail. with_related picks joinedload
# for many-to-one (metric_type, ...) and selectinload for the many-to-many
# (requirements) -- joinedload on an M2M would cartesian-product the rows.
# status/assignee/owner/user/organization/project/test_sets: unused, excluded.
_METRIC_RELATED_FIELDS = (
    include(models.Metric.metric_type),
    include(models.Metric.model),
    include(models.Metric.backend_type),
    # requirements serializes as RequirementReference, which reads counts/tags;
    # with_default_derived_field_loads only cascades those into many-to-one
    # relations, so these chains are explicit to avoid an N+1 per requirement.
    include(models.Metric.requirements),
    include(models.Metric.requirements, models.Requirement.comments),
    include(models.Metric.requirements, models.Requirement.tasks),
    include(
        models.Metric.requirements, models.Requirement._tags_relationship, models.TaggedItem.tag
    ),
)


def get_metric(
    db: Session, metric_id: uuid.UUID, organization_id: str, user_id: str | None = None
) -> Optional[models.Metric]:
    """Get a specific metric by ID with its related objects, including many-to-many relationships.

    Raises ``ItemDeletedException`` for a soft-deleted metric, same as every other
    entity's single-item fetch.
    """
    return get_item_detail(
        db,
        models.Metric,
        metric_id,
        organization_id=organization_id,
        user_id=user_id,
        related_fields=_METRIC_RELATED_FIELDS,
    )


def _metric_scope_filter(metric_scope: str | None):
    """Build a query transform filtering Metric.metric_scope by a comma-separated scope list.

    Returns None when there's nothing to filter, so callers can pass the result straight
    through as get_items_detail's extra_filter without an extra None-check.
    """
    if not metric_scope:
        return None
    from sqlalchemy import or_
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
    from sqlalchemy.sql.expression import cast

    scopes = [s.strip() for s in metric_scope.split(",") if s.strip()]
    if not scopes:
        return None

    def _filter(q):
        return q.filter(
            or_(*[models.Metric.metric_scope.op("@>")(cast([s], PG_JSONB)) for s in scopes])
        )

    return _filter


def get_metrics(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    metric_scope: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.Metric]:
    """Get all metrics with their related objects, including many-to-many relationships."""
    return get_items_detail(
        db,
        models.Metric,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_METRIC_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
        extra_filter=_metric_scope_filter(metric_scope),
    )


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
    db: Session,
    metric: schemas.MetricCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
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
    organization_id: str | None = None,
    user_id: str | None = None,
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


def add_requirement_to_metric(
    db: Session, metric_id: UUID, requirement_id: UUID, user_id: UUID, organization_id: UUID
) -> bool:
    """Add a requirement to a metric.

    Args:
        db: Database session
        metric_id: ID of the metric
        requirement_id: ID of the requirement to add
        user_id: ID of the user performing the operation
        organization_id: ID of the organization

    Returns:
        bool: True if the requirement was added, False if it was already associated
    """
    # Verify the metric exists AND belongs to the organization (SECURITY CRITICAL)
    metric = get_item(db, models.Metric, metric_id, organization_id)
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found or not accessible")

    # Verify the requirement exists AND belongs to the organization (SECURITY CRITICAL)
    requirement = get_item(db, models.Requirement, requirement_id, organization_id)
    if not requirement:
        raise ValueError(f"Requirement with id {requirement_id} not found or not accessible")

    # Check if the association already exists
    existing = (
        db.query(models.requirement_metric_association)
        .filter(
            models.requirement_metric_association.c.metric_id == metric_id,
            models.requirement_metric_association.c.requirement_id == requirement_id,
            models.requirement_metric_association.c.organization_id == organization_id,
        )
        .first()
    )

    if existing:
        return False

    # Create the association
    db.execute(
        models.requirement_metric_association.insert().values(
            metric_id=metric_id,
            requirement_id=requirement_id,
            user_id=user_id,
            organization_id=organization_id,
        )
    )

    # Transaction commit is handled by the session context manager
    return True


def remove_requirement_from_metric(
    db: Session, metric_id: UUID, requirement_id: UUID, organization_id: UUID
) -> bool:
    """Remove a requirement from a metric.

    Args:
        db: Database session
        metric_id: ID of the metric
        requirement_id: ID of the requirement to remove
        organization_id: ID of the organization

    Returns:
        bool: True if the requirement was removed, False if it wasn't associated
    """
    # Verify the metric exists AND belongs to the organization (SECURITY CRITICAL)
    metric = get_item(db, models.Metric, metric_id, organization_id)
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found or not accessible")

    # Verify the requirement exists AND belongs to the organization (SECURITY CRITICAL)
    requirement = get_item(db, models.Requirement, requirement_id, organization_id)
    if not requirement:
        raise ValueError(f"Requirement with id {requirement_id} not found or not accessible")

    result = (
        db.query(models.requirement_metric_association)
        .filter(
            models.requirement_metric_association.c.metric_id == metric_id,
            models.requirement_metric_association.c.requirement_id == requirement_id,
            models.requirement_metric_association.c.organization_id == organization_id,
        )
        .delete()
    )

    # Transaction commit is handled by the session context manager
    return result > 0


def get_metric_requirements(
    db: Session,
    metric_id: UUID,
    organization_id: str,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Requirement]:
    """Get all requirements associated with a metric.

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
        List of requirements associated with the metric
    """
    # Verify the metric exists AND belongs to the organization (SECURITY CRITICAL)
    metric = get_item(db, models.Metric, metric_id, organization_id)
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found or not accessible")

    return (
        QueryBuilder(db, models.Requirement)
        .with_related(include(models.Requirement.user))
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.join(models.requirement_metric_association).filter(
                models.requirement_metric_association.c.metric_id == metric_id
            )
        )
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def get_requirement_metrics(
    db: Session,
    requirement_id: UUID,
    organization_id: str,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Metric]:
    """Get all metrics associated with a requirement.

    Args:
        db: Database session
        requirement_id: ID of the requirement
        organization_id: ID of the organization (SECURITY CRITICAL)
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string

    Returns:
        List of metrics associated with the requirement
    """
    # Verify the requirement exists AND belongs to the organization (SECURITY CRITICAL)
    requirement = get_item(db, models.Requirement, requirement_id, organization_id)
    if not requirement:
        raise ValueError(f"Requirement with id {requirement_id} not found or not accessible")

    return (
        QueryBuilder(db, models.Metric)
        .with_related(include(models.Metric.metric_type), include(models.Metric.backend_type))
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.join(models.requirement_metric_association).filter(
                models.requirement_metric_association.c.requirement_id == requirement_id
            )
        )
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


# Test Set Metric CRUD
def get_test_set_metrics(
    db: Session, test_set_id: UUID, organization_id: str
) -> List[models.Metric]:
    """Get all metrics associated with a test set.

    Queries Metric via the association table rather than reading TestSet.metrics
    directly -- robust regardless of whether the caller's TestSet object eager-loaded it.
    """
    return (
        QueryBuilder(db, models.Metric)
        .with_related(include(models.Metric.metric_type), include(models.Metric.backend_type))
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.join(models.test_set_metric_association).filter(
                models.test_set_metric_association.c.test_set_id == test_set_id
            )
        )
        .all()
    )


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
    metric = get_item(db, models.Metric, metric_id, organization_id)
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
    metric = get_item(db, models.Metric, metric_id, organization_id)
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
