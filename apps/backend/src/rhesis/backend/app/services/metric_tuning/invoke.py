"""Running a metric over one tuning case.

**This is the part of the feature that is easy to get backwards, and getting it
backwards produces numbers that look fine and mean nothing.**

On the normal evaluation path a prompt's ``expected_response`` is handed to the
metric as its ``expected_output`` -- the reference answer. On a tuning case that
column holds the *expected verdict*: what the metric should have said. Pass it
through and the metric under test is shown the answer key, told the expected
response to "How are you?" is ``fail``, and every scorecard comes out flattering.
Nothing raises when this is wrong.

So a tuning run puts the metric in the system-under-test role: the case payload
is unpacked into the same three arguments the metric receives in a real run --
input, output, and the case's *own* expected output -- and nothing else. The
expected verdict is read afterwards, by the comparison, and never enters here.
See domain.local/adr/0002 and adr/0004.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Union

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric_tuning_metadata import MetricTuningCaseResult
from rhesis.backend.app.schemas.metric_types import ScoreType
from rhesis.backend.app.services.metric_tuning.payload import CasePayload
from rhesis.backend.app.services.metric_tuning.verdict import BINARY_VERDICTS

logger = logging.getLogger(__name__)


def verdict_from_score(metric: models.Metric, score: Union[float, str, None]) -> Optional[str]:
    """Render a metric's own score as a verdict string.

    The stored expected verdict is one string for all three score types, so the
    metric's answer has to be rendered the same way to sit beside it. A binary
    metric returns a number the SDK treats as a flag, which is displayed as
    pass/fail rather than as ``1.0`` -- a case labelled ``pass`` compared against
    ``1.0`` reads as a disagreement to a human even when it is not.
    """
    if score is None:
        return None

    if metric.score_type == ScoreType.BINARY.value:
        if isinstance(score, str):
            lowered = score.strip().lower()
            if lowered in BINARY_VERDICTS:
                return lowered
        passing, failing = BINARY_VERDICTS
        return passing if bool(score) else failing

    if metric.score_type == ScoreType.NUMERIC.value:
        try:
            return str(float(score))
        except (TypeError, ValueError):
            return str(score)

    return str(score)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_result(message: str) -> MetricTuningCaseResult:
    return MetricTuningCaseResult(error=message, evaluated_at=_now())


def invoke_metric_on_case(
    db: Session,
    metric: models.Metric,
    payload: CasePayload,
    organization_id: str,
) -> MetricTuningCaseResult:
    """Run the metric over one case and return what it said.

    Never raises. A failed call comes back as a result carrying ``error``, so
    one bad case does not end the run -- and so a provider failure is never
    mistaken for the metric disagreeing.

    The evaluator retries transient errors itself, so there is no retry here.
    """
    from rhesis.backend.metrics.evaluator import MetricEvaluator

    try:
        evaluator = MetricEvaluator(db=db, organization_id=organization_id)
        results = evaluator.evaluate(
            input_text=payload.input,
            output_text=payload.output,
            # The case's own expected output -- what the *system under test*
            # should have answered. Never prompt.expected_response, which is the
            # expected verdict. See the module docstring.
            expected_output=payload.expected_output or "",
            context=[],
            metrics=[metric],
        )
    except Exception as e:  # noqa: BLE001 -- one case failing must not end the run
        logger.error("Tuning run: metric %s raised on a case: %s", metric.id, e, exc_info=True)
        return _error_result(str(e))

    if not results:
        return _error_result("The metric returned no result.")

    # One metric in, so one result out -- whatever key the evaluator chose for it.
    result: Any = next(iter(results.values()))
    if not isinstance(result, dict):
        return _error_result("The metric returned a result in an unrecognized shape.")

    error = result.get("error")
    if error:
        return _error_result(str(error))

    return MetricTuningCaseResult(
        verdict=verdict_from_score(metric, result.get("score")),
        reasoning=result.get("reason"),
        evaluated_at=_now(),
    )
