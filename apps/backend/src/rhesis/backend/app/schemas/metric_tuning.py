"""API shapes for metric tuning cases.

A tuning case is one labelled example of what a metric should say: an input, the
recorded output being judged, the verdict a human expects, and why. It is stored
as a normal ``test`` + ``prompt`` pair owned by the metric -- see
``services/metric_tuning/cases.py`` for the column mapping.

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
    # The verdict a human expects from the metric for this case.
    expected: str
    # Why that verdict is right. Optional -- it is for the reviewer, not for scoring.
    rationale: Optional[str] = None


class MetricTuningCaseCreate(MetricTuningCaseBase):
    """A new case. Input, output and verdict are all required.

    A case without a verdict carries no judgement and cannot be scored, so there
    is no draft state to model.
    """


class MetricTuningCaseUpdate(Base):
    """Partial update -- only the fields present are applied."""

    input: Optional[str] = None
    output: Optional[str] = None
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
