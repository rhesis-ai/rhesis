"""CRUD for annotations.

Listing goes through one query builder shared by the page and its ``X-Total-Count``
so the two can never disagree. The run-level aggregates at the bottom replace the
JSONB scan the test-run grid used to do.
"""

import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import distinct, exists, func, or_, select
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import AnnotationTarget, EntityType
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

# Relationships serialized by schemas.Annotation.
_ANNOTATION_RELATED_FIELDS = (
    include(models.Annotation.user),
    include(models.Annotation.status),
    include(models.Annotation.resolved_by),
)

_ON_TEST_RESULT = (
    (models.Annotation.entity_id == models.TestResult.id)
    & (models.Annotation.entity_type == EntityType.TEST_RESULT.value)
    & (models.Annotation.deleted_at.is_(None))
)


def get_annotation(
    db: Session,
    annotation_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Annotation]:
    return get_item_detail(
        db,
        models.Annotation,
        annotation_id,
        organization_id,
        user_id,
        related_fields=_ANNOTATION_RELATED_FIELDS,
    )


def _annotations_query(
    db: Session,
    organization_id: str,
    search: str | None = None,
    rating: str | None = None,
    resolved: bool | None = None,
    target_type: str | None = None,
    entity_type: str | None = None,
    test_run_id: uuid.UUID | None = None,
    test_set_id: uuid.UUID | None = None,
    endpoint_id: uuid.UUID | None = None,
    metric: str | None = None,
    annotator_id: uuid.UUID | None = None,
    requirement_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    filter: str | None = None,
) -> QueryBuilder:
    """Build the filtered annotation query behind both the list page and its count."""

    def _apply(q):
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                models.Annotation.comments.ilike(pattern)
                | models.Annotation.target_reference.ilike(pattern)
            )
        if rating:
            q = q.join(models.Annotation.status).filter(models.Status.name == rating)
        if resolved is not None:
            q = q.filter(models.Annotation.resolved == resolved)
        if target_type:
            q = q.filter(models.Annotation.target_type == target_type)
        if entity_type:
            q = q.filter(models.Annotation.entity_type == entity_type)
        if test_run_id:
            q = q.filter(_in_test_run(test_run_id))
        if test_set_id:
            q = q.filter(_in_test_set(test_set_id))
        if endpoint_id:
            q = q.filter(_in_endpoint(endpoint_id))
        if metric:
            q = q.filter(_on_metric(metric))
        if annotator_id:
            q = q.filter(models.Annotation.user_id == str(annotator_id))
        if requirement_id:
            q = q.filter(_in_requirement(requirement_id))
        if date_from:
            start = datetime.combine(date_from, datetime.min.time())
            q = q.filter(models.Annotation.updated_at >= start)
        if date_to:
            end = datetime.combine(date_to, datetime.min.time())
            q = q.filter(
                models.Annotation.updated_at < end + timedelta(days=1)
            )
        return q

    return (
        QueryBuilder(db, models.Annotation)
        .with_related(*_ANNOTATION_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_odata_filter(filter)
        .with_custom_filter(_apply)
    )


def _in_test_run(test_run_id: uuid.UUID):
    """Annotations on a test result or a trace belonging to the given run."""
    on_result = exists(
        select(models.TestResult.id).where(
            models.TestResult.id == models.Annotation.entity_id,
            models.Annotation.entity_type == EntityType.TEST_RESULT.value,
            models.TestResult.test_run_id == test_run_id,
        )
    )
    on_trace = exists(
        select(models.Trace.id).where(
            models.Trace.id == models.Annotation.entity_id,
            models.Annotation.entity_type == EntityType.TRACE.value,
            models.Trace.test_run_id == test_run_id,
        )
    )
    return or_(on_result, on_trace)


def _in_test_set(test_set_id: uuid.UUID):
    """Annotations whose parent ran under a test configuration tied to the given test set."""
    on_result = exists(
        select(models.TestResult.id).where(
            models.TestResult.id == models.Annotation.entity_id,
            models.Annotation.entity_type == EntityType.TEST_RESULT.value,
            models.TestResult.test_configuration_id == models.TestConfiguration.id,
            models.TestConfiguration.test_set_id == test_set_id,
        )
    )
    on_trace = exists(
        select(models.Trace.id).where(
            models.Trace.id == models.Annotation.entity_id,
            models.Annotation.entity_type == EntityType.TRACE.value,
            models.Trace.test_run_id == models.TestRun.id,
            models.TestRun.test_configuration_id == models.TestConfiguration.id,
            models.TestConfiguration.test_set_id == test_set_id,
        )
    )
    return or_(on_result, on_trace)


def _in_endpoint(endpoint_id: uuid.UUID):
    """Annotations whose parent ran under a test configuration tied to the given endpoint."""
    on_result = exists(
        select(models.TestResult.id).where(
            models.TestResult.id == models.Annotation.entity_id,
            models.Annotation.entity_type == EntityType.TEST_RESULT.value,
            models.TestResult.test_configuration_id == models.TestConfiguration.id,
            models.TestConfiguration.endpoint_id == endpoint_id,
        )
    )
    on_trace = exists(
        select(models.Trace.id).where(
            models.Trace.id == models.Annotation.entity_id,
            models.Annotation.entity_type == EntityType.TRACE.value,
            models.Trace.test_run_id == models.TestRun.id,
            models.TestRun.test_configuration_id == models.TestConfiguration.id,
            models.TestConfiguration.endpoint_id == endpoint_id,
        )
    )
    return or_(on_result, on_trace)


def _on_metric(metric_name: str):
    """Annotations targeting a specific metric by name (case-insensitive)."""
    return (
        models.Annotation.target_type == AnnotationTarget.METRIC.value
    ) & models.Annotation.target_reference.ilike(metric_name)


def _in_requirement(requirement_id: uuid.UUID):
    """Annotations whose parent test result belongs to a test linked to the given requirement."""
    return exists(
        select(models.TestResult.id).where(
            models.TestResult.id == models.Annotation.entity_id,
            models.Annotation.entity_type == EntityType.TEST_RESULT.value,
            models.TestResult.test_id == models.Test.id,
            models.Test.requirement_id == requirement_id,
        )
    )


def get_annotations(
    db: Session,
    organization_id: str,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    **filters,
) -> List[models.Annotation]:
    return (
        _annotations_query(db, organization_id, **filters)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def count_annotations(db: Session, organization_id: str, **filters) -> int:
    return _annotations_query(db, organization_id, **filters).count()


def get_annotations_by_entity(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    organization_id: str,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> List[models.Annotation]:
    return (
        QueryBuilder(db, models.Annotation)
        .with_related(*_ANNOTATION_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(
                models.Annotation.entity_id == entity_id,
                models.Annotation.entity_type == entity_type,
            )
        )
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def create_annotation(
    db: Session,
    data: dict,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.Annotation:
    return create_item(db, models.Annotation, data, organization_id, user_id)


def update_annotation(
    db: Session,
    annotation_id: uuid.UUID,
    data: dict,
    organization_id: str,
) -> Optional[models.Annotation]:
    # No user_id: it is the annotator, and an update must not reassign authorship.
    return update_item(db, models.Annotation, annotation_id, data, organization_id)


def delete_annotation(
    db: Session,
    annotation_id: uuid.UUID,
    organization_id: str,
) -> Optional[models.Annotation]:
    return delete_item(db, models.Annotation, annotation_id, organization_id)


def get_annotations_for_entities(
    db: Session,
    entity_type: str,
    entity_ids: List[uuid.UUID],
) -> dict[uuid.UUID, List[models.Annotation]]:
    """Annotations for many entities of one type, newest first, keyed by entity id."""
    if not entity_ids:
        return {}
    rows = (
        db.query(models.Annotation)
        .filter(
            models.Annotation.entity_type == entity_type,
            models.Annotation.entity_id.in_(entity_ids),
            models.Annotation.deleted_at.is_(None),
        )
        .options(include(models.Annotation.user), include(models.Annotation.status))
        .order_by(models.Annotation.updated_at.desc())
        .all()
    )
    grouped: dict[uuid.UUID, List[models.Annotation]] = {}
    for row in rows:
        grouped.setdefault(row.entity_id, []).append(row)
    return grouped


def get_annotation_statistics_for_runs(
    db: Session,
    test_run_ids: List[uuid.UUID],
) -> dict[str, dict[str, int]]:
    """Per-run counts of annotated and human-corrected tests, for the test-run grid.

    *Corrected* means the latest entity-level annotation disagrees with the
    automated verdict the run produced -- ``original_status_id``, the snapshot
    taken before the first annotation overwrote the live status.
    """
    if not test_run_ids:
        return {}

    stats: dict[str, dict[str, int]] = {
        str(run_id): {"annotated_tests": 0, "corrected_tests": 0} for run_id in test_run_ids
    }

    annotated = (
        db.query(
            models.TestResult.test_run_id,
            func.count(distinct(models.TestResult.test_id)),
        )
        .join(models.Annotation, _ON_TEST_RESULT)
        .filter(
            models.TestResult.test_run_id.in_(test_run_ids),
            models.TestResult.deleted_at.is_(None),
        )
        .group_by(models.TestResult.test_run_id)
        .all()
    )
    for run_id, count in annotated:
        stats[str(run_id)]["annotated_tests"] = count

    latest = (
        db.query(
            models.TestResult.test_run_id.label("run_id"),
            models.TestResult.test_id.label("test_id"),
            models.TestResult.original_status_id.label("original_status_id"),
            models.Annotation.status_id.label("status_id"),
            func.row_number()
            .over(
                partition_by=models.Annotation.entity_id,
                order_by=models.Annotation.updated_at.desc(),
            )
            .label("rank"),
        )
        .join(
            models.Annotation,
            _ON_TEST_RESULT & (models.Annotation.target_type == AnnotationTarget.TEST_RESULT.value),
        )
        .filter(
            models.TestResult.test_run_id.in_(test_run_ids),
            models.TestResult.deleted_at.is_(None),
        )
        .subquery()
    )
    corrected = (
        db.query(latest.c.run_id, func.count(distinct(latest.c.test_id)))
        .filter(latest.c.rank == 1, latest.c.status_id != latest.c.original_status_id)
        .group_by(latest.c.run_id)
        .all()
    )
    for run_id, count in corrected:
        stats[str(run_id)]["corrected_tests"] = count

    return stats


def get_annotation_facets(
    db: Session,
    organization_id: str,
) -> dict:
    """Distinct filter values derived from existing annotations.

    Returns endpoints and metric names that actually appear in the org's
    annotations, so the filter drawer shows only relevant choices. Endpoints
    are fetched through the test configuration join (bypassing project scope)
    and metric names come from ``target_reference`` on metric annotations.
    """
    from rhesis.backend.app.scope import bypass_tenant_filter

    # Endpoints linked to annotated test results via test_configuration.
    # bypass_tenant_filter so the Endpoint rows (project-scoped) are visible
    # from the cross-project annotations page.
    with bypass_tenant_filter():
        endpoint_rows = (
            db.query(
                distinct(models.Endpoint.id).label("id"),
                models.Endpoint.name,
            )
            .join(
                models.TestConfiguration,
                models.TestConfiguration.endpoint_id == models.Endpoint.id,
            )
            .join(
                models.TestResult,
                models.TestResult.test_configuration_id == models.TestConfiguration.id,
            )
            .join(
                models.Annotation,
                (models.Annotation.entity_id == models.TestResult.id)
                & (models.Annotation.entity_type == EntityType.TEST_RESULT.value)
                & (models.Annotation.deleted_at.is_(None)),
            )
            .filter(
                models.Annotation.organization_id == organization_id,
                models.TestResult.deleted_at.is_(None),
            )
            .order_by(models.Endpoint.name)
            .all()
        )

    # Distinct metric names from metric-targeted annotations.
    metric_rows = (
        db.query(distinct(models.Annotation.target_reference))
        .filter(
            models.Annotation.organization_id == organization_id,
            models.Annotation.target_type == AnnotationTarget.METRIC.value,
            models.Annotation.target_reference.isnot(None),
            models.Annotation.deleted_at.is_(None),
        )
        .order_by(models.Annotation.target_reference)
        .all()
    )

    # Distinct annotators (users who have created annotations in this org).
    annotator_rows = (
        db.query(
            distinct(models.User.id).label("id"),
            models.User.name,
        )
        .join(
            models.Annotation,
            (models.Annotation.user_id == models.User.id)
            & (models.Annotation.deleted_at.is_(None)),
        )
        .filter(models.Annotation.organization_id == organization_id)
        .order_by(models.User.name)
        .all()
    )

    # Distinct requirements linked to annotated test results.
    with bypass_tenant_filter():
        requirement_rows = (
            db.query(
                distinct(models.Requirement.id).label("id"),
                models.Requirement.name,
            )
            .join(models.Test, models.Test.requirement_id == models.Requirement.id)
            .join(models.TestResult, models.TestResult.test_id == models.Test.id)
            .join(
                models.Annotation,
                (models.Annotation.entity_id == models.TestResult.id)
                & (models.Annotation.entity_type == EntityType.TEST_RESULT.value)
                & (models.Annotation.deleted_at.is_(None)),
            )
            .filter(
                models.Annotation.organization_id == organization_id,
                models.TestResult.deleted_at.is_(None),
            )
            .order_by(models.Requirement.name)
            .all()
        )

    return {
        "endpoints": [{"id": str(r.id), "name": r.name} for r in endpoint_rows],
        "metrics": [r[0] for r in metric_rows],
        "annotators": [{"id": str(r.id), "name": r.name} for r in annotator_rows],
        "requirements": [{"id": str(r.id), "name": r.name} for r in requirement_rows],
    }
