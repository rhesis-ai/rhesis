"""Reading a tuning judgement off an ``annotation`` row, and writing one back.

A tuning judgement is an annotation on the case: ``(Test, metric)`` with the
metric's id as the reference. The verdict it was made against travels in
``attributes`` rather than in a column, because it means nothing to any other
annotation -- only tuning re-reads a stored verdict to ask whether the metric has
moved since (``material_change``).

The decision itself is the annotation's **status**, which is what makes a tuning
judgement legible to everything that reads annotations generically: the hub shows
``Accepted`` / ``Rejected`` in the same column it shows ``Pass`` / ``Fail``.
Mapping it back to a decision is a name lookup, and a row whose status is neither
reads as no judgement at all rather than as an accept -- see ``decision_of``.
"""

import logging
from typing import List, Optional, Sequence

from rhesis.backend.app import models
from rhesis.backend.app.constants import AnnotationTarget
from rhesis.backend.app.schemas.metric_tuning import TuningDecision

logger = logging.getLogger(__name__)

# The status row each decision is stored as, under the ``Annotation`` entity type.
STATUS_NAMES: dict[TuningDecision, str] = {
    TuningDecision.ACCEPTED: "Accepted",
    TuningDecision.REJECTED: "Rejected",
}

_DECISIONS = {name.lower(): decision for decision, name in STATUS_NAMES.items()}


def judgements_for_metric(
    metric: models.Metric, annotations: Sequence[models.Annotation]
) -> List[models.Annotation]:
    """This metric's judgements among a case's annotations, newest first.

    The caller batch-loads every annotation on the case, and three kinds of row
    in there are not a judgement of this metric: an entity-level label left in
    the explorer, another metric's judgement, and one whose status is neither
    Accepted nor Rejected -- which is what the SDK and the MCP tools produce if
    they annotate a tuning case directly. All three are filtered out here rather
    than counted, because the count is what tells a reviewer whether a judgement
    of theirs was invalidated or never made.
    """
    reference = str(metric.id)
    return [
        annotation
        for annotation in annotations
        if annotation.target_type == AnnotationTarget.METRIC.value
        and annotation.target_reference == reference
        and decision_of(annotation) is not None
    ]


def decision_of(annotation: models.Annotation) -> Optional[TuningDecision]:
    """The decision this annotation records, or None if its status is not one.

    None rather than a default: a row carrying some other organization-defined
    status has not been accepted, and counting it as one would inflate the
    agreement ratio the whole feature is watched through.
    """
    name = getattr(annotation.status, "name", None)
    if not name:
        return None
    decision = _DECISIONS.get(name.strip().lower())
    if decision is None:
        logger.warning(
            "Tuning annotation %s carries status %r, which is neither Accepted nor Rejected",
            annotation.id,
            name,
        )
    return decision


def judged_verdict(annotation: models.Annotation) -> Optional[str]:
    """The metric verdict this judgement was made against."""
    return _str_or_none((annotation.attributes or {}).get("verdict"))


def judged_score_type(annotation: models.Annotation) -> Optional[str]:
    """The score type that verdict was read under. See ``annotations._record``."""
    return _str_or_none((annotation.attributes or {}).get("score_type"))


def _str_or_none(value) -> Optional[str]:
    return None if value is None else str(value)
