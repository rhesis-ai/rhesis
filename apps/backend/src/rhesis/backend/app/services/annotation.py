"""Annotation writes, with the status override they imply on the parent.

Creating, retargeting or deleting an annotation on a TestResult or Trace applies
or reverts the parent's status override (see ``services.annotation_override``),
so those writes go through here rather than straight to CRUD.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.constants import ENTITY_LEVEL_TARGETS, EntityType
from rhesis.backend.app.crud import annotation as annotation_crud
from rhesis.backend.app.services.annotation_override import apply_override, revert_override
from rhesis.backend.app.services.verdict_matrix_cache import get_verdict_matrix_cache

_PARENT_MODELS = {
    EntityType.TEST_RESULT.value: models.TestResult,
    EntityType.TRACE.value: models.Trace,
    EntityType.TEST.value: models.Test,
}

# Parents whose automated status an annotation can override.
_OVERRIDABLE = (models.TestResult, models.Trace)


def _load_parent(db: Session, entity_type: str, entity_id: uuid.UUID):
    model = _PARENT_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot annotate '{entity_type}'. Must be one of: {', '.join(_PARENT_MODELS)}",
        )
    parent = db.query(model).filter(model.id == entity_id).first()
    if parent is None:
        raise HTTPException(status_code=404, detail=f"{entity_type} {entity_id} not found")
    return parent


def _validate_status(db: Session, status_id: uuid.UUID) -> None:
    if db.query(models.Status).filter(models.Status.id == status_id).first() is None:
        raise HTTPException(status_code=404, detail="Status not found")


def _snapshot_original_status(db: Session, parent) -> None:
    """Record the automated verdict before the first annotation overwrites it.

    Without it ``matches_annotation`` would compare an annotation against a status
    the annotation itself just set, and every override would look like agreement.
    """
    if parent.original_status_id is not None:
        return
    current = getattr(parent, "status_id", None) or getattr(parent, "trace_metrics_status_id", None)
    if current is not None:
        parent.original_status_id = current
        db.flush()


def _commit(db: Session, parent) -> None:
    # Explicit commit: FastAPI's dependency cleanup would otherwise race the next
    # request. Cache invalidation follows it so no reader repopulates stale rows.
    db.commit()
    test_run_id = getattr(parent, "test_run_id", None)
    if test_run_id is not None:
        get_verdict_matrix_cache().invalidate(str(test_run_id))


def _org_id(current_user: models.User) -> str | None:
    return str(current_user.organization_id) if current_user.organization_id else None


def _fetch(db: Session, annotation_id: uuid.UUID, current_user: models.User):
    return annotation_crud.get_annotation(
        db,
        annotation_id,
        organization_id=_org_id(current_user),
        user_id=str(current_user.id),
    )


def _require(db: Session, annotation_id: uuid.UUID, current_user: models.User):
    annotation = _fetch(db, annotation_id, current_user)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


def create_annotation(
    db: Session,
    data: schemas.AnnotationCreate,
    current_user: models.User,
) -> models.Annotation:
    entity_type = EntityType.get_value(data.entity_type)
    parent = _load_parent(db, entity_type, data.entity_id)
    _validate_status(db, data.status_id)

    target = data.target
    annotation = annotation_crud.create_annotation(
        db,
        {
            "entity_type": entity_type,
            "entity_id": data.entity_id,
            "target_type": target.type if target else ENTITY_LEVEL_TARGETS[entity_type],
            "target_reference": target.reference if target else None,
            "status_id": data.status_id,
            "comments": data.comments,
            "attributes": data.attributes,
        },
        organization_id=_org_id(current_user),
        user_id=str(current_user.id),
    )

    if isinstance(parent, _OVERRIDABLE):
        _snapshot_original_status(db, parent)
        apply_override(db, parent, annotation)

    _commit(db, parent)
    return _fetch(db, annotation.id, current_user)


def update_annotation(
    db: Session,
    annotation_id: uuid.UUID,
    data: schemas.AnnotationUpdate,
    current_user: models.User,
) -> models.Annotation:
    annotation = _require(db, annotation_id, current_user)
    old_target = (annotation.target_type, annotation.target_reference)

    if data.status_id is not None:
        _validate_status(db, data.status_id)

    fields = data.model_dump(exclude_unset=True)
    target = fields.pop("target", None)
    if target:
        fields["target_type"] = target["type"]
        fields["target_reference"] = target.get("reference")
    if data.resolved is not None and data.resolved != annotation.resolved:
        fields["resolved_at"] = datetime.now(timezone.utc) if data.resolved else None
        fields["resolved_by_id"] = current_user.id if data.resolved else None

    annotation_crud.update_annotation(db, annotation_id, fields, _org_id(current_user))
    annotation = _require(db, annotation_id, current_user)

    parent = _load_parent(db, annotation.entity_type, annotation.entity_id)
    if isinstance(parent, _OVERRIDABLE):
        new_target = (annotation.target_type, annotation.target_reference)
        if new_target != old_target:
            revert_override(db, parent, old_target[0], old_target[1], annotation_id)
        apply_override(db, parent, annotation)

    _commit(db, parent)
    return _fetch(db, annotation_id, current_user)


def delete_annotation(
    db: Session,
    annotation_id: uuid.UUID,
    current_user: models.User,
) -> models.Annotation:
    annotation = _require(db, annotation_id, current_user)
    parent = _load_parent(db, annotation.entity_type, annotation.entity_id)

    if isinstance(parent, _OVERRIDABLE):
        revert_override(
            db, parent, annotation.target_type, annotation.target_reference, annotation_id
        )

    deleted = annotation_crud.delete_annotation(db, annotation_id, _org_id(current_user))
    _commit(db, parent)
    return deleted
