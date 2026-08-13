"""Pydantic validation for the ``Test.test_metadata`` JSONB of metric tuning cases.

Same contract as ``schemas/explorer_metadata.py``, and for the same reason: the
column is shared with other writers, so ``extra="allow"`` round-trips
unrecognized keys losslessly rather than raising or dropping them, every
``parse_*`` is total (garbage input becomes an all-defaults model), and dumping
is always ``model_dump(mode="json", exclude_none=True)`` at the call site so a
``None`` field comes back as an absent key rather than ``null``.

"""

import logging
from enum import Enum
from typing import Any, Mapping, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

logger = logging.getLogger(__name__)


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


class MetricTuningCaseResult(BaseModel):
    """What the metric said about one case, from the latest run.

    Only the latest run is kept, so a new run overwrites this outright rather
    than appending (domain.local/adr/0004).

    ``verdict`` is the metric's own score rendered as a string, for the same
    reason ``expected`` is one: a binary metric returns pass/fail, a numeric one
    a number, a categorical one a category name, and storing all three the same
    way keeps the comparison in one place instead of branching per score type at
    every read.

    ``error`` set means the metric call failed for this case. A failed call is
    deliberately not the same as a wrong verdict -- a flaky provider should never
    read as a bad metric -- so the two never collapse into one field.
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


class MetricTuningCaseMetadata(BaseModel):
    """``Test.test_metadata`` for metric-tuning rows.

    The rationale and the latest run's result live here. The rest of a case is
    either shown to the metric -- input, output and expected output, which travel
    together in ``prompt.content`` as the case payload -- or is the answer key,
    which is ``prompt.expected_response``. Neither the rationale nor the result
    is ever shown to the metric.

    ``rationale`` is ``Optional[str]`` so "key absent" (``None``) stays
    distinguishable from "key present but empty" (``""``).
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    # Why the human's verdict is what it is. Free text, for the reviewer.
    rationale: Optional[str] = None
    # What the metric said last time it was run over this case.
    result: Optional[MetricTuningCaseResult] = None

    @field_validator("rationale", mode="before")
    @classmethod
    def _validate_optional_str(cls, v: Any) -> Optional[str]:
        return _coerce_optional_str(v)


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
