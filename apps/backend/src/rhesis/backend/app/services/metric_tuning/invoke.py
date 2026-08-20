"""Running a metric over one tuning case.

**This is the part of the feature that is easy to get backwards, and getting it
backwards produces numbers that look fine and mean nothing.**

On the normal evaluation path a prompt's ``expected_response`` is handed to the
metric as its reference answer. A tuning case leaves that column empty -- there is
no expected verdict any more (ADR-0005) -- so the original leak, where the metric
under test was told the verdict it was supposed to return, is gone. The
structural mistake it came from is not: route the metric under test through the
normal evaluation path and it is being read at the wrong level, which is what
produced that leak and will produce the next one.

So a tuning run puts the metric in the system-under-test role: the case payload
is unpacked into the same three arguments the metric receives in a real run --
input, output, and the case's reference answer -- and nothing else. Nothing a
human wrote reaches it, reviews and their comments included: a scorecard has to
reflect the metric's judgement rather than its ability to read a hint.
See domain.local/adr/0002, adr/0004 and adr/0005.

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

from rhesis.backend.app import models
from rhesis.backend.app.crud.user import get_user
from rhesis.backend.app.schemas.metric_tuning_metadata import MetricTuningCaseResult
from rhesis.backend.app.schemas.metric_types import ScoreType
from rhesis.backend.app.services.metric_tuning.payload import CasePayload

logger = logging.getLogger(__name__)

# How a binary metric's verdict is rendered. Lowercase so "Pass" and "pass" are
# never two different verdicts in the same tuning set.
BINARY_VERDICTS = ("pass", "fail")


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
    try:
        return getattr(evaluation, "model_id", None)
    except (ValueError, TypeError) as e:
        # The accessor parses the stored value as a UUID, so a malformed setting
        # raises rather than reading as absent -- and `getattr` only swallows
        # AttributeError. Left alone it escapes as a 500 from a function whose
        # whole purpose is to refuse cleanly.
        raise MetricModelNotConfigured(
            "The default evaluation model setting could not be read. Pick a default evaluation "
            "model on the Models page, or set a model on the metric, before running it over its "
            "tuning cases."
        ) from e


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

    user = get_user(db, user_id=user_id) if user_id else None
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

    One string for all three score types, so a reviewer's judgement can record
    the verdict it was about without branching per metric. A binary metric
    returns a number the SDK treats as a flag, which is rendered pass/fail rather
    than as ``1.0`` -- a reviewer asked to judge ``1.0`` is being asked about the
    wrong thing.
    """
    if score is None:
        return None

    if metric.score_type == ScoreType.BINARY.value:
        if isinstance(score, str):
            lowered = score.strip().lower()
            if lowered in BINARY_VERDICTS:
                return lowered
            # Any other word is the judge's own, not a flag. There is no binary
            # judge in the SDK -- a binary metric is backed by one that answers
            # in categories -- so this really happens, and `bool()` on a string
            # is true whatever it says: "no" would render as "pass". Shown as
            # the metric said it instead of guessed at.
            return score.strip()
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


# How the SDK opens the reason on a result it is using to report its own failure.
_SDK_FAILURE_REASON = "Error evaluating with "


def _declares_error_category(metric: models.Metric) -> bool:
    """Whether ``error`` is one of this metric's own categories rather than a sentinel."""
    categories = metric.categories or []
    if not isinstance(categories, list):
        return False
    return any(isinstance(c, str) and c.strip().lower() == "error" for c in categories)


def _failure_from_result(metric: models.Metric, result: dict) -> Optional[str]:
    """The failure this result is reporting, if it is reporting one.

    Two shapes reach here and only one of them says ``error``. The error builder
    sets it outright. The local strategy never does: it wraps whatever the SDK
    handed back in ``MetricResultBuilder.success()``, and the SDK answers its own
    failures with a result rather than an exception -- the score is a sentinel
    (``"error"`` for a categorical metric, ``0.0`` for the rest) and the cause is
    left in a reason it formats itself. ``success()`` carries neither the SDK's
    ``details["error"]`` nor an ``error`` key, so the reason is all that survives.

    Reading that second shape as a verdict fails quietly, which is the danger. A
    categorical metric stores ``error`` as the verdict; a binary one stores
    ``pass``, since any non-empty score string is truthy. The run then reports
    zero errored cases and the scorecard counts a provider outage as the metric
    agreeing. A 401 against the hosted model is exactly this.
    """
    error = result.get("error")
    if error:
        return str(error)

    reason = result.get("reason")
    score = result.get("score")

    # Only a sentinel when the metric does not offer "error" as a real answer.
    if (
        isinstance(score, str)
        and score.strip().lower() == "error"
        and not _declares_error_category(metric)
    ):
        return str(reason or "The metric failed to evaluate this case.")

    # All that is left for the score types whose sentinel is an ordinary number.
    if isinstance(reason, str) and reason.startswith(_SDK_FAILURE_REASON):
        return reason

    return None


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
            # The case's own reference answer -- what the *system under test*
            # should have answered. Never prompt.expected_response, which this
            # feature does not write at all. See the module docstring.
            expected_output=payload.reference_answer or "",
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

    failure = _failure_from_result(metric, result)
    if failure:
        return _error_result(failure)

    return MetricTuningCaseResult(
        verdict=verdict_from_score(metric, result.get("score")),
        reasoning=result.get("reason"),
        evaluated_at=_now(),
    )
