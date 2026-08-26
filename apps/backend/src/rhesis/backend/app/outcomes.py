"""The single vocabulary for pass/fail/error across the platform.

Two axes, not one. Today's codebase stores a single free-text status name
and asks every reader to reconstruct both of these from it -- which is why
"Failed" means three unrelated things depending on where you read it. See
``playground/outcome-model/inventory.md`` for the full audit (14
vocabularies, 7 duplicated classifiers, 10 user-visible bugs) and
``playground/outcome-model/proposal.md`` for the design this implements.

``Execution`` -- did we obtain a usable observation?
    NOT_RUN, RUNNING, OK, ERROR, CANCELLED

``Verdict`` -- given it ran, did it meet its criteria?
    PASS, FAIL, INCONCLUSIVE

A verdict is only meaningful when execution is OK. That is the invariant a
single status field cannot express, and the reason "the endpoint 500'd" and
"the endpoint answered wrong" have always collapsed into one bucket.

``Outcome`` is the single derived value every layer displays and aggregates
on -- the (execution, verdict) pair projected down to one of six values.
Nothing outside this module should invent a seventh.
"""

from enum import Enum
from typing import Any, Dict, Optional, Tuple


class Execution(str, Enum):
    NOT_RUN = "not_run"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class Outcome(str, Enum):
    """What every layer displays and aggregates on. Six values, no more."""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    CANCELLED = "cancelled"
    PENDING = "pending"


_OUTCOME_BY_VERDICT = {
    Verdict.PASS: Outcome.PASS,
    Verdict.FAIL: Outcome.FAIL,
    Verdict.INCONCLUSIVE: Outcome.INCONCLUSIVE,
}


def outcome_of(execution: Execution, verdict: Optional[Verdict] = None) -> Outcome:
    """Project (execution, verdict) down to the one value every layer renders.

    Raises on the two combinations that would mean the caller has the model
    wrong, rather than silently picking one: a verdict is required when
    execution is OK (there is nothing else to derive an outcome from) and
    forbidden otherwise (an errored, cancelled, or unrun test has no
    verdict to report, whatever a stray value on the row might say).
    """
    if execution == Execution.OK:
        if verdict is None:
            raise ValueError("execution == OK requires a verdict")
        return _OUTCOME_BY_VERDICT[verdict]

    if verdict is not None:
        raise ValueError(f"execution == {execution.value} must not carry a verdict")

    if execution == Execution.ERROR:
        return Outcome.ERROR
    if execution == Execution.CANCELLED:
        return Outcome.CANCELLED
    return Outcome.PENDING  # NOT_RUN, RUNNING


def classify_metrics(
    metrics: Optional[Dict[str, Any]], *, http_error: bool = False
) -> Tuple[Execution, Optional[Verdict]]:
    """Classify a test result's outcome from its metrics dict.

    The single implementation of a rule that existed as seven independent,
    disagreeing copies (inventory.md's "duplication and inconsistency" #1).
    Every metric value is expected to carry ``is_successful: bool | None``
    (``None`` meaning the metric itself reported inconclusive -- see
    ``metrics/strategies/local.py``) and, on a crashed or timed-out metric,
    a truthy ``error`` key (``MetricResultBuilder.error()``/``.timeout()``).

    Precedence, most-informative first:

    1. An HTTP-level error means the endpoint never produced evaluable
       output. Metrics are meaningless even if some happen to be present
       (a stale evaluation from a retry, for instance) -- ``ERROR``.
    2. No metrics at all, or nothing metrics-shaped -- nothing was
       evaluated -- ``ERROR``.
    3. Any metric definitively failed -- ``FAIL``. A real failure is never
       masked by another metric that merely errored or was inconclusive;
       it is the strongest signal available and reviewers need to see it.
    4. Any remaining metric *crashed while evaluating* (carries an
       ``error`` key) -- ``ERROR``. Distinct from FAIL: the platform could
       not judge this metric, the system under test did nothing wrong.
    5. Any remaining metric is inconclusive (``is_successful is None``,
       no error) -- ``INCONCLUSIVE``. The metric evaluated and legitimately
       has no pass/fail verdict to give (e.g. a pure score with no
       threshold).
    6. Otherwise every metric passed -- ``PASS``.
    """
    if http_error:
        return Execution.ERROR, None

    valid = {k: v for k, v in (metrics or {}).items() if isinstance(v, dict)}
    if not valid:
        return Execution.ERROR, None

    saw_fail = False
    saw_metric_error = False
    saw_inconclusive = False

    for metric in valid.values():
        if metric.get("error"):
            saw_metric_error = True
            continue
        is_successful = metric.get("is_successful")
        if is_successful is None:
            saw_inconclusive = True
        elif not is_successful:
            saw_fail = True

    if saw_fail:
        return Execution.OK, Verdict.FAIL
    if saw_metric_error:
        return Execution.ERROR, None
    if saw_inconclusive:
        return Execution.OK, Verdict.INCONCLUSIVE
    return Execution.OK, Verdict.PASS


_STATUS_NAME_BY_OUTCOME = {
    Outcome.PASS: "Pass",
    Outcome.FAIL: "Fail",
    Outcome.ERROR: "Error",
    Outcome.INCONCLUSIVE: "Inconclusive",
}


def outcome_to_test_result_status_name(outcome: Outcome) -> str:
    """Bridge to the legacy ``status.name`` shown in review/detail UIs.

    Exists only so writers can keep populating ``status_id`` -- a
    display/review artefact, not the source of truth (see the
    ``TestResult`` model's column comment) -- without each re-inventing
    this mapping. New code that only needs the real value should read
    ``execution``/``verdict`` directly and never call this.

    Only the four outcomes a test result can actually reach at write time
    are mapped; CANCELLED and PENDING have no test-result status name
    because nothing persists a test_result row in those states.
    """
    try:
        return _STATUS_NAME_BY_OUTCOME[outcome]
    except KeyError:
        raise ValueError(f"No test-result status name for outcome {outcome.value!r}") from None


def execution_verdict_from_status_name(
    status_name: Optional[str],
) -> Tuple[Execution, Optional[Verdict]]:
    """Derive (execution, verdict) from a legacy status name directly.

    For the one write path that is allowed to supply ``status_id`` without
    ever going through ``classify_metrics`` -- a caller of
    ``POST /test_results`` may set the status explicitly with no metrics
    attached at all (see ``routers/test_result.py``). Prefer
    ``classify_metrics`` wherever metrics are actually available; this
    exists only to keep the source-of-truth columns populated when they
    aren't.
    """
    from rhesis.backend.app.constants import (
        TEST_RESULT_STATUS_FAILED,
        TEST_RESULT_STATUS_PASSED,
    )

    normalized = (status_name or "").lower()
    if normalized in TEST_RESULT_STATUS_PASSED:
        return Execution.OK, Verdict.PASS
    if normalized in TEST_RESULT_STATUS_FAILED:
        return Execution.OK, Verdict.FAIL
    if normalized == "inconclusive":
        return Execution.OK, Verdict.INCONCLUSIVE
    if normalized == "error":
        return Execution.ERROR, None
    return Execution.NOT_RUN, None
