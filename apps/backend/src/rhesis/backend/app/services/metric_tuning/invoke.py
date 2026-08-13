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

**The judging model is resolved explicitly, and the chain ends in an error.**
It is the metric's own model, else the configured default evaluation model, and
then nothing. The evaluation path this borrows keeps going: past those two it
drops to whatever the caller passed, and past that to the SDK's own built-in
default, the hosted Rhesis LLM. Neither of those last two is announced anywhere.
A tuning run scored by a judge nobody picked measures nothing and says nothing
about it -- set the metric's model afterwards and every stored verdict silently
refers to a different judge. So the run is refused instead, before it starts.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Union

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.schemas.metric_tuning_metadata import MetricTuningCaseResult
from rhesis.backend.app.schemas.metric_types import ScoreType
from rhesis.backend.app.services.metric_tuning.payload import CasePayload
from rhesis.backend.app.services.metric_tuning.verdict import BINARY_VERDICTS

logger = logging.getLogger(__name__)


class MetricModelNotConfigured(Exception):
    """Neither the metric nor the evaluation settings name a model to judge with."""


def _load_model_or_raise(
    db: Session, model_id: str, organization_id: str, label: str, source: str
) -> Any:
    """Turn a Model row into an LLM, or say which configured model failed.

    Reuses the evaluation path's own resolver so a Model row is built in exactly
    one place -- provider, key, endpoint and usage-accrual wiring all stay in
    ``strategies/local.py``. What changes here is the failure semantics: that
    resolver logs and returns ``None``, which is the silent drop this feature
    must not inherit.
    """
    from rhesis.backend.metrics.strategies.local import _resolve_metric_model

    model = _resolve_metric_model(model_id, db, organization_id, label)
    if model is None:
        raise MetricModelNotConfigured(
            f"The {source} could not be loaded. Check that it still exists and has a provider set."
        )
    return model


def _configured_evaluation_model_id(user: Optional[models.User]) -> Optional[Any]:
    """The model explicitly configured as the default for evaluation, if any.

    Reads the same setting as the normal evaluation path but stops there: that
    path continues into the system default when this is unset, which is the step
    a tuning run must not take silently. Every level is optional in the schema,
    hence the walk.
    """
    if user is None:
        return None
    settings = getattr(user, "settings", None)
    models_settings = getattr(settings, "models", None)
    evaluation = getattr(models_settings, "evaluation", None)
    return getattr(evaluation, "model_id", None)


def resolve_metric_model(
    db: Session, metric: models.Metric, organization_id: str, user_id: Optional[str]
) -> Any:
    """The model this metric judges with: its own, else the default for evaluation.

    Two steps, both explicit, and an error rather than a third:

    1. the model saved on the metric, when it has one;
    2. otherwise the model configured as the default for evaluation.

    What it deliberately will not do is reach the *system* default underneath
    those. ``get_user_evaluation_model`` conflates the two -- a user who has
    configured nothing gets the hosted Rhesis model handed back as though it
    were their choice -- so the setting is read directly instead. A tuning run
    scored by a judge nobody picked measures nothing, and worse, says nothing
    about it: change the metric's model afterwards and every stored verdict
    silently refers to a different judge.
    """
    if metric.model_id:
        return _load_model_or_raise(
            db,
            str(metric.model_id),
            organization_id,
            metric.name,
            f"model configured on the metric {metric.name!r}",
        )

    user = crud.get_user(db, user_id=user_id) if user_id else None
    evaluation_model_id = _configured_evaluation_model_id(user)

    if not evaluation_model_id:
        raise MetricModelNotConfigured(
            f"The metric {metric.name!r} has no model, and no default evaluation model is "
            "configured. Set one on the metric, or pick a default evaluation model on the "
            "Models page, before running it over its tuning cases."
        )

    return _load_model_or_raise(
        db,
        str(evaluation_model_id),
        organization_id,
        f"{metric.name} (default evaluation model)",
        "default evaluation model",
    )


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
    model: Any,
) -> MetricTuningCaseResult:
    """Run the metric over one case and return what it said.

    ``model`` is required and comes from ``resolve_metric_model``. Passing it
    explicitly is what stops the evaluator reaching its own default when the
    metric's model cannot be resolved -- there is no model argument to omit.

    Never raises. A failed call comes back as a result carrying ``error``, so
    one bad case does not end the run -- and so a provider failure is never
    mistaken for the metric disagreeing.

    The evaluator retries transient errors itself, so there is no retry here.
    """
    from rhesis.backend.metrics.evaluator import MetricEvaluator

    try:
        evaluator = MetricEvaluator(model=model, db=db, organization_id=organization_id)
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
