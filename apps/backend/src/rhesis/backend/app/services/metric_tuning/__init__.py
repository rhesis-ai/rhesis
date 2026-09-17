"""Metric tuning: a per-metric set of cases, runs over them, and annotations of
what the metric said.

Each case is an (input, output) pair -- plus a reference answer where the metric
needs one -- recording a situation the metric has to get right. It carries no
expected verdict: the judgement happens after a run, when a reviewer accepts what
the metric said or rejects it with a comment (domain.local/adr/0005).

The set lives in the normal ``test`` / ``test_set`` tables, owned by the metric
through ``metric_id`` and hidden from the user-facing lists the way Explorer
hides its own rows.

Package façade -- callers import from here, not from the submodules.
"""

from rhesis.backend.app.services.metric_tuning.agreement import (
    agreement_over,
    get_agreement,
)
from rhesis.backend.app.services.metric_tuning.annotations import (
    AnnotationCommentRequired,
    NothingToAnnotate,
    accept_remaining,
    annotate_case,
)
from rhesis.backend.app.services.metric_tuning.cases import (
    create_tuning_case,
    delete_tuning_case,
    get_tuning_case,
    list_tuning_cases,
    to_api,
    update_tuning_case,
)
from rhesis.backend.app.services.metric_tuning.fingerprint import (
    metric_fingerprint,
    run_predates_metric,
)
from rhesis.backend.app.services.metric_tuning.improve import (
    ImprovementUnavailable,
    NoStandingRejections,
    improve_from_annotations,
    standing_rejections,
)
from rhesis.backend.app.services.metric_tuning.invoke import (
    MetricModelNotConfigured,
    invoke_metric_on_case,
    resolve_metric_model,
    verdict_from_score,
)
from rhesis.backend.app.services.metric_tuning.material_change import annotation_still_stands
from rhesis.backend.app.services.metric_tuning.outcome import case_outcome, standing_annotation
from rhesis.backend.app.services.metric_tuning.runs import (
    NoTuningCases,
    TuningRunInFlight,
    execute_tuning_run,
    fail_tuning_run,
    get_tuning_run,
    start_tuning_run,
)
from rhesis.backend.app.services.metric_tuning.staleness import (
    STALE_RUN_AFTER,
    STALE_RUN_MESSAGE,
    run_is_stale,
)
from rhesis.backend.app.services.metric_tuning.test_sets import (
    get_or_create_tuning_test_set,
    get_tuning_test_set,
)

__all__ = [
    "STALE_RUN_AFTER",
    "STALE_RUN_MESSAGE",
    "AnnotationCommentRequired",
    "ImprovementUnavailable",
    "MetricModelNotConfigured",
    "NoStandingRejections",
    "NoTuningCases",
    "NothingToAnnotate",
    "TuningRunInFlight",
    "accept_remaining",
    "agreement_over",
    "annotate_case",
    "annotation_still_stands",
    "case_outcome",
    "create_tuning_case",
    "delete_tuning_case",
    "execute_tuning_run",
    "fail_tuning_run",
    "get_agreement",
    "get_or_create_tuning_test_set",
    "get_tuning_case",
    "get_tuning_run",
    "get_tuning_test_set",
    "improve_from_annotations",
    "invoke_metric_on_case",
    "list_tuning_cases",
    "metric_fingerprint",
    "resolve_metric_model",
    "run_is_stale",
    "run_predates_metric",
    "standing_annotation",
    "standing_rejections",
    "start_tuning_run",
    "to_api",
    "update_tuning_case",
    "verdict_from_score",
]
