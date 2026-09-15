"""Apply and revert the status override an annotation puts on its parent.

An annotation with a Pass/Fail verdict overrides the automated outcome of the
TestResult or Trace it targets: entity-level targets flip the parent's status,
metric and turn targets rewrite the matching entry inside the parent's metrics
JSONB and the parent status is recalculated from there.

The marker written into that JSONB keeps the key ``review_id``. Its value is the
annotation id (the backfill reuses each JSONB ``review_id`` as the annotation's
primary key), so every existing marker, ``v_metric_stats.has_override`` and the
insights built on them stay valid without touching the data.
"""

import uuid

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.annotation_override import test_result as _test_result
from rhesis.backend.app.services.annotation_override import trace as _trace


def _writer(parent):
    if isinstance(parent, models.TestResult):
        return _test_result
    if isinstance(parent, models.Trace):
        return _trace
    return None


def apply_override(db: Session, parent, annotation: models.Annotation) -> None:
    """Push an annotation's verdict onto its parent. No-op for parents without overrides."""
    writer = _writer(parent)
    if writer is None:
        return

    status = annotation.status or db.get(models.Status, annotation.status_id)
    if status is None:
        return

    writer.apply_override(parent, annotation, {"name": status.name, "status_id": str(status.id)})


def revert_override(
    db: Session,
    parent,
    target_type: str,
    target_reference: str | None,
    deleted_annotation_id: uuid.UUID,
) -> None:
    """Undo a deleted annotation's override, handing over to its most recent sibling if any."""
    writer = _writer(parent)
    if writer is None:
        return

    replacement = (
        db.query(models.Annotation)
        .filter(
            models.Annotation.entity_type == type(parent).__name__,
            models.Annotation.entity_id == parent.id,
            models.Annotation.target_type == target_type,
            models.Annotation.target_reference == target_reference,
            models.Annotation.id != deleted_annotation_id,
            models.Annotation.deleted_at.is_(None),
        )
        .order_by(models.Annotation.updated_at.desc())
        .first()
    )

    writer.revert_override(
        db, parent, target_type, target_reference, str(deleted_annotation_id), replacement
    )
