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

from pydantic import UUID4, BaseModel, ConfigDict

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.metric_tuning_metadata import TuningRunStatus


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


class MetricTuningCaseResult(BaseModel):
    """What the metric said about this case in the latest run.

    Absent until the metric has been run over the case. ``verdict`` is the
    metric's own answer, to be read beside ``expected`` -- which is what the
    human said it should be, and which the metric never sees.

    Plain ``BaseModel``, not the shared ``Base``: this is a value on a case, not
    a row. ``Base`` would add ``id``/``nano_id``/``project_id``, and an ``id``
    here would advertise a handle that does not exist.
    """

    # The metric's own verdict, as a string, whatever its score type.
    verdict: Optional[str] = None
    # The metric's explanation, where it produces one.
    reasoning: Optional[str] = None
    # Set when the metric call failed for this case. Not the same as a wrong
    # verdict, and never reported as one.
    error: Optional[str] = None
    evaluated_at: Optional[str] = None


class MetricTuningCase(MetricTuningCaseBase):
    id: UUID4
    # True when `expected` no longer fits the metric's current score type, which
    # happens when the score type is changed after the case was written. Derived
    # on read, never stored -- see services/metric_tuning/verdict.py.
    is_stale: bool = False
    # The latest run's result for this case, or None if it has never been run.
    result: Optional[MetricTuningCaseResult] = None
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]

    model_config = ConfigDict(from_attributes=True)


class MetricTuningRun(BaseModel):
    """The state of a metric's latest tuning run.

    Only the latest is kept -- a new run overwrites the previous one, per
    domain.local/adr/0004. A metric that has never been run reads as
    ``never_run`` rather than as an absent object, so the interface has one
    shape to render either way.

    Plain ``BaseModel``, not the shared ``Base``: a run is stored in JSONB and is
    deliberately not a row (ADR-0004), so it has no id to expose. Inheriting
    ``Base`` would put a null ``id`` on every response and suggest otherwise.
    """

    status: TuningRunStatus = TuningRunStatus.NEVER_RUN
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    # How many cases the run set out to cover, and how many it has finished.
    # The pair is what makes progress reportable while a run is still going.
    total_cases: int = 0
    completed_cases: int = 0
    # Cases whose metric call failed. Reported apart from the verdicts.
    errored_cases: int = 0
    # Why the run as a whole failed. A single case failing does not fail a run.
    error: Optional[str] = None
