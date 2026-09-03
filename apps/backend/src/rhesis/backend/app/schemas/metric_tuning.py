"""API shapes for metric tuning cases and the reviews of what a metric said.

A tuning case is one situation a metric has to get right: an input, the answer
being judged and -- where the metric needs one -- a reference answer. It records
no expected verdict. Nobody can honestly say what number a numeric metric
*should* have returned, while saying whether ``0.2`` is wrong is easy, so the
judgement happens after a run instead: a reviewer accepts what the metric said or
rejects it with a comment (domain.local/adr/0005).

The three case fields are the **case payload** -- what the metric is shown --
stored together in ``prompt.content`` because a tuning case puts the metric in
the system-under-test role (ADR-0003). Reviews are stored apart, in
``test.test_metadata``, and are never shown to the metric.

``outcome`` and ``review`` are both derived on read. A review is only still
standing while the metric's verdict has not materially changed under the metric's
current threshold, which is a question that cannot be answered once and stored.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict, Field

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.metric_tuning_metadata import ReviewDecision, TuningRunStatus
from rhesis.backend.app.schemas.metric_types import ScoreType, ThresholdOperator


class TuningCaseOutcome(str, Enum):
    """How one case stands after the latest run.

    ``UNREVIEWED`` is never counted as accepted: a set nobody looked at must not
    report itself as perfect, and the cases an edit just broke must not read as
    successes until someone looks.
    """

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    # The metric call failed. Not the same as a verdict a reviewer rejected.
    ERRORED = "errored"
    UNREVIEWED = "unreviewed"


class UnreviewedReason(str, Enum):
    """Why an unreviewed case is unreviewed. The work is the same either way,
    but a case that lost a review says so rather than looking untouched."""

    NEVER_JUDGED = "never_judged"
    INVALIDATED = "invalidated"


class MetricTuningCaseBase(Base):
    # The input given to the system under test.
    input: str
    # The answer the metric has to judge.
    output: str
    # What the system under test should have answered, for a metric that judges
    # against a reference. Never an "expected" anything -- that word belonged to
    # the retired expected verdict and the two were indistinguishable in the grid.
    reference_answer: Optional[str] = None


class MetricTuningCaseCreate(MetricTuningCaseBase):
    """A new case. The input and the answer being judged are both required --
    they are what the metric is run over, so without them there is nothing to
    run."""


class MetricTuningCaseUpdate(Base):
    """Partial update -- only the fields present are applied."""

    input: Optional[str] = None
    output: Optional[str] = None
    reference_answer: Optional[str] = None


class MetricTuningCaseResult(BaseModel):
    """What the metric said about this case in the latest run.

    Absent until the metric has been run over the case. ``error`` set means the
    call failed, which is deliberately not the same as a verdict a reviewer would
    reject.

    Plain ``BaseModel``, not the shared ``Base``: this is a value on a case, not a
    row. ``Base`` would add ``id``/``nano_id``/``project_id``, and an ``id`` here
    would advertise a handle that does not exist.
    """

    # The metric's own verdict, as a string, whatever its score type.
    verdict: Optional[str] = None
    # The metric's explanation, where it produces one.
    reasoning: Optional[str] = None
    # Set when the metric call failed for this case.
    error: Optional[str] = None
    evaluated_at: Optional[str] = None


class MetricTuningReview(BaseModel):
    """The review that currently stands for a case.

    ``verdict`` is the raw verdict the reviewer was judging, so the interface can
    show what the judgement was about. The review history behind this is not
    exposed: what a reader needs is the judgement that holds now and the comment
    that came with it.
    """

    decision: ReviewDecision
    # What is wrong with the verdict. Always present on a rejection.
    comment: Optional[str] = None
    verdict: Optional[str] = None
    reviewed_at: Optional[str] = None


class MetricTuningReviewCreate(BaseModel):
    """A reviewer's judgement of the verdict a case currently carries.

    The verdict being judged is read server-side from the stored result rather
    than sent, so a review can never claim to be about something the metric did
    not say.
    """

    decision: ReviewDecision
    # Required on a rejection: the comment is what someone reads when rewriting
    # the evaluation prompt, so a rejection without one records nothing useful.
    comment: Optional[str] = None


class MetricTuningCase(MetricTuningCaseBase):
    id: UUID4
    # The latest run's result for this case, or None if it has never been run.
    result: Optional[MetricTuningCaseResult] = None
    # Derived on read, both of them -- see the module docstring.
    outcome: TuningCaseOutcome = TuningCaseOutcome.UNREVIEWED
    review: Optional[MetricTuningReview] = None
    unreviewed_reason: Optional[UnreviewedReason] = None
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]

    model_config = ConfigDict(from_attributes=True)


class TuningAgreement(BaseModel):
    """How much of what the metric said the reviewer accepted.

    This is the one number an author watches while editing an evaluation prompt:
    change the wording, run again, see whether it went up.

    ``ratio`` is ``None`` when nothing has been judged, never ``1.0`` -- a set
    nobody has looked at has no agreement rather than a perfect one. It is
    computed from the stored reviews on every read and never written down, so a
    review a run has just invalidated stops counting immediately.

    ``judged`` travels with the ratio because a ratio without its denominator is
    not a measurement: three out of three should not read like a solved problem.
    """

    # accepted / (accepted + rejected). None when nothing has been judged.
    ratio: Optional[float] = None
    # The denominator -- accepted plus rejected, and nothing else.
    judged: int = 0
    accepted: int = 0
    rejected: int = 0
    # Left out of the ratio and reported beside it, never counted as accepted.
    unreviewed: int = 0
    # The metric call failed. Left out too, and kept apart from the verdicts so a
    # flaky provider never reads as a bad metric.
    errored: int = 0


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
    # Not part of the run at all -- reviews are written between runs and change
    # this without one. It travels with the run because that is the one thing the
    # tab already re-reads while a run is going, and the number has to move as the
    # cases land. Derived on every read; see ``TuningAgreement``.
    agreement: TuningAgreement = TuningAgreement()
    # True when the metric has changed in a verdict-affecting way since this run
    # started, so its agreement belongs to the earlier metric. Derived from the
    # stored fingerprint on every read; a run without one answers False, because
    # unknown is not the same as out of date.
    predates_metric: bool = False


class ImprovedMetricFields(BaseModel):
    """The metric fields a model may rewrite from a reviewer's rejections.

    Deliberately narrow: the evaluation fields and nothing else. No ids, no
    relations, no ``metric_scope`` -- a rejection says the metric judged one case
    wrongly, which is not an opinion about which turn shapes it applies to.

    Every field is required but nullable rather than optional-with-a-default, so
    the JSON schema handed to the model lists them all: a provider running strict
    structured output rejects a schema whose properties are not all required, and
    a numeric metric genuinely has no ``categories`` to give.

    ``score_type`` and ``categories`` are here because the model has to reason
    about the score bands coherently, not because it may move them -- both are
    overwritten with the metric's current values before this is returned. An
    improvement that changed ``score_type`` would invalidate every review for the
    metric, which is not something a button does quietly (domain.local/adr/0006).
    """

    name: str = Field(description="Title Case with spaces, e.g. 'Factual Accuracy'")
    description: str
    evaluation_prompt: str = Field(description="The evaluation criteria, no template placeholders")
    evaluation_steps: str
    reasoning: str
    explanation: str
    score_type: ScoreType
    min_score: Optional[float]
    max_score: Optional[float]
    threshold: Optional[float]
    threshold_operator: Optional[ThresholdOperator]
    categories: Optional[List[str]]
    passing_categories: Optional[List[str]]


class MetricTuningImprovement(BaseModel):
    """A proposed rewrite of a metric, read off the rejections its reviewers wrote.

    Producing one never writes anything. The reviewer sees the current fields
    beside these and applies them with an ordinary metric update, or does not --
    an in-place rewrite of the evaluation prompt the reviews were made against
    would have no diff and no undo (ADR-0006).

    ``changed`` is what the dialog shows; the fields it leaves out are named as
    unchanged rather than hidden, so the reviewer can see the rewrite left them
    alone. ``rejections_used`` is the header: how many comments this was written
    from.
    """

    improvement: ImprovedMetricFields
    # Names of the fields whose proposed value differs from the metric's current one.
    changed: List[str] = []
    rejections_used: int = 0


__all__ = [
    "ImprovedMetricFields",
    "MetricTuningCase",
    "MetricTuningCaseCreate",
    "MetricTuningCaseResult",
    "MetricTuningCaseUpdate",
    "MetricTuningImprovement",
    "MetricTuningReview",
    "MetricTuningReviewCreate",
    "MetricTuningRun",
    "TuningAgreement",
    "ReviewDecision",
    "TuningCaseOutcome",
    "UnreviewedReason",
]
