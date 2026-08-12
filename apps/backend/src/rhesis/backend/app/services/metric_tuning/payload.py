"""The case payload: what a tuning case shows its metric.

A tuning case puts the metric in the system-under-test role, so ``prompt.content``
holds what that system receives -- the whole case being judged, not just the
question. Input, output and the case's own expected response travel together,
serialized as JSON. See domain.local/adr/0003.

The verdict is deliberately **not** in here. It is the answer key, read by the
agreement check after the metric has spoken, and putting it in the payload would
show the metric what it is supposed to say (ADR-0002).

Parsing is total, the same contract as ``schemas/metric_tuning_metadata.py``:
content that will not parse comes back as an all-defaults payload carrying the
raw text as ``input``, so a case written before this shape existed still renders
as something a human can repair rather than vanishing or raising.
"""

import json
import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)


class CasePayload(BaseModel):
    """The situation a tuning case presents to its metric."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    # What was asked of the system under test.
    input: str = ""
    # The answer the metric has to judge.
    output: str = ""
    # What the system under test should have answered. Optional: plenty of
    # metrics judge an answer without a reference to compare it to.
    expected_output: Optional[str] = None


def serialize_payload(payload: CasePayload) -> str:
    """Render a payload for storage in ``prompt.content``."""
    return json.dumps(payload.model_dump(mode="json", exclude_none=True))


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
