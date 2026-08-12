"""Pydantic validation for the ``Test.test_metadata`` JSONB of metric tuning cases.

Same contract as ``schemas/explorer_metadata.py``, and for the same reason: the
column is shared with other writers, so ``extra="allow"`` round-trips
unrecognized keys losslessly rather than raising or dropping them, every
``parse_*`` is total (garbage input becomes an all-defaults model), and dumping
is always ``model_dump(mode="json", exclude_none=True)`` at the call site so a
``None`` field comes back as an absent key rather than ``null``.

"""

import logging
from typing import Any, Mapping, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

logger = logging.getLogger(__name__)


def _coerce_optional_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


class MetricTuningCaseMetadata(BaseModel):
    """``Test.test_metadata`` for metric-tuning rows.

    Only the rationale lives here. The rest of a case is either shown to the
    metric -- input, output and expected output, which travel together in
    ``prompt.content`` as the case payload -- or is the answer key, which is
    ``prompt.expected_response``. The rationale is neither: it is for whoever
    reviews the case later, and the metric never sees it.

    ``rationale`` is ``Optional[str]`` so "key absent" (``None``) stays
    distinguishable from "key present but empty" (``""``).
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    # Why the human's verdict is what it is. Free text, for the reviewer.
    rationale: Optional[str] = None

    @field_validator("rationale", mode="before")
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
