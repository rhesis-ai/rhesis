"""
Batch execution context: shared data pre-fetched before async execution.

This module owns the ExecutionContext dataclass and the prefetch function
that populates it from a live DB session.  After prefetch, all SQLAlchemy
models are expunged so they can be used safely across threads/coroutines.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.quota.enforcement import QuotaExceededError
from rhesis.backend.metrics.metric_config import metric_model_to_config
from rhesis.sdk.metrics import MetricConfig

logger = logging.getLogger(__name__)

DEFAULT_BATCH_CONCURRENCY = 10
DEFAULT_PER_TEST_TIMEOUT = 1800  # 30 min — accommodates multi-turn tests with slow endpoints
DEFAULT_INVOKE_MAX_ATTEMPTS = 4
DEFAULT_INVOKE_RETRY_MIN_WAIT = 1.0
DEFAULT_INVOKE_RETRY_MAX_WAIT = 30.0
# Number of recovery passes after the main batch.  Each pass retries tests whose
# failure looks transient (not timeouts, not missing data, not cancellations).
DEFAULT_RECOVERY_ROUNDS = 1


@dataclass
class ExecutionContext:
    """Pre-fetched shared data for all tests in a batch."""

    test_config: TestConfiguration
    test_run: TestRun
    test_set: TestSet
    endpoint: Endpoint
    organization_id: str
    user_id: Optional[str]
    project_id: Optional[str] = None
    execution_model: Any = None
    evaluation_model: Any = None
    # SDK MetricConfig objects built while the DB session is open (ORM-safe after close).
    # Shared list used when all tests share the same metrics (Priority 1/2).
    metric_configs: List[MetricConfig] = field(default_factory=list)
    # Per-test metric configs for requirement-mapped metrics (Priority 3) where each
    # test may have a different requirement with different metrics.
    per_test_metric_configs: Dict[str, List[MetricConfig]] = field(default_factory=dict)
    # Judge models for metrics that configure their own `model_id`, resolved while the
    # session is open because metric evaluation runs after it closes. A `None` value
    # records a resolution that was attempted and failed, which is distinct from a
    # `model_id` being absent here entirely; see `prepare_metrics`.
    metric_models: Dict[str, Any] = field(default_factory=dict)
    test_data: Dict[str, Any] = field(default_factory=dict)
    input_files: Dict[str, List] = field(default_factory=dict)
    existing_result_ids: Set[str] = field(default_factory=set)
    batch_concurrency: int = DEFAULT_BATCH_CONCURRENCY
    per_test_timeout: int = DEFAULT_PER_TEST_TIMEOUT
    connector_metric_sender: Any = None
    reference_test_run_id: Optional[str] = None
    trace_id: Optional[str] = None
    invoke_max_attempts: int = DEFAULT_INVOKE_MAX_ATTEMPTS
    invoke_retry_min_wait: float = DEFAULT_INVOKE_RETRY_MIN_WAIT
    invoke_retry_max_wait: float = DEFAULT_INVOKE_RETRY_MAX_WAIT
    # Celery task ID for cooperative cancellation checks inside the async loop.
    celery_task_id: Optional[str] = None
    # How many recovery passes to run after the main batch (0 = no retries).
    recovery_rounds: int = DEFAULT_RECOVERY_ROUNDS
    # Snapshot of test_data taken before the main pass, used to persist error
    # records after the batch for tests that failed without a DB row.
    test_data_snapshot: Dict[str, Any] = field(default_factory=dict)

    def get_metric_configs_for_test(self, test_id: str) -> List[MetricConfig]:
        """Return metric configs for a specific test.

        Uses per-test configs when available (requirement-mapped metrics),
        otherwise falls back to the shared list (test_set / execution-time).
        """
        if self.per_test_metric_configs:
            return self.per_test_metric_configs.get(test_id, [])
        return self.metric_configs

    @property
    def has_metrics(self) -> bool:
        """True if any test has metric configs to evaluate."""
        return bool(self.metric_configs) or bool(self.per_test_metric_configs)


def _resolve_metric_judge_models(
    session: Session,
    organization_id: Optional[str],
    metric_configs: List[MetricConfig],
    per_test_metric_configs: Dict[str, List[MetricConfig]],
) -> Dict[str, Any]:
    """Resolve every distinct per-metric judge `model_id` in the batch, once each.

    Deduped by `model_id` so a model shared by many metrics (or by many tests
    sharing a requirement) costs one lookup rather than one per metric. Failures are
    recorded as a `None` value rather than omitted, so the evaluator can tell
    "tried and failed" from "never attempted" and warn accordingly.
    """
    from rhesis.backend.metrics.strategies.local import _resolve_metric_model

    all_configs = list(metric_configs)
    for configs in per_test_metric_configs.values():
        all_configs.extend(configs)

    resolved: Dict[str, Any] = {}
    for config in all_configs:
        model_id = (config.parameters or {}).get("model_id")
        if not model_id or model_id in resolved:
            continue
        resolved[model_id] = _resolve_metric_model(
            model_id, session, organization_id, config.name or config.class_name
        )

    if resolved:
        failed = [mid for mid, model in resolved.items() if model is None]
        logger.info(
            f"Pre-resolved {len(resolved) - len(failed)}/{len(resolved)} per-metric judge models"
        )
    return resolved


def prefetch_execution_context(
    session: Session,
    test_config: TestConfiguration,
    test_run: TestRun,
    tests: List[Test],
    reference_test_run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> ExecutionContext:
    """Pre-fetch all shared data in a single session before async execution."""
    from rhesis.backend.app.crud import endpoint as endpoint_crud
    from rhesis.backend.app.crud import user as user_crud
    from rhesis.backend.app.database import bind_scope_to_session
    from rhesis.backend.app.models.requirement import Requirement
    from rhesis.backend.app.services.test_set import get_test_set
    from rhesis.backend.app.utils.query_utils import QueryBuilder, include
    from rhesis.backend.jobs.execution.executors.data import get_test_metrics

    organization_id = str(test_config.organization_id) if test_config.organization_id else ""
    user_id = str(test_config.user_id) if test_config.user_id else None
    # Carry the project so project filtering / stamping applies. Without it this
    # would wipe the project GUC set by BaseJob.get_db_session() and the batch
    # would lose access to its project-scoped rows under fail-closed RLS.
    project_id = str(test_config.project_id) if test_config.project_id else ""

    bind_scope_to_session(session, organization_id, user_id or "", project_id)

    # get_test_set/get_endpoint raise ItemDeletedException for a soft-deleted
    # row; it's in BaseTask.dont_autoretry_for, so this fails the task
    # immediately instead of retrying against a row that will never come back.
    test_set = get_test_set(session, str(test_config.test_set_id), organization_id)

    endpoint = endpoint_crud.get_endpoint(
        session,
        test_config.endpoint_id,
        organization_id,
        user_id,
        project_id=project_id or None,
    )
    if not endpoint:
        raise ValueError(f"Endpoint {test_config.endpoint_id} not found")

    # Prime auth token
    from rhesis.backend.app.services.invokers.auth.manager import AuthenticationManager

    auth_manager = AuthenticationManager()
    try:
        auth_manager.get_valid_token(session, endpoint)
    except Exception as e:
        logger.warning(f"Failed to prime auth token: {e}")

    # Resolve execution model (for Penelope) and evaluation model (for metrics).
    # Per-run overrides stored in test_config.attributes take precedence over
    # the user's defaults, which in turn fall back to env-level defaults.
    attrs = test_config.attributes or {}
    execution_model = None
    evaluation_model = None
    try:
        from rhesis.backend.app.config.settings import get_model_settings
        from rhesis.backend.app.utils.user_model_utils import (
            get_evaluation_model_with_override,
            get_execution_model_with_override,
            resolve_default_hosted_model,
        )

        model_settings = get_model_settings()
        override_execution_model_id = attrs.get("execution_model_id")
        override_evaluation_model_id = attrs.get("evaluation_model_id")

        if user_id:
            user = user_crud.get_user_by_id(session, user_id)
            if user:
                execution_model = get_execution_model_with_override(
                    session, user, model_id=override_execution_model_id
                )
                evaluation_model = get_evaluation_model_with_override(
                    session, user, model_id=override_evaluation_model_id
                )
            else:
                # Resolve rather than passing the bare default string on:
                # the string is only turned into a model much later, inside
                # Penelope / the metric judge, and a model built there carries
                # no provenance stamp. See resolve_default_hosted_model.
                logger.warning(f"User {user_id} not found, using default models")
                execution_model = resolve_default_hosted_model(
                    model_settings.execution_model, session, organization_id
                )
                evaluation_model = resolve_default_hosted_model(
                    model_settings.evaluation_model, session, organization_id
                )
        else:
            execution_model = resolve_default_hosted_model(
                model_settings.execution_model, session, organization_id
            )
            evaluation_model = resolve_default_hosted_model(
                model_settings.evaluation_model, session, organization_id
            )
    except QuotaExceededError:
        # Not a resolution failure -- let it propagate as-is. The broad
        # except below would otherwise retry the identical call against the
        # same org and quota state, misreport it as "failed to resolve" in
        # the log, and only raise the same error a second time anyway.
        raise
    except Exception as e:
        from rhesis.backend.app.config.settings import get_model_settings
        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        logger.warning(f"Failed to resolve execution/evaluation models: {e}")
        model_settings = get_model_settings()
        if execution_model is None:
            execution_model = resolve_default_hosted_model(
                model_settings.execution_model, session, organization_id
            )
        if evaluation_model is None:
            evaluation_model = resolve_default_hosted_model(
                model_settings.evaluation_model, session, organization_id
            )

    # Warm the session identity map with prompt/requirement/requirement.metrics eager-loaded
    # for every test in the batch, in one query. get_test_and_prompt/get_test_metrics
    # below re-fetch each test by id from this same session -- SQLAlchemy's identity
    # map returns the very same instance per row, so once these relationships are
    # already populated here, those per-test lookups find them already loaded instead
    # of issuing one extra lazy-load query per test per relationship (N+1).
    test_ids = [test.id for test in tests]
    if test_ids:
        QueryBuilder(session, Test).with_custom_filter(
            lambda q: q.filter(Test.id.in_(test_ids))
        ).with_related(
            include(Test.prompt),
            include(Test.requirement, Requirement.metrics),
            # test_type decides which executor each test gets. Eager-load it so it
            # is already populated when the Test objects are expunged below.
            include(Test.test_type),
        ).all()

    # Pre-fetch per-test data
    test_data: Dict[str, Any] = {}
    for test in tests:
        try:
            from rhesis.backend.jobs.execution.executors.data import get_test_and_prompt

            test_obj, prompt_content, expected_response = get_test_and_prompt(
                session, str(test.id), organization_id
            )
            test_data[str(test.id)] = {
                "test": test_obj,
                "prompt_content": prompt_content,
                "expected_response": expected_response,
            }
        except Exception as e:
            logger.error(f"Failed to pre-fetch test {test.id}: {e}")

    # Input files are loaded lazily inside the semaphore (per-test) to avoid
    # holding all base64-encoded attachments in memory for the entire batch.

    # Pre-fetch metrics: convert ORM -> MetricConfig before session closes.  Async
    # evaluation runs after session.close(); detached Metric rows would raise on
    # lazy loads (e.g. backend_type) in metric_model_to_config.
    #
    # Metric resolution follows a 3-level priority (see executors/data.py):
    #   P1 execution-time, P2 test-set, P3 requirement.
    # P1 and P2 come from shared config (test_configuration.attributes / test_set.metrics)
    # and resolve identically for every test, so a single resolution is correct — but
    # only when one of them actually wins. get_test_metrics() can fall through past a
    # *configured* P1/P2 to P3 if it resolves to zero valid metrics (missing/invalid IDs,
    # or every candidate filtered out for lacking a class_name), and that fallback can
    # differ per test. So resolve the sample test first and branch on the priority that
    # actually won, not on whether P1/P2 config is merely present.
    metric_configs: List[MetricConfig] = []
    per_test_metric_configs: Dict[str, List[MetricConfig]] = {}

    try:
        from rhesis.backend.jobs.execution.executors.metrics import (
            prepare_metric_configs,
        )

        def _convert_metrics(metric_models, label):
            configs = []
            for m in metric_models:
                try:
                    configs.append(metric_model_to_config(m))
                except Exception as conv_err:
                    logger.warning(
                        f"Failed to convert metric {getattr(m, 'id', '?')} "
                        f"to MetricConfig for {label}: {conv_err}"
                    )
            return configs

        sample_test = tests[0] if tests else None
        if sample_test:
            sample_metrics, sample_source = get_test_metrics(
                sample_test,
                session,
                organization_id,
                user_id,
                test_set=test_set,
                test_configuration=test_config,
                return_source=True,
            )
        else:
            sample_metrics, sample_source = [], "none"

        if sample_source in ("execution_time", "test_set"):
            # P1 / P2 actually won: shared config, safe to reuse for every test.
            models = prepare_metric_configs(sample_metrics, str(sample_test.id))
            metric_configs = _convert_metrics(models, f"test {sample_test.id}")
        else:
            # P3 (or no metrics at all) — resolution can differ per test since each
            # test may belong to a different requirement. Cache by requirement_id so tests
            # sharing a requirement don't each re-query get_requirement_metrics() (N+1).
            metrics_by_requirement_id: Dict[Any, List] = {
                sample_test.requirement_id: sample_metrics
            }
            for test in tests:
                tid = str(test.id)
                if test is sample_test:
                    metrics = sample_metrics
                elif test.requirement_id in metrics_by_requirement_id:
                    metrics = metrics_by_requirement_id[test.requirement_id]
                else:
                    metrics = get_test_metrics(
                        test,
                        session,
                        organization_id,
                        user_id,
                        test_set=test_set,
                        test_configuration=test_config,
                    )
                    metrics_by_requirement_id[test.requirement_id] = metrics
                models = prepare_metric_configs(metrics, tid)
                per_test_metric_configs[tid] = _convert_metrics(models, f"test {tid}")
    except Exception as e:
        logger.warning(f"Failed to pre-fetch metrics: {e}")

    # Resolve per-metric judge models now, while the session is still open. Metric
    # evaluation happens after session.close(), so a `model_id` left unresolved here
    # cannot be honoured later and the metric would quietly fall back to the default
    # judge instead of the model the user picked.
    metric_models = _resolve_metric_judge_models(
        session, organization_id, metric_configs, per_test_metric_configs
    )

    # Batch check existing results
    existing_result_ids: Set[str] = set()
    try:
        from rhesis.backend.app.models.test_result import TestResult

        existing = (
            session.query(TestResult.test_id)
            .filter(
                TestResult.test_run_id == test_run.id,
                TestResult.test_configuration_id == test_config.id,
                TestResult.deleted_at.is_(None),
            )
            .all()
        )
        existing_result_ids = {str(r.test_id) for r in existing}
    except Exception as e:
        logger.warning(f"Failed to batch-check existing results: {e}")

    # Build connector metric sender
    connector_metric_sender = None
    try:
        from rhesis.backend.jobs.execution.executors.runners import (
            _build_connector_metric_sender,
        )

        project_id = str(endpoint.project_id) if endpoint.project_id else None
        environment = endpoint.environment
        connector_metric_sender = _build_connector_metric_sender(
            project_id, environment, organization_id
        )
    except Exception as e:
        logger.warning(f"Failed to build connector metric sender: {e}")

    # Read concurrency / retry config from test_config.attributes with env override.
    batch_concurrency = int(
        os.environ.get(
            "BATCH_CONCURRENCY",
            attrs.get("batch_concurrency", DEFAULT_BATCH_CONCURRENCY),
        )
    )
    per_test_timeout = attrs.get("per_test_timeout", DEFAULT_PER_TEST_TIMEOUT)
    invoke_max_attempts = int(attrs.get("invoke_max_attempts", DEFAULT_INVOKE_MAX_ATTEMPTS))
    invoke_retry_min_wait = float(attrs.get("invoke_retry_min_wait", DEFAULT_INVOKE_RETRY_MIN_WAIT))
    invoke_retry_max_wait = float(attrs.get("invoke_retry_max_wait", DEFAULT_INVOKE_RETRY_MAX_WAIT))
    recovery_rounds = int(
        os.environ.get("RECOVERY_ROUNDS", attrs.get("recovery_rounds", DEFAULT_RECOVERY_ROUNDS))
    )

    # Expunge models for safe cross-context use
    session.expunge(endpoint)
    session.expunge(test_config)
    session.expunge(test_run)
    session.expunge(test_set)
    for td in test_data.values():
        try:
            session.expunge(td["test"])
        except Exception:
            pass

    return ExecutionContext(
        test_config=test_config,
        test_run=test_run,
        test_set=test_set,
        endpoint=endpoint,
        organization_id=organization_id,
        user_id=user_id,
        project_id=project_id,
        execution_model=execution_model,
        evaluation_model=evaluation_model,
        metric_configs=metric_configs,
        per_test_metric_configs=per_test_metric_configs,
        metric_models=metric_models,
        test_data=test_data,
        existing_result_ids=existing_result_ids,
        batch_concurrency=batch_concurrency,
        per_test_timeout=per_test_timeout,
        connector_metric_sender=connector_metric_sender,
        reference_test_run_id=reference_test_run_id,
        trace_id=trace_id,
        invoke_max_attempts=invoke_max_attempts,
        invoke_retry_min_wait=invoke_retry_min_wait,
        invoke_retry_max_wait=invoke_retry_max_wait,
        recovery_rounds=recovery_rounds,
    )
