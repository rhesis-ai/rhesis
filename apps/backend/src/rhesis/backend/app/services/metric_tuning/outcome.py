"""How one tuning case stands after the latest run.

Both the outcome and the annotation behind it are derived here, on every read,
and neither is stored. A stored outcome would freeze the arithmetic that produced
it: move the metric's threshold and yesterday's accept would still read as an
accept even though the verdict it was about now falls on the other side. See
domain.local/adr/0005 and ``material_change.py`` for the rule itself.

The four outcomes never collapse into fewer. An errored case is a provider that
could not be reached, not a metric a reviewer disagreed with, and an unannotated
case is not an accepted one -- a set nobody looked at must not report itself as
perfect.
"""

import logging
from typing import Optional, Sequence, Tuple

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric_tuning import (
    TuningCaseOutcome,
    TuningDecision,
    UnannotatedReason,
)
from rhesis.backend.app.schemas.metric_tuning_metadata import MetricTuningCaseMetadata
from rhesis.backend.app.services.metric_tuning.judgement import (
    decision_of,
    judged_score_type,
    judged_verdict,
    judgements_for_metric,
)
from rhesis.backend.app.services.metric_tuning.material_change import annotation_still_stands

logger = logging.getLogger(__name__)


def current_verdict(metadata: MetricTuningCaseMetadata) -> Optional[str]:
    """The verdict a reviewer would be judging, or None if there is not one.

    A case whose metric call failed has no verdict to judge, however much text
    the failure left behind.
    """
    result = metadata.result
    if not result or result.error:
        return None
    return result.verdict


def standing_annotation(
    metric: models.Metric,
    metadata: MetricTuningCaseMetadata,
    annotations: Sequence[models.Annotation],
) -> Optional[models.Annotation]:
    """The newest annotation that still holds for the verdict the case carries now."""
    return _standing(metric, metadata, judgements_for_metric(metric, annotations))


def _standing(
    metric: models.Metric,
    metadata: MetricTuningCaseMetadata,
    judgements: Sequence[models.Annotation],
) -> Optional[models.Annotation]:
    """Pick the judgement in force from this metric's, already filtered and newest first.

    The first one that still stands wins -- re-judging a case leaves the earlier
    row as history rather than overwriting it, and an older judgement of the same
    verdict is not the one in force.

    Whoever wrote it does not matter. A metric is tuned by everyone who annotated
    it, not only by whoever is looking now.
    """
    verdict = current_verdict(metadata)
    for judgement in judgements:
        if annotation_still_stands(
            metric,
            judged_verdict(judgement),
            judged_score_type(judgement),
            verdict,
        ):
            return judgement
    return None


def case_outcome(
    metric: models.Metric,
    metadata: MetricTuningCaseMetadata,
    annotations: Sequence[models.Annotation],
) -> Tuple[TuningCaseOutcome, Optional[models.Annotation], Optional[UnannotatedReason]]:
    """The case's outcome, the annotation it rests on, and why it is unannotated."""
    result = metadata.result
    if result and result.error:
        return TuningCaseOutcome.ERRORED, None, None

    judgements = judgements_for_metric(metric, annotations)
    annotation = _standing(metric, metadata, judgements)
    if annotation:
        outcome = (
            TuningCaseOutcome.ACCEPTED
            if decision_of(annotation) == TuningDecision.ACCEPTED
            else TuningCaseOutcome.REJECTED
        )
        return outcome, annotation, None

    # A case with judgements behind it but none of them standing had one taken
    # away by a material change, and says so -- the reviewer needs to know their
    # judgement was dropped rather than never made. With no verdict there was
    # nothing to judge in the first place.
    reason = (
        UnannotatedReason.INVALIDATED
        if judgements and current_verdict(metadata)
        else UnannotatedReason.NEVER_JUDGED
    )
    return TuningCaseOutcome.UNANNOTATED, None, reason
