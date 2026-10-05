"""Which models a test run needs, and building only those.

One rule, shared by the execute and re-score routes (to refuse a run before it is
queued) and by the batch and sequential workers (to build the models).
"""

import logging
from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.crud.user import get_user_by_id
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.models.type_lookup import TypeLookup
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota.enforcement import QuotaExceededError
from rhesis.backend.app.services.run_config import record_resolved_evaluation_model

# Called through the module so tests that patch these at their source still apply.
from rhesis.backend.app.utils import user_model_utils

logger = logging.getLogger(__name__)

#: Metrics with this backend run in the user's SDK process through the connector.
SDK_BACKEND = "sdk"

#: Backend of a metric row that has none set. Same default as ``metric_model_to_config``.
DEFAULT_METRIC_BACKEND = "rhesis"


@dataclass(frozen=True)
class RunModelNeeds:
    """Which of the two run models a run uses."""

    evaluation: bool = True
    execution: bool = True


@dataclass(frozen=True)
class RunModels:
    """The models built for a run. ``None`` for one the run does not use."""

    evaluation: Any = None
    execution: Any = None


def metric_backends(db: Session, metrics: Iterable[Any]) -> List[str]:
    """Distinct backend names of ``Metric`` rows, read in one query.

    Read by id because callers do not eager-load ``Metric.backend_type``.
    """
    type_ids = {getattr(metric, "backend_type_id", None) for metric in metrics}
    backends = {DEFAULT_METRIC_BACKEND} if None in type_ids else set()
    type_ids.discard(None)
    if type_ids:
        rows = db.query(TypeLookup.type_value).filter(TypeLookup.id.in_(list(type_ids))).all()
        backends.update(value for (value,) in rows)
        # A backend that could not be read is not known to be an SDK one.
        if len(rows) < len(type_ids):
            backends.add(DEFAULT_METRIC_BACKEND)
    return sorted(backends)


def model_needs(
    backends: Iterable[Optional[str]], has_multi_turn: bool, replay: bool = False
) -> RunModelNeeds:
    """The rule. Any non-SDK metric and any multi-turn test (goal interpretation and
    scoring) need the evaluation model. The execution model drives Penelope, so only
    multi-turn tests that run live need it, never a *replay* of stored outputs."""
    judged = any(backend != SDK_BACKEND for backend in backends)
    return RunModelNeeds(
        evaluation=judged or has_multi_turn,
        execution=has_multi_turn and not replay,
    )


def model_needs_from_plan(
    metric_plan: Optional[Mapping[str, Any]], replay: bool = False
) -> RunModelNeeds:
    """Model needs of a run, read from its metric plan (``jobs/execution/metric_plan.py``)."""
    # No plan, or one saved before it recorded these: build both, as every run used to.
    if not metric_plan or "metric_backends" not in metric_plan:
        return RunModelNeeds(evaluation=True, execution=not replay)
    return model_needs(
        metric_plan["metric_backends"], bool(metric_plan.get("has_multi_turn")), replay
    )


def is_replay(test_config: TestConfiguration) -> bool:
    """True when the run scores a previous run's stored outputs instead of running live."""
    return bool((test_config.attributes or {}).get("reference_test_run_id"))


def build_models(
    db: Session,
    principal: user_model_utils.Principal,
    needs: RunModelNeeds,
    *,
    evaluation_model_id: Optional[str] = None,
    execution_model_id: Optional[str] = None,
) -> RunModels:
    """Build the models *needs* names.

    Raises ``ModelNotConfiguredError`` for the first one that cannot be built.
    ``QuotaExceededError`` passes through untouched, so it keeps its own 402.
    """
    built = {}
    wanted = (
        ("evaluation", needs.evaluation, evaluation_model_id),
        ("execution", needs.execution, execution_model_id),
    )
    for purpose, needed, override in wanted:
        if not needed:
            continue
        built[purpose] = user_model_utils.build_model_or_raise(db, principal, purpose, override)
    return RunModels(**built)


def check_run_models(
    db: Session,
    user: User,
    test_config: TestConfiguration,
    metric_plan: Optional[Mapping[str, Any]],
) -> None:
    """Refuse a run before it is queued when a model it needs cannot be built."""
    attrs = test_config.attributes or {}
    build_models(
        db,
        user,
        model_needs_from_plan(metric_plan, replay=is_replay(test_config)),
        evaluation_model_id=attrs.get("evaluation_model_id"),
        execution_model_id=attrs.get("execution_model_id"),
    )


def _run_user(session: Session, user_id: Optional[str]) -> Optional[User]:
    """The user a run resolves models for, or ``None`` to use the deployment defaults."""
    if not user_id:
        return None
    try:
        user = get_user_by_id(session, user_id)
    except Exception as error:
        logger.warning(f"Failed to load user {user_id}, using default models: {error}")
        return None
    if user is None:
        logger.warning(f"User {user_id} not found, using default models")
    return user


def _build_for_worker(
    session: Session,
    user: Optional[User],
    purpose: user_model_utils.ModelPurpose,
    override: Optional[str],
    organization_id: Optional[str],
) -> Any:
    """Build one run model. A worker has nobody to show a configuration error to,
    so the org's own broken model falls back to the deployment default."""
    if user is not None:
        try:
            return user_model_utils.resolve_model(session, user, purpose, override=override)
        except QuotaExceededError:
            # Not a resolution failure. The default would hit the same quota.
            raise
        except Exception as error:
            logger.warning(f"Failed to resolve {purpose} model, using the default: {error}")
    # Resolved here, not passed on as a string, so the model carries its usage stamp.
    default_model = getattr(get_model_settings(), f"{purpose}_model")
    return user_model_utils.resolve_default_hosted_model(default_model, session, organization_id)


def resolve_run_models(
    session: Session,
    test_config: TestConfiguration,
    test_run: TestRun,
    replay: bool = False,
    live_backends: Iterable[Optional[str]] = (),
    live_multi_turn: bool = False,
) -> RunModels:
    """Build the models a worker needs for this run, and only those.

    The plan is frozen at dispatch, so the worker also passes what it sees now
    (*live_backends*, *live_multi_turn*). A metric or test edited since can add a need.
    """
    attrs = test_config.attributes or {}
    is_replayed = replay or is_replay(test_config)
    planned = model_needs_from_plan((test_run.attributes or {}).get("metric_plan"), is_replayed)
    live = model_needs(live_backends, live_multi_turn, is_replayed)
    needs = RunModelNeeds(
        planned.evaluation or live.evaluation, planned.execution or live.execution
    )
    organization_id = str(test_config.organization_id) if test_config.organization_id else None
    user_id = str(test_config.user_id) if test_config.user_id else None
    user = _run_user(session, user_id) if (needs.evaluation or needs.execution) else None

    evaluation = execution = None
    if needs.execution:
        execution = _build_for_worker(
            session, user, "execution", attrs.get("execution_model_id"), organization_id
        )
    if needs.evaluation:
        evaluation = _build_for_worker(
            session, user, "evaluation", attrs.get("evaluation_model_id"), organization_id
        )
    logger.info(
        f"Run {test_run.id} builds evaluation model={needs.evaluation}, "
        f"execution model={needs.execution}"
    )

    # Names the model on the run's Configuration tab. A no-op when none was built.
    record_resolved_evaluation_model(
        session, test_run=test_run, model_name=getattr(evaluation, "model_name", None)
    )
    return RunModels(evaluation=evaluation, execution=execution)
