"""Deciding whether a stored review still describes what the metric says now.

A review judges one verdict the metric produced. A later run produces another
one, and the question this module answers is whether that new verdict is the
same *decision* as the one the reviewer looked at. If it is, the review stands.
If it is not, the review is invalidated and the case goes back to unreviewed --
see domain.local/adr/0005.

Sameness is decided on the **bucket**, not the string: a numeric score only
becomes a decision by crossing its threshold, so ``0.79 -> 0.81`` is noise under
a ``0.5`` threshold and a reversal under a ``0.8`` one. The bucket is derived
here, on read, from the metric's current threshold and passing categories, and
never stored -- moving a threshold has to re-evaluate the reviews that already
exist rather than freeze yesterday's arithmetic.

Where no bucket can be derived -- no threshold, a verdict that is not a number,
an unknown operator or score type -- the fallback is exact string equality, never
"it stands". Ordinary drift then invalidates, which is the safe direction: it
asks for a fresh look instead of keeping a review that may no longer hold.

Nothing here raises. It runs on every read of every case.
"""

import logging
from typing import Any, Optional

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric_types import (
    OPERATOR_MAP,
    ScoreType,
    ThresholdOperator,
)

logger = logging.getLogger(__name__)

# Returned instead of a bucket when this metric cannot produce one. Distinct
# from any real bucket value, including ``None`` and ``False``.
_NO_BUCKET = object()


def review_still_stands(
    metric: models.Metric,
    judged_verdict: Optional[str],
    judged_score_type: Optional[str],
    current_verdict: Optional[str],
) -> bool:
    """True when a review of ``judged_verdict`` still holds for ``current_verdict``.

    ``judged_verdict`` and ``judged_score_type`` are what the review recorded when
    it was made; ``current_verdict`` is what the latest run produced.
    """
    judged = _clean(judged_verdict)
    current = _clean(current_verdict)

    # Nothing to have judged, or nothing that was judged: no review to keep.
    if current is None or judged is None:
        return False

    # A different score type makes the two verdicts incomparable, whatever they say.
    if metric.score_type != judged_score_type:
        return False

    judged_bucket = _bucket(metric, judged)
    current_bucket = _bucket(metric, current)

    if judged_bucket is _NO_BUCKET or current_bucket is _NO_BUCKET:
        return judged == current

    return judged_bucket == current_bucket


def _clean(verdict: Optional[str]) -> Optional[str]:
    """The comparable form of a stored verdict; ``None`` when there is none."""
    if verdict is None:
        return None
    return str(verdict).strip() or None


def _bucket(metric: models.Metric, verdict: str) -> Any:
    """The decision ``verdict`` represents for this metric, or ``_NO_BUCKET``."""
    score_type = metric.score_type

    if score_type == ScoreType.BINARY.value:
        # A binary verdict is already the decision.
        return verdict.lower()

    if score_type == ScoreType.NUMERIC.value:
        return _numeric_bucket(metric, verdict)

    if score_type == ScoreType.CATEGORICAL.value:
        return _categorical_bucket(metric, verdict)

    logger.warning(
        "Metric %s has unrecognized score_type %r; comparing tuning verdicts as strings",
        metric.id,
        score_type,
    )
    return _NO_BUCKET


def _numeric_bucket(metric: models.Metric, verdict: str) -> Any:
    """Which side of the metric's threshold this score lands on."""
    try:
        threshold = float(metric.threshold)
        score = float(verdict)
    except (TypeError, ValueError):
        # No threshold to land either side of, or a verdict that is not a number.
        return _NO_BUCKET

    try:
        passes = OPERATOR_MAP[ThresholdOperator(metric.threshold_operator)]
    except (ValueError, KeyError):
        logger.warning(
            "Metric %s has unrecognized threshold_operator %r; "
            "comparing tuning verdicts as strings",
            metric.id,
            metric.threshold_operator,
        )
        return _NO_BUCKET

    return passes(score, threshold)


def _categorical_bucket(metric: models.Metric, verdict: str) -> Any:
    """Whether this category is one of the metric's passing ones."""
    passing = metric.passing_categories
    if not isinstance(passing, list) or not passing:
        return _NO_BUCKET
    return verdict.lower() in {str(category).strip().lower() for category in passing}
