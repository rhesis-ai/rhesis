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

from sqlalchemy import delete, func, or_, update
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
    include(models.Requirement.parent),
    include(models.Requirement.requirement_type),
    include(models.Requirement.impact),
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


def get_requirement_descriptions(db: Session, names: Iterable[str]) -> Dict[str, str]:
    """``{name: description}`` for requirements with these exact names and a description.

    Names are not unique. A project requirement wins over an organization-level one with
    the same name, and the newest wins after that.
    """
    names = list(names)
    if not names:
        return {}
    rows = (
        db.query(models.Requirement.name, models.Requirement.description)
        .filter(
            models.Requirement.name.in_(names),
            models.Requirement.description.isnot(None),
            models.Requirement.description != "",
        )
        # Later rows overwrite earlier ones in the dict below.
        .order_by(models.Requirement.project_id.isnot(None), models.Requirement.created_at)
    )
    return {name: description for name, description in rows.all()}


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


def get_parent_ids(db: Session, requirement_ids: Iterable[uuid.UUID]) -> Dict[str, Optional[str]]:
    """``{requirement_id: parent_id}`` for the given ids; unknown or deleted ids are left out."""
    ids = [uuid.UUID(str(r)) for r in requirement_ids]
    if not ids:
        return {}
    rows = db.query(models.Requirement.id, models.Requirement.parent_id).filter(
        models.Requirement.id.in_(ids), models.Requirement.deleted_at.is_(None)
    )
    return {str(rid): (str(pid) if pid else None) for rid, pid in rows.all()}


def get_children_counts(db: Session, requirement_ids: Iterable[uuid.UUID]) -> Dict[str, int]:
    """Live child requirements per requirement id."""
    ids = [uuid.UUID(str(r)) for r in requirement_ids]
    if not ids:
        return {}
    rows = (
        db.query(models.Requirement.parent_id, func.count(models.Requirement.id))
        .filter(models.Requirement.parent_id.in_(ids), models.Requirement.deleted_at.is_(None))
        .group_by(models.Requirement.parent_id)
    )
    return {str(pid): count for pid, count in rows.all()}


def get_example_counts(db: Session, requirement_ids: Iterable[uuid.UUID]) -> Dict[str, int]:
    """Live annotations linked to each requirement."""
    ids = [uuid.UUID(str(r)) for r in requirement_ids]
    if not ids:
        return {}
    rows = (
        db.query(models.Annotation.requirement_id, func.count(models.Annotation.id))
        .filter(models.Annotation.requirement_id.in_(ids), models.Annotation.deleted_at.is_(None))
        .group_by(models.Annotation.requirement_id)
    )
    return {str(rid): count for rid, count in rows.all()}


def get_sources_by_requirement(
    db: Session, requirement_ids: Iterable[uuid.UUID]
) -> Dict[str, List[schemas.RequirementSourceRef]]:
    """Each requirement's linked sources, with the note stored on the link, by title."""
    ids = [uuid.UUID(str(r)) for r in requirement_ids]
    if not ids:
        return {}
    link = models.requirement_source_association
    rows = (
        db.query(
            link.c.requirement_id,
            link.c.note,
            models.Source.id,
            models.Source.title,
            models.Source.url,
            models.Source.source_metadata,
            models.TypeLookup.id,
            models.TypeLookup.type_value,
        )
        .join(models.Source, models.Source.id == link.c.source_id)
        .outerjoin(models.TypeLookup, models.TypeLookup.id == models.Source.source_type_id)
        .filter(link.c.requirement_id.in_(ids), models.Source.deleted_at.is_(None))
        .order_by(models.Source.title)
        .all()
    )
    by_requirement: Dict[str, List[schemas.RequirementSourceRef]] = {}
    for requirement_id, note, source_id, title, url, metadata, type_id, type_value in rows:
        # A website source added by link keeps it in its metadata, not the url column.
        if not url and isinstance(metadata, dict):
            url = metadata.get("url")
        source_type = (
            schemas.RequirementSourceTypeRef(id=type_id, type_value=type_value) if type_id else None
        )
        by_requirement.setdefault(str(requirement_id), []).append(
            schemas.RequirementSourceRef(
                id=source_id, title=title, url=url, source_type=source_type, note=note
            )
        )
    return by_requirement


def link_source(
    db: Session,
    requirement_id: uuid.UUID,
    source_id: uuid.UUID,
    note: Optional[str],
    organization_id: str,
    user_id: str,
) -> bool:
    """Link a source to a requirement, or update the note if already linked.

    Returns True when a new link was made.
    """
    link = models.requirement_source_association
    existing = (
        db.query(link.c.requirement_id)
        .filter(link.c.requirement_id == requirement_id, link.c.source_id == source_id)
        .first()
    )
    if existing:
        db.execute(
            update(link)
            .where(link.c.requirement_id == requirement_id, link.c.source_id == source_id)
            .values(note=note)
        )
        return False
    db.execute(
        link.insert().values(
            requirement_id=requirement_id,
            source_id=source_id,
            note=note,
            user_id=user_id,
            organization_id=organization_id,
        )
    )
    return True


def unlink_source(db: Session, requirement_id: uuid.UUID, source_id: uuid.UUID) -> bool:
    """Remove a source link. Returns False when there was none."""
    link = models.requirement_source_association
    linked = (
        db.query(link.c.requirement_id)
        .filter(link.c.requirement_id == requirement_id, link.c.source_id == source_id)
        .first()
    )
    if linked is None:
        return False
    db.execute(
        delete(link).where(link.c.requirement_id == requirement_id, link.c.source_id == source_id)
    )
    return True


def get_example_annotations(db: Session, requirement_id: uuid.UUID) -> List[models.Annotation]:
    """Live annotations linked to a requirement, newest first."""
    return (
        db.query(models.Annotation)
        .options(
            include(models.Annotation.user),
            include(models.Annotation.status),
            include(models.Annotation.resolved_by),
        )
        .filter(
            models.Annotation.requirement_id == requirement_id,
            models.Annotation.deleted_at.is_(None),
        )
        .order_by(models.Annotation.created_at.desc(), models.Annotation.id.desc())
        .all()
    )


def set_requirement_review(db: Session, requirement: models.Requirement, review: dict) -> None:
    requirement.review = review
    db.flush()
