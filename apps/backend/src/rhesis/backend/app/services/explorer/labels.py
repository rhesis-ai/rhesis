"""The human label on an explorer test, which is an annotation on it.

A label has two possible authors and they are not interchangeable. A metric that
evaluated the test writes ``pass``/``fail`` into ``test_metadata`` naming itself
as the ``labeler``; a person who labels the same test writes an ``annotation``
row. Storing them apart is what keeps both: one metadata key could only hold
whichever was written last, so a person's label used to destroy the metric's.

**A human label wins on read.** ``effective_label`` prefers the newest annotation
and falls back to the metric's, which is what lets the tree, the import/export
copy and everything downstream agree on what a test is labelled without any of
them knowing where the label came from.

Labels are per person. The annotation written here is the caller's own, so
labelling a test twice moves your label instead of adding a second one, and
clearing it removes yours and leaves everyone else's alone. That is the one place
the explorer differs from the rest of annotations, where a second judgement is a
second row -- a tree cell shows one label, so a person editing theirs has to be
editing, not appending.
"""

import uuid
from typing import List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import AnnotationTarget, EntityType
from rhesis.backend.app.crud.annotation import create_annotation
from rhesis.backend.app.schemas.explorer_metadata import ExplorerTestMetadata
from rhesis.backend.app.utils.crud_utils import get_or_create_status

#: What ``meta.labeler`` says when the label came from a person rather than a metric.
HUMAN_LABELER = "user"

#: Labels a person can set, and the status row each is stored as. Pass and Fail
#: live under the ``TestResult`` entity type because that is where every
#: organization already has them -- a parallel pair under ``Test`` would be the
#: same two verdicts under a second name.
LABEL_STATUS_NAMES = {"pass": "Pass", "fail": "Fail"}

#: Clearing a label. Distinct from "no label was given", which is ``None``.
CLEARED = ""

_LABELS = {name.lower(): label for label, name in LABEL_STATUS_NAMES.items()}


def entity_level(annotations: Sequence[models.Annotation]) -> List[models.Annotation]:
    """The annotations that label the test itself, newest first.

    A tuning judgement on the same row targets a metric, not the test, so it is
    not a label and is filtered out here.
    """
    return [
        annotation
        for annotation in annotations
        if annotation.target_type == AnnotationTarget.TEST.value
    ]


def label_of(annotation: models.Annotation) -> Optional[str]:
    """The explorer label this annotation carries, or None if its status is not one."""
    name = getattr(annotation.status, "name", None)
    return _LABELS.get(name.strip().lower()) if name else None


def effective_label(
    meta: ExplorerTestMetadata, annotations: Sequence[models.Annotation]
) -> Tuple[str, Optional[str]]:
    """The label to show for a test and who set it. A person's beats a metric's.

    The labeler comes back exactly as stored, so ``None`` means the metadata
    names nobody. Callers supply their own default for that -- the tree shows
    ``imported``, a copy stamps itself -- because the two answers are different
    and a default chosen here would silently override both.
    """
    for annotation in entity_level(annotations):
        label = label_of(annotation)
        if label:
            return label, HUMAN_LABELER
    return meta.label, meta.labeler


def is_human_label(label: Optional[str], labeler: Optional[str]) -> bool:
    """Whether a write means "a person labelled this", and so is an annotation.

    A metric's own verdict and an imported one both travel in the metadata: they
    are facts about where the test came from, not judgements anybody made here.
    """
    return labeler == HUMAN_LABELER and label in LABEL_STATUS_NAMES


def set_label(
    db: Session,
    test_id: uuid.UUID,
    label: str,
    organization_id: str,
    user_id: str,
) -> Optional[models.Annotation]:
    """Record, move or clear the caller's own label on a test.

    Returns the annotation now standing for this caller, or None once it is
    cleared. A ``label`` that is neither a verdict nor ``CLEARED`` -- ``error``
    from a failed metric call, say -- is not a person's judgement and is left to
    the metadata.

    Flushes and never commits, so the label lands in the same transaction as the
    rest of the node write. The two writes that act on the caller's existing row
    set its columns directly rather than going back through CRUD, which would
    commit on its own and split one edit across two transactions.
    """
    if label != CLEARED and label not in LABEL_STATUS_NAMES:
        return None

    mine = (
        db.query(models.Annotation)
        .filter(
            models.Annotation.entity_type == EntityType.TEST.value,
            models.Annotation.entity_id == test_id,
            models.Annotation.target_type == AnnotationTarget.TEST.value,
            models.Annotation.user_id == user_id,
            models.Annotation.deleted_at.is_(None),
        )
        .order_by(models.Annotation.created_at.desc())
        .first()
    )

    if label == CLEARED:
        if mine is not None:
            mine.soft_delete()
            db.flush()
        return None

    status = get_or_create_status(
        db,
        name=LABEL_STATUS_NAMES[label],
        entity_type=EntityType.TEST_RESULT,
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )

    if mine is not None:
        mine.status_id = status.id
        db.flush()
        return mine

    return create_annotation(
        db,
        {
            "entity_type": EntityType.TEST.value,
            "entity_id": test_id,
            "target_type": AnnotationTarget.TEST.value,
            "status_id": status.id,
        },
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )
