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
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.constants import TestType
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
    db: Session,
    requirement_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
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
    organization_id: str | None = None,
    user_id: str | None = None,
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
    organization_id: str | None = None,
    user_id: str | None = None,
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
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.Requirement:
    """Create requirement."""
    return create_item(db, models.Requirement, requirement, organization_id, user_id)


def update_requirement(
    db: Session,
    requirement_id: uuid.UUID,
    requirement: schemas.RequirementUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Requirement]:
    """Update requirement."""
    return update_item(
        db, models.Requirement, requirement_id, requirement, organization_id, user_id
    )


def delete_requirement(
    db: Session,
    requirement_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Requirement]:
    """Delete requirement."""
    return delete_item(db, models.Requirement, requirement_id, organization_id, user_id)


def get_test_counts_by_requirement(
    db: Session,
    requirement_ids: Iterable[uuid.UUID],
    organization_id: str,
    project_id: uuid.UUID | None = None,
) -> Dict[str, schemas.RequirementTestCounts]:
    """Linked-test counts per requirement, split by single-/multi-turn.

    Counts the same tests the ``/tests`` list shows for ``requirement_id eq ...``, so a card
    matches its detail page's Linked tests tab. The predicates are spelled out because the
    ambient soft-delete and scope listeners don't reliably cover a column-only grouped select
    (see ``crud.test.get_test_facets``). Untyped tests count as single-turn, as at run time.
    """
    ids = [uuid.UUID(str(r)) for r in requirement_ids]
    if not ids:
        return {}
    Test = models.Test
    is_multi_turn = models.TypeLookup.type_value == TestType.MULTI_TURN.value
    query = (
        db.query(Test.requirement_id, is_multi_turn, func.count(Test.id))
        .outerjoin(models.TypeLookup, Test.test_type_id == models.TypeLookup.id)
        .filter(
            Test.requirement_id.in_(ids),
            Test.deleted_at.is_(None),
            Test.explorer_row.is_(False),
            Test.metric_id.is_(None),
            Test.organization_id == uuid.UUID(str(organization_id)),
        )
        .group_by(Test.requirement_id, is_multi_turn)
    )
    if project_id is not None:
        # Mirrors the ambient project predicate: org-wide rows carry no project.
        query = query.filter(or_(Test.project_id == project_id, Test.project_id.is_(None)))

    counts = {str(rid): schemas.RequirementTestCounts() for rid in ids}
    for requirement_id, multi_turn, count in query.all():
        entry = counts[str(requirement_id)]
        if multi_turn:
            entry.multi_turn += count
        else:
            entry.single_turn += count
        entry.total += count
    return counts


def attach_test_counts(
    db: Session,
    requirements: List[models.Requirement],
    organization_id: str,
    project_id: uuid.UUID | None = None,
) -> List[models.Requirement]:
    """Set ``test_counts`` on each requirement for ``RequirementWithMetricsSchema``."""
    counts = get_test_counts_by_requirement(
        db, [r.id for r in requirements], organization_id, project_id
    )
    for requirement in requirements:
        requirement.test_counts = counts[str(requirement.id)]
    return requirements


def get_requirement_names(db: Session, requirement_ids: Iterable[str]) -> Dict[str, str]:
    """``{requirement_id: name}`` for the given ids; unknown or deleted ids are left out."""
    ids = [uuid.UUID(str(r)) for r in requirement_ids]
    if not ids:
        return {}
    rows = db.query(models.Requirement.id, models.Requirement.name).filter(
        models.Requirement.id.in_(ids)
    )
    return {str(rid): name for rid, name in rows.all()}


def get_scorable_metrics_by_requirement(
    db: Session, requirement_ids: Iterable[str]
) -> Dict[str, List[models.Metric]]:
    """Each requirement's metrics that can actually run (those with a ``class_name``)."""
    ids = [uuid.UUID(str(r)) for r in requirement_ids]
    if not ids:
        return {}
    association = models.requirement_metric_association
    rows = (
        db.query(association.c.requirement_id, models.Metric)
        .join(models.Metric, models.Metric.id == association.c.metric_id)
        .filter(association.c.requirement_id.in_(ids))
        .filter(models.Metric.class_name.isnot(None))
        .all()
    )
    by_requirement: Dict[str, List[models.Metric]] = {}
    for requirement_id, metric in rows:
        by_requirement.setdefault(str(requirement_id), []).append(metric)
    return by_requirement
