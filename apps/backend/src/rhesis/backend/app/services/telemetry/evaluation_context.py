"""What a trace evaluation needs from its project: metrics, judge model, evaluator.

Every evaluation of a project needs the same metrics and judge model, and resolving
them reads several rows and decrypts a key, so both are cached per (organization,
project) for ``TRACE_EVAL_CONTEXT_TTL_SECONDS`` (see ``trace_metrics_config``).
Failures are never cached: the next evaluation resolves again.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.metric import get_metrics_by_ids
from rhesis.backend.app.crud.organization import get_organization
from rhesis.backend.app.crud.project import find_project
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, enforce_quota
from rhesis.backend.app.services.telemetry.trace_metrics_config import context_ttl_seconds
from rhesis.backend.app.utils.ttl_cache import TTLCache
from rhesis.backend.metrics.applicability import metric_target
from rhesis.backend.metrics.metric_config import MetricConfig, validate_metric_configs

logger = logging.getLogger(__name__)

_metric_configs = TTLCache(context_ttl_seconds)
_judge_models = TTLCache(context_ttl_seconds)

# When a production trace is judged. Each metric is judged once, in the phase its target needs.
TURN_PHASE = "turn"  # Each turn of a conversation, as it arrives.
TRACE_PHASE = "trace"  # A trace with no conversation: its one turn is the whole run.
CONVERSATION_PHASE = "conversation"  # A conversation, once it has gone quiet.

_WHOLE_TRACE_TARGETS = frozenset({"conversation", "run"})


def judged_in_phase(target: Optional[str], phase: str) -> bool:
    """Whether a metric with *target* is judged in *phase*.

    ``conversation`` and ``run`` need every turn, so in a conversation they wait for it to
    go quiet. Turn and per-span targets are judged as each turn arrives. A metric whose
    target is unknown is judged on each turn.
    """
    if phase == CONVERSATION_PHASE:
        return target in _WHOLE_TRACE_TARGETS
    if phase == TURN_PHASE:
        return target not in _WHOLE_TRACE_TARGETS
    return target != "conversation"


def load_project_trace_metrics(
    db: Session, organization_id: str, config: Dict[str, Any], phase: str
) -> List[Any]:
    """The metrics a project assigned to its traces (``config["metric_ids"]``) that are
    judged in *phase* (``TURN_PHASE``, ``TRACE_PHASE`` or ``CONVERSATION_PHASE``)."""
    metrics = get_metrics_by_ids(db, organization_id, config.get("metric_ids") or [])
    return [m for m in metrics if judged_in_phase(metric_target(m), phase)]


def project_metric_configs(
    db: Session, organization_id: str, project_id: str, config: Dict[str, Any], phase: str
) -> Tuple[List[MetricConfig], Dict[str, Any]]:
    """The project's metrics judged in *phase*: valid configs, and error results for the rest.

    Plain configs and result dicts, not ORM rows: they are shared across threads and
    sessions, and building a config reads the metric's lazy relationships, which must
    happen inside the read transaction, not during the judge calls. A metric that
    cannot be built gets an error result, as the evaluator gives it, and the others
    still run.
    """

    def load() -> Tuple[List[MetricConfig], Dict[str, Any]]:
        metrics = load_project_trace_metrics(db, organization_id, config, phase=phase)
        return validate_metric_configs(metrics)

    key = (str(organization_id), str(project_id), phase, tuple(config.get("metric_ids") or ()))
    return _metric_configs.get_or_load(key, load)


def project_judge_models(db: Session, organization_id: str, project_id: str, trace_id: str):
    """The project's ``(evaluation model, text model)``, or ``(None, None)`` if unresolvable.

    Resolving them reads the project, its owner, the model row and decrypts the key.

    Raises:
        QuotaExceededError: the organization is at its model token limit.
    """
    from rhesis.backend.app.config.settings import get_model_settings
    from rhesis.backend.app.utils.user_model_utils import (
        resolve_default_hosted_model,
        resolve_model,
        text_model_for,
    )

    # Cached across threads: these are SDK model objects, not ORM rows; nothing in them
    # is bound to a session.
    def load():
        project = find_project(db, project_id)
        project_user = (project.owner or project.user) if project else None
        if project_user:
            default_model = resolve_model(db, project_user, "evaluation")
            return default_model, text_model_for(db, project_user, default_model)
        model = resolve_default_hosted_model(
            get_model_settings().evaluation_model, db, organization_id
        )
        return model, None

    try:
        return _judge_models.get_or_load((str(organization_id), str(project_id)), load)
    except QuotaExceededError:
        raise  # The caller marks the trace skipped.
    except Exception as e:
        # Not cached (the loader raised), so the next trace tries again.
        logger.warning(f"Failed to get default evaluation model for trace {trace_id}: {e}")
        return None, None


def build_evaluator(db: Session, project_id: str, trace_id: str, organization_id: str):
    """The evaluator with the project's evaluation model.

    Built only once there is something to evaluate, so the quota check below runs
    only for a phase that would really call the model. The models are cached, so the
    token-limit check for a hosted model runs here on every trace, not only on a miss.

    Raises:
        QuotaExceededError: the organization is at its model token limit.
    """
    from rhesis.backend.metrics.evaluator import MetricEvaluator

    default_model, text_model = project_judge_models(db, organization_id, project_id, trace_id)
    if getattr(default_model, "usage_metered", None) is True:
        organization = get_organization(db, organization_id)
        enforce_quota(db, str(organization_id), organization, QuotaResource.MODEL_TOKENS)

    # require_model: without a resolved judge the SDK would build its own default
    # model, which carries no usage stamp.
    return MetricEvaluator(
        model=default_model,
        text_model=text_model,
        db=db,
        organization_id=organization_id,
        require_model=True,
    )


def merge_metric_results(
    results: Optional[Dict[str, Any]], invalid: Dict[str, Any]
) -> Dict[str, Any]:
    """The evaluator's results plus the error results of metrics that could not be built."""
    return {**(results or {}), **invalid}
