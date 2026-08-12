"""Validating an expected verdict against the metric that owns it.

The verdict is one string for all three score types -- ``"pass"`` for binary,
``"0.8"`` for numeric, a category name for categorical -- so the API never has to
branch per metric. That only holds if the string is checked against the owning
metric, which is what this module does.

The same check runs on write and on read. On write it rejects; on read it marks
the case stale, because a metric's ``score_type`` can change long after its cases
were written. Staleness is therefore derived, never stored -- a stored marker
would still say "stale" after the metric changed back.
"""

import logging
from typing import Optional

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric_types import ScoreType

logger = logging.getLogger(__name__)

# The two verdicts a binary metric can be expected to return. Stored lowercase so
# "Pass" and "pass" cannot both end up in the same tuning test set.
BINARY_VERDICTS = ("pass", "fail")


class InvalidVerdict(ValueError):
    """An expected verdict that does not fit its metric's score type."""


def _expected_shape(metric: models.Metric) -> str:
    """What a valid verdict looks like for this metric, for the error message."""
    score_type = metric.score_type

    if score_type == ScoreType.BINARY.value:
        return f"one of {' or '.join(BINARY_VERDICTS)}"

    if score_type == ScoreType.NUMERIC.value:
        if metric.min_score is not None and metric.max_score is not None:
            return f"a number between {metric.min_score} and {metric.max_score}"
        return "a number"

    if score_type == ScoreType.CATEGORICAL.value:
        categories = metric.categories or []
        return f"one of the metric's categories: {', '.join(categories)}"

    return "a value this metric can return"


def normalize_verdict(metric: models.Metric, verdict: str) -> str:
    """Check a verdict against the metric and return the form to store.

    For a verdict that is allowed to be absent, call ``normalize_optional_verdict``
    instead -- this one treats blank as just another value that fits no score type.

    Raises ``InvalidVerdict`` with a message naming what was expected. An
    unrecognized ``score_type`` accepts anything -- refusing would make a metric
    in a state this code does not know about impossible to tune at all.
    """
    score_type = metric.score_type
    candidate = verdict.strip()

    if score_type == ScoreType.BINARY.value:
        lowered = candidate.lower()
        if lowered not in BINARY_VERDICTS:
            raise InvalidVerdict(
                f"{verdict!r} is not a valid verdict for a binary metric -- "
                f"expected {_expected_shape(metric)}."
            )
        return lowered

    if score_type == ScoreType.NUMERIC.value:
        try:
            value = float(candidate)
        except ValueError:
            raise InvalidVerdict(
                f"{verdict!r} is not a number -- expected {_expected_shape(metric)}."
            ) from None
        # Only bound when the metric declares a range; a numeric metric without
        # one accepts any number.
        if metric.min_score is not None and value < metric.min_score:
            raise InvalidVerdict(f"{verdict!r} is below this metric's minimum score.")
        if metric.max_score is not None and value > metric.max_score:
            raise InvalidVerdict(f"{verdict!r} is above this metric's maximum score.")
        return candidate

    if score_type == ScoreType.CATEGORICAL.value:
        categories = metric.categories or []
        if candidate not in categories:
            raise InvalidVerdict(
                f"{verdict!r} is not one of this metric's categories -- "
                f"expected {_expected_shape(metric)}."
            )
        return candidate

    logger.warning(
        "Metric %s has unrecognized score_type %r; accepting verdict unchecked",
        metric.id,
        score_type,
    )
    return candidate


def normalize_optional_verdict(metric: models.Metric, verdict: Optional[str]) -> Optional[str]:
    """Same check, for a verdict that is allowed to be absent.

    Blank counts as absent, so an empty verdict control is stored as no verdict
    rather than as an empty-string one nothing can compare against.
    """
    if verdict is None or not verdict.strip():
        return None
    return normalize_verdict(metric, verdict)


def is_stale(metric: models.Metric, verdict: Optional[str]) -> bool:
    """True when a stored verdict no longer fits its metric's score type.

    An unlabelled case is never stale. Staleness is about a verdict that no
    longer fits, not an absent one -- there is nothing to re-label, only to
    label, and reporting the two as the same thing hides which is which.
    """
    if not verdict:
        return False
    try:
        normalize_verdict(metric, verdict)
    except InvalidVerdict:
        return True
    return False
