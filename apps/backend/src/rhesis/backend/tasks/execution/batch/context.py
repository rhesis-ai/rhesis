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
    execution_model: Any = None
    evaluation_model: Any = None
    # SDK MetricConfig objects built while the DB session is open (ORM-safe after close).
    metric_configs: List[MetricConfig] = field(default_factory=list)
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


def prefetch_execution_context(
    session: Session,
    test_config: TestConfiguration,
    test_run: TestRun,
    tests: List[Test],
    reference_test_run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> ExecutionContext:
    """Pre-fetch all shared data in a single session before async execution."""
    from rhesis.backend.app import crud
    from rhesis.backend.app.database import set_session_variables
    from rhesis.backend.app.services.test_set import get_test_set
    from rhesis.backend.tasks.execution.executors.data import get_test_metrics

    organization_id = str(test_config.organization_id) if test_config.organization_id else ""
    user_id = str(test_config.user_id) if test_config.user_id else None

    set_session_variables(session, organization_id, user_id or "")

    test_set = get_test_set(session, str(test_config.test_set_id))

    endpoint = session.query(Endpoint).filter(Endpoint.id == test_config.endpoint_id).first()
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
        from rhesis.backend.app.constants import DEFAULT_EVALUATION_MODEL, DEFAULT_EXECUTION_MODEL
        from rhesis.backend.app.utils.user_model_utils import (
            get_evaluation_model_with_override,
            get_execution_model_with_override,
        )

        override_execution_model_id = attrs.get("execution_model_id")
        override_evaluation_model_id = attrs.get("evaluation_model_id")

        if user_id:
            user = crud.get_user_by_id(session, user_id)
            if user:
                execution_model = get_execution_model_with_override(
                    session, user, model_id=override_execution_model_id
                )
                evaluation_model = get_evaluation_model_with_override(
                    session, user, model_id=override_evaluation_model_id
                )
            else:
                logger.warning(f"User {user_id} not found, using default models")
                execution_model = DEFAULT_EXECUTION_MODEL
                evaluation_model = DEFAULT_EVALUATION_MODEL
        else:
            execution_model = DEFAULT_EXECUTION_MODEL
            evaluation_model = DEFAULT_EVALUATION_MODEL
    except Exception as e:
        from rhesis.backend.app.constants import DEFAULT_EVALUATION_MODEL, DEFAULT_EXECUTION_MODEL

        logger.warning(f"Failed to resolve execution/evaluation models: {e}")
        if execution_model is None:
            execution_model = DEFAULT_EXECUTION_MODEL
        if evaluation_model is None:
            evaluation_model = DEFAULT_EVALUATION_MODEL

    # Pre-fetch per-test data
    test_data: Dict[str, Any] = {}
    for test in tests:
        try:
            from rhesis.backend.tasks.execution.executors.data import get_test_and_prompt

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
    metric_configs: List[MetricConfig] = []
    try:
        sample_test = tests[0] if tests else None
        if sample_test:
            metrics = get_test_metrics(
                sample_test,
                session,
                organization_id,
                user_id,
                test_set=test_set,
                test_configuration=test_config,
            )
            from rhesis.backend.tasks.execution.executors.metrics import (
                prepare_metric_configs,
            )

            metric_models = prepare_metric_configs(metrics, str(sample_test.id))
            for m in metric_models:
                try:
                    metric_configs.append(metric_model_to_config(m))
                except Exception as conv_err:
                    logger.warning(
                        f"Failed to convert metric {getattr(m, 'id', '?')} to "
                        f"MetricConfig for test {sample_test.id}: {conv_err}"
                    )
    except Exception as e:
        logger.warning(f"Failed to pre-fetch metrics: {e}")

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
        from rhesis.backend.tasks.execution.executors.runners import (
            _build_connector_metric_sender,
        )

        project_id = str(endpoint.project_id) if endpoint.project_id else None
        environment = endpoint.environment
        connector_metric_sender = _build_connector_metric_sender(project_id, environment)
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
        execution_model=execution_model,
        evaluation_model=evaluation_model,
        metric_configs=metric_configs,
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
