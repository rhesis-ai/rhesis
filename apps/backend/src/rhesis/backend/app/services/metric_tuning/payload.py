"""The case payload: what a tuning case shows its metric.

A tuning case puts the metric in the system-under-test role, so ``prompt.content``
holds what that system receives -- the whole case being judged, not just the
question. Input, output and the case's reference answer travel together,
serialized as JSON. See domain.local/adr/0003.

Nothing a human wrote about the case is in here. There is no expected verdict any
more (ADR-0005), but the structural rule it protected still holds: a review and
its comment are written after the metric has spoken and must never enter the
invocation, or the scorecard measures the metric's ability to read a hint.

Parsing is total, the same contract as ``schemas/metric_tuning_metadata.py``:
content that will not parse comes back as an all-defaults payload carrying the
raw text as ``input``, so a case written before this shape existed still renders
as something a human can repair rather than vanishing or raising.
"""

import json
import logging
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


class CasePayload(BaseModel):
    """The situation a tuning case presents to its metric."""

    model_config = ConfigDict(extra="allow", validate_assignment=True, populate_by_name=True)

    # What was asked of the system under test.
    input: str = ""
    # The answer the metric has to judge.
    output: str = ""
    # What the system under test should have answered. Optional: plenty of
    # metrics judge an answer without a reference to compare it to.
    #
    # Read under its old name too. Cases written before ADR-0005 retired the word
    # "expected" from this field still have `expected_output` in their stored
    # payload, and a rename that dropped their reference answer would be a silent
    # edit to the thing being scored.
    reference_answer: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("reference_answer", "expected_output"),
    )


def serialize_payload(payload: CasePayload) -> str:
    """Render a payload for storage in ``prompt.content``."""
    return json.dumps(payload.model_dump(mode="json", exclude_none=True, by_alias=False))


def parse_payload(content: Optional[str]) -> CasePayload:
    """Parse ``prompt.content``. Never raises -- see module docstring."""
    if not content:
        return CasePayload()
    try:
        raw = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        # Not JSON: almost certainly a case stored before the payload existed,
        # when content held the bare input.
        return CasePayload(input=content)

    if not isinstance(raw, dict):
        return CasePayload(input=content)

    try:
        return CasePayload.model_validate(raw)
    except ValidationError:
        logger.warning("Failed to parse tuning case payload %r; using defaults", content)
        return CasePayload(input=content)
