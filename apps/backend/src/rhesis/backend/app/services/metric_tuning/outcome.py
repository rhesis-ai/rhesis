"""How one tuning case stands after the latest run.

Both the outcome and the review behind it are derived here, on every read, and
neither is stored. A stored outcome would freeze the arithmetic that produced it:
move the metric's threshold and yesterday's accept would still read as an accept
even though the verdict it was about now falls on the other side. See
domain.local/adr/0005 and ``material_change.py`` for the rule itself.

The four outcomes never collapse into fewer. An errored case is a provider that
could not be reached, not a metric a reviewer disagreed with, and an unreviewed
case is not an accepted one -- a set nobody looked at must not report itself as
perfect.
"""

import logging
from typing import Optional, Tuple

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric_tuning import TuningCaseOutcome, UnreviewedReason
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseMetadata,
    MetricTuningReview,
    ReviewDecision,
)
from rhesis.backend.app.services.metric_tuning.material_change import review_still_stands

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


def standing_review(
    metric: models.Metric, metadata: MetricTuningCaseMetadata
) -> Optional[MetricTuningReview]:
    """The newest review that still holds for the verdict the case carries now.

    Newest first, and the first one that still stands wins -- an older review of
    the same verdict is history, not the judgement in force.
    """
    verdict = current_verdict(metadata)
    for review in reversed(metadata.reviews):
        if review_still_stands(metric, review.verdict, review.score_type, verdict):
            return review
    return None


def case_outcome(
    metric: models.Metric, metadata: MetricTuningCaseMetadata
) -> Tuple[TuningCaseOutcome, Optional[MetricTuningReview], Optional[UnreviewedReason]]:
    """The case's outcome, the review it rests on, and why it is unreviewed."""
    result = metadata.result
    if result and result.error:
        return TuningCaseOutcome.ERRORED, None, None

    review = standing_review(metric, metadata)
    if review:
        outcome = (
            TuningCaseOutcome.ACCEPTED
            if review.decision == ReviewDecision.ACCEPTED
            else TuningCaseOutcome.REJECTED
        )
        return outcome, review, None

    # A case with reviews behind it but none of them standing had one taken away
    # by a material change, and says so -- the reviewer needs to know their
    # judgement was dropped rather than never made. With no verdict there was
    # nothing to judge in the first place.
    reason = (
        UnreviewedReason.INVALIDATED
        if metadata.reviews and current_verdict(metadata)
        else UnreviewedReason.NEVER_JUDGED
    )
    return TuningCaseOutcome.UNREVIEWED, None, reason
