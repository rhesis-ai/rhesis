"""API shapes for metric tuning cases.

A tuning case is one example of what a metric should say: an input, the recorded
output being judged, the verdict a human expects, and why. The verdict can be
filled in later, which leaves the case **unlabelled** in the meantime. It is
stored as a normal ``test`` + ``prompt`` pair owned by the metric -- see
``services/metric_tuning/cases.py`` for the column mapping.

``input``, ``output`` and ``expected_output`` are the **case payload**: what the
metric is shown. They are stored together in ``prompt.content`` because a tuning
case puts the metric in the system-under-test role (ADR-0003). ``expected`` is
the answer key and is stored apart from them, on ``prompt.expected_response``.

``expected`` is a plain string on purpose. The owning metric's ``score_type``
decides how to read it -- ``"pass"``/``"fail"`` for binary, ``"1.0"`` for
numeric, a category name for categorical -- so one field serves all three
without the API having to branch per metric. What keeps that honest is
``services/metric_tuning/verdict.py``, which checks the string against the metric
on the way in and again on the way out.
"""

from datetime import datetime
from typing import Optional, Union

from pydantic import UUID4, ConfigDict

from rhesis.backend.app.schemas import Base


class MetricTuningCaseBase(Base):
    # The input given to the system under test.
    input: str
    # The answer the metric has to judge.
    output: str
    # What the system under test should have answered. Optional -- plenty of
    # metrics judge an answer without a reference to compare it to.
    expected_output: Optional[str] = None
    # The verdict a human expects from the metric for this case. Absent on an
    # unlabelled case: one captured now and judged later.
    expected: Optional[str] = None
    # Why that verdict is right. Optional -- it is for the reviewer, not for scoring.
    rationale: Optional[str] = None


class MetricTuningCaseCreate(MetricTuningCaseBase):
    """A new case. Only the input and the answer being judged are required.

    Those two are what the metric evaluates, so without them there is nothing to
    run. A case saved without a verdict is an unlabelled case: runnable, but with
    nothing to compare the result against, so scoring skips it.
    """


class MetricTuningCaseUpdate(Base):
    """Partial update -- only the fields present are applied.

    ``expected`` reads absence and blankness differently: omitting it leaves the
    stored verdict alone, while sending a blank one takes the verdict back and
    returns the case to unlabelled.
    """

    input: Optional[str] = None
    output: Optional[str] = None
    expected_output: Optional[str] = None
    expected: Optional[str] = None
    rationale: Optional[str] = None


class MetricTuningCase(MetricTuningCaseBase):
    id: UUID4
    # True when `expected` no longer fits the metric's current score type, which
    # happens when the score type is changed after the case was written. Derived
    # on read, never stored -- see services/metric_tuning/verdict.py.
    is_stale: bool = False
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]

    model_config = ConfigDict(from_attributes=True)
