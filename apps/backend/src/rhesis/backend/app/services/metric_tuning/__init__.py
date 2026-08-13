"""Metric tuning: a per-metric set of labelled cases.

Each case is an (input, recorded output) pair plus the verdict a human expects
from the metric and why. The set lives in the normal ``test`` / ``test_set``
tables, owned by the metric through ``metric_id`` and hidden from the user-facing
lists the way Explorer hides its own rows.

Package façade -- callers import from here, not from the submodules.
"""

from rhesis.backend.app.services.metric_tuning.cases import (
    create_tuning_case,
    delete_tuning_case,
    get_tuning_case,
    list_tuning_cases,
    to_api,
    update_tuning_case,
)
from rhesis.backend.app.services.metric_tuning.invoke import (
    MetricModelNotConfigured,
    invoke_metric_on_case,
    resolve_metric_model,
    verdict_from_score,
)
from rhesis.backend.app.services.metric_tuning.runs import (
    NoTuningCases,
    TuningRunInFlight,
    execute_tuning_run,
    fail_tuning_run,
    get_tuning_run,
    start_tuning_run,
)
from rhesis.backend.app.services.metric_tuning.test_sets import (
    get_or_create_tuning_test_set,
    get_tuning_test_set,
)
from rhesis.backend.app.services.metric_tuning.verdict import (
    BINARY_VERDICTS,
    InvalidVerdict,
    is_stale,
    normalize_verdict,
)

__all__ = [
    "BINARY_VERDICTS",
    "InvalidVerdict",
    "MetricModelNotConfigured",
    "NoTuningCases",
    "TuningRunInFlight",
    "create_tuning_case",
    "delete_tuning_case",
    "execute_tuning_run",
    "fail_tuning_run",
    "get_or_create_tuning_test_set",
    "get_tuning_case",
    "get_tuning_run",
    "get_tuning_test_set",
    "invoke_metric_on_case",
    "is_stale",
    "list_tuning_cases",
    "normalize_verdict",
    "resolve_metric_model",
    "start_tuning_run",
    "to_api",
    "update_tuning_case",
    "verdict_from_score",
]
