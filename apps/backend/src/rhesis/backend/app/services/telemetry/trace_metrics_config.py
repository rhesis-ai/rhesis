"""A project's trace-metrics setting, and whether its traces need evaluating.

Read on every stored trace (ingest decides whether to queue an evaluation) and on
every evaluation, so it is cached per (organization, project) for
``TRACE_EVAL_CONTEXT_TTL_SECONDS`` (default 60). A change to a project's trace
metrics therefore reaches new traces within that time.
"""

import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.project import find_project
from rhesis.backend.app.utils.ttl_cache import TTLCache


def context_ttl_seconds() -> float:
    return float(os.environ.get("TRACE_EVAL_CONTEXT_TTL_SECONDS", "60"))


_configs = TTLCache(context_ttl_seconds)


def trace_metrics_config(project: models.Project) -> Dict[str, Any]:
    """Extract trace_metrics config from project attributes.

    The frontend stores ``trace_metrics`` as a plain list of metric-ID
    strings while the evaluation pipeline expects a config dict with
    optional keys ``enabled``, ``sampling_rate``, and ``metric_ids``.
    This function normalises both representations into a config dict.

    Returns defaults when attributes are absent or incomplete.
    """
    attrs = project.attributes or {}
    raw = attrs.get("trace_metrics", {})
    if isinstance(raw, list):
        return {"metric_ids": raw}
    if not isinstance(raw, dict):
        return {}
    return raw


def evaluation_enabled(config: Optional[Dict[str, Any]]) -> bool:
    """The project assigned trace metrics and did not turn evaluation off."""
    return bool(config and config.get("metric_ids") and config.get("enabled") is not False)


def project_trace_metrics_config(
    db: Session, organization_id: str, project_id: str
) -> Optional[Dict[str, Any]]:
    """The project's trace-metrics config, or ``None`` when the project is not found.

    *db* must be bound to the organization (RLS), as every task session is.
    """

    def load() -> Optional[Dict[str, Any]]:
        project = find_project(db, project_id)
        return None if project is None else dict(trace_metrics_config(project))

    return _configs.get_or_load((str(organization_id), str(project_id)), load)
