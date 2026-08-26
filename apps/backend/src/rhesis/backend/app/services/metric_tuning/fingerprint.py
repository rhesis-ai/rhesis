"""Whether a run's numbers still belong to the metric on screen.

Applying an improvement rewrites the evaluation prompt every verdict in the run
came from. The reviews stay -- they are human words, and the per-case
material-change rule re-checks each one on the next run -- but the agreement
number stops describing the metric it sits under, so the run has to be able to
say it predates it (domain.local/adr/0006).

The check is a fingerprint of the fields that decide a verdict, captured at run
start, rather than the metric's ``updated_at``. Both halves matter: renaming a
metric must not stale a run, and editing the evaluation prompt by hand in the
metric editor must.

Nothing is written on read. A missing fingerprint is unknown, not stale -- runs
stored before this existed must not all report themselves out of date.
"""

import hashlib
import json
import logging
from typing import Any, List, Optional

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric_tuning_metadata import MetricTuningRunSummary

logger = logging.getLogger(__name__)

# The fields a verdict actually comes out of: what the judge is told, and where
# the resulting score turns into a decision. Everything else on a metric -- its
# name, description, reasoning, explanation -- can be rewritten without any
# verdict moving, so none of it belongs here.
FINGERPRINTED_FIELDS = (
    "evaluation_prompt",
    "evaluation_steps",
    "threshold",
    "threshold_operator",
    "passing_categories",
)


def metric_fingerprint(metric: models.Metric) -> str:
    """A digest of the metric fields that decide what a verdict is.

    Stable across restarts and processes, so a run claimed by one worker is
    comparable in the request that reads it back.
    """
    material = {field: _normalize(getattr(metric, field, None)) for field in FINGERPRINTED_FIELDS}
    encoded = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def run_predates_metric(summary: MetricTuningRunSummary, metric: models.Metric) -> bool:
    """True when this run scored a metric that has since changed.

    A run with no fingerprint answers False: it cannot be shown to be out of
    date, and presenting every pre-existing run as stale would be a worse lie
    than presenting an unknown one as current.
    """
    stored = (summary.metric_fingerprint or "").strip()
    if not stored:
        return False
    return stored != metric_fingerprint(metric)


def _normalize(value: Any) -> Any:
    """The comparable form of one fingerprinted field.

    Only differences that can move a verdict survive this. ``None`` and blank
    are the same absence; ``0.5`` and ``0.50`` are the same threshold; and the
    passing categories are compared the way ``material_change`` compares them --
    as a case-insensitive set -- so reordering or recasing them changes no
    decision and stales no run.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return _normalize_categories(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    text = str(getattr(value, "value", value)).strip()
    return text or None


def _normalize_categories(value: List[Any]) -> Optional[List[str]]:
    categories = sorted({str(item).strip().lower() for item in value if str(item).strip()})
    return categories or None
