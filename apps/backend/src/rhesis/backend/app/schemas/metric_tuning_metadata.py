"""Pydantic validation for the ``Test.test_metadata`` JSONB of metric tuning cases.

Same contract as ``schemas/explorer_metadata.py``, and for the same reason: the
column is shared with other writers, so ``extra="allow"`` round-trips
unrecognized keys losslessly rather than raising or dropping them, every
``parse_*`` is total (garbage input becomes an all-defaults model), and dumping
is always ``model_dump(mode="json", exclude_none=True)`` at the call site so a
``None`` field comes back as an absent key rather than ``null``.

Two things live here, and the split matters. The ``result`` is machine output and
only the latest run's is kept (domain.local/adr/0004). The ``reviews`` are
human-authored and accumulate, because the comments in them are what someone
reads when rewriting an evaluation prompt -- wiping those on every run would
destroy the thing the feature produces (domain.local/adr/0005).
"""

import logging
from enum import Enum
from typing import Any, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

logger = logging.getLogger(__name__)

# How many reviews a case keeps. The cap exists because ADR-0004 is right that an
# unbounded blob in a column nothing paginates is a problem. Eviction skips any
# review carrying a comment, so a case reviewed with comments ten times over
# grows past this rather than losing them -- see ``evictable`` below.
REVIEW_HISTORY_LIMIT = 10


def _coerce_optional_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


class TuningRunStatus(str, Enum):
    """Where a metric's latest tuning run got to.

    ``NEVER_RUN`` is not stored -- it is what a metric with no summary yet reads
    as, so the API always has a status to return.
    """

    NEVER_RUN = "never_run"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewDecision(str, Enum):
    """What a reviewer said about the verdict a metric gave."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class MetricTuningCaseResult(BaseModel):
    """What the metric said about one case, from the latest run.

    Machine output, so only the latest run is kept and a new run overwrites this
    outright (domain.local/adr/0004). Reviews are the opposite and live beside
    it.

    ``verdict`` is the metric's own score rendered as a string whatever its score
    type -- a number for numeric, pass/fail for binary, a category name for
    categorical -- so a review can record the one it judged without branching per
    score type.

    ``error`` set means the metric call failed for this case. A failed call is
    deliberately not the same as a verdict a reviewer would reject -- a flaky
    provider should never read as a bad metric -- so the two never collapse into
    one field.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    # What the metric returned. None when the call failed.
    verdict: Optional[str] = None
    # The metric's own explanation of that verdict, where it produces one.
    reasoning: Optional[str] = None
    # Why the call failed, when it did.
    error: Optional[str] = None
    # When the metric was run over this case, ISO-8601 UTC.
    evaluated_at: Optional[str] = None

    @field_validator("verdict", "reasoning", "error", "evaluated_at", mode="before")
    @classmethod
    def _validate_optional_str(cls, v: Any) -> Optional[str]:
        return _coerce_optional_str(v)


class MetricTuningReview(BaseModel):
    """One reviewer's judgement of one verdict a metric gave.

    ``verdict`` and ``score_type`` are what the review was judging, recorded so a
    later run can tell whether the metric's decision actually moved. The bucket
    that decision falls in is **not** stored: it is derived on read from the
    metric's current threshold, so moving a threshold re-evaluates existing
    reviews instead of freezing yesterday's arithmetic (ADR-0005).

    ``comment`` is required on a rejection and is the point of the whole feature
    -- it is the raw material for rewriting the evaluation prompt.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    decision: ReviewDecision = ReviewDecision.ACCEPTED
    # What is wrong with the verdict. Always set on a rejection, never on an accept.
    comment: Optional[str] = None
    # The raw verdict this review was judging, and the score type it was judged under.
    verdict: Optional[str] = None
    score_type: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[str] = None

    @field_validator(
        "comment", "verdict", "score_type", "reviewer_id", "reviewed_at", mode="before"
    )
    @classmethod
    def _validate_optional_str(cls, v: Any) -> Optional[str]:
        return _coerce_optional_str(v)

    @property
    def evictable(self) -> bool:
        """Whether the history cap may drop this review.

        An accept carries nothing a human wrote, so it is the one that goes. A
        review with a comment is never evicted -- a cap that silently dropped
        those would destroy what the feature produces (ADR-0005).
        """
        return not (self.comment or "").strip()


class MetricTuningCaseMetadata(BaseModel):
    """``Test.test_metadata`` for metric-tuning rows.

    The latest run's result and the case's review history live here. The rest of
    a case is the payload shown to the metric -- input, output and reference
    answer, travelling together in ``prompt.content`` (ADR-0003). Nothing here is
    ever shown to the metric: a scorecard has to reflect the metric's judgement
    rather than its ability to read a reviewer's hint.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    # What the metric said last time it was run over this case.
    result: Optional[MetricTuningCaseResult] = None
    # Oldest first. Accumulates across runs, capped at REVIEW_HISTORY_LIMIT.
    reviews: List[MetricTuningReview] = []


class MetricTuningRunSummary(BaseModel):
    """The latest tuning run, stored under ``TestSet.attributes["tuning_run"]``.

    On the tuning test set rather than the metric because it is a fact about the
    set of cases, and because nothing else writes these attributes -- attribute
    regeneration early-returns for metric-owned sets.

    ``total_cases`` is how many cases the run set out to cover and ``completed``
    how many it has finished, which is what makes progress reportable while the
    run is still going.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    status: TuningRunStatus = TuningRunStatus.NEVER_RUN
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_cases: int = 0
    completed_cases: int = 0
    # How many cases the metric call failed on. Reported apart from the verdicts
    # so a flaky provider is visibly a flaky provider.
    errored_cases: int = 0
    # Why the run as a whole failed, when it did. A single case failing does not
    # fail the run -- that is `errored_cases`.
    error: Optional[str] = None

    @field_validator("error", "started_at", "completed_at", mode="before")
    @classmethod
    def _validate_optional_str(cls, v: Any) -> Optional[str]:
        return _coerce_optional_str(v)


def parse_metric_tuning_case_metadata(
    raw: Optional[Mapping[str, Any]],
) -> MetricTuningCaseMetadata:
    """Parse ``Test.test_metadata``. Never raises -- see module docstring."""
    try:
        return MetricTuningCaseMetadata.model_validate(raw or {})
    except ValidationError:
        logger.warning("Failed to parse metric tuning case metadata %r; using defaults", raw)
        return MetricTuningCaseMetadata()


def parse_metric_tuning_run_summary(
    raw: Optional[Mapping[str, Any]],
) -> MetricTuningRunSummary:
    """Parse ``TestSet.attributes["tuning_run"]``. Never raises.

    A metric that has never been run has no key at all, which parses to a
    ``NEVER_RUN`` summary rather than to None -- so callers never branch on
    absence.
    """
    try:
        return MetricTuningRunSummary.model_validate(raw or {})
    except ValidationError:
        logger.warning("Failed to parse metric tuning run summary %r; using defaults", raw)
        return MetricTuningRunSummary()
