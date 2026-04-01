"""Core test execution runners - shared by executors and in-place service."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.execution.constants import PENELOPE_EVALUATED_METRICS, MetricScope
from rhesis.backend.tasks.execution.evaluation import (
    evaluate_multi_turn_metrics,
    evaluate_single_turn_metrics,
)
from rhesis.backend.tasks.execution.executors.output_providers import (
    MultiTurnOutput,
    OutputProvider,
    SingleTurnOutput,
)
from rhesis.backend.tasks.execution.response_extractor import (
    normalize_context_to_list,
)

from .data import get_test_metrics
from .metrics import prepare_metric_configs

logger = logging.getLogger(__name__)


def _get_endpoint_routing(
    db: Session,
    endpoint_id: str,
    organization_id: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Look up project_id and environment from an endpoint."""
    try:
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.query_utils import QueryBuilder

        qb = QueryBuilder(db, models.Endpoint).with_organization_filter(organization_id)
        endpoint = qb.query.filter(models.Endpoint.id == endpoint_id).first()
        if endpoint:
            return str(endpoint.project_id), endpoint.environment
    except Exception as e:
        logger.warning(f"Could not resolve endpoint routing: {e}")
    return None, None


def _build_connector_metric_sender(
    project_id: Optional[str],
    environment: Optional[str],
):
    """Build an async callable that dispatches connector metrics via WebSocket RPC.

    Returns None when project/environment are unavailable, which tells
    the evaluator to skip connector metrics.
    """
    if not project_id or not environment:
        return None

    async def _send(metric_run_id, metric_name, inputs):
        from rhesis.backend.app.services.connector.rpc_client import (
            SDKRpcClient,
        )

        rpc = SDKRpcClient()
        try:
            await rpc.initialize()
            return await rpc.send_and_await_metric_result(
                project_id=project_id,
                environment=environment,
                metric_run_id=metric_run_id,
                metric_name=metric_name,
                inputs=inputs,
                timeout=30.0,
            )
        finally:
            await rpc.close()

    return _send


class BaseRunner(ABC):
    """
    Abstract base class for test execution runners.

    Defines the contract that all runners must implement. Runners encapsulate
    the core test execution logic that is shared between executors (with DB
    persistence) and in-place service (ephemeral results).
    """

    @abstractmethod
    async def run(
        self,
        db: Session,
        test: Test,
        endpoint_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
        model: Optional[Any] = None,
        **kwargs: Any,
    ) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
        """
        Execute test and return results.

        Args:
            db: Database session
            test: Test model instance
            endpoint_id: Endpoint to test
            organization_id: Organization ID
            user_id: User ID (optional)
            model: Optional model override for evaluation
            **kwargs: Additional runner-specific parameters

        Returns:
            Tuple of (execution_time_ms, test_output, metrics_results)

        Raises:
            Exception: If test execution fails
        """
        pass


class SingleTurnRunner(BaseRunner):
    """
    Core single-turn test execution logic.

    Shared by SingleTurnTestExecutor (with DB persistence) and
    in-place execution service (ephemeral results).
    """

    async def run(
        self,
        db: Session,
        test: Test,
        endpoint_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
        model: Optional[Any] = None,
        prompt_content: str = "",
        expected_response: str = "",
        evaluate_metrics: bool = True,
        test_execution_context: Optional[Dict[str, str]] = None,
        test_set: Optional[Any] = None,
        test_configuration: Optional[Any] = None,
        output_provider: Optional[OutputProvider] = None,
    ) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
        """
        Execute single-turn test.

        Args:
            db: Database session
            test: Test model instance
            prompt_content: Prompt text
            expected_response: Expected response for evaluation
            endpoint_id: Endpoint to test
            organization_id: Organization ID
            user_id: User ID
            model: Optional model override for metric evaluation
            evaluate_metrics: Whether to evaluate metrics
            test_execution_context: Optional dict with test_run_id,
                test_result_id, test_id
            test_set: Optional TestSet model instance for metric override
            test_configuration: Optional TestConfiguration for
                execution-time metric override
            output_provider: Optional OutputProvider to obtain output.
                If None, uses default SingleTurnOutput (live endpoint).

        Returns:
            Tuple of (execution_time_ms, processed_result, metrics_results)
        """
        test_id = str(test.id)

        # Prepare metrics if evaluation requested
        # Metric resolution priority: execution-time > test set > behavior
        metric_configs = []
        if evaluate_metrics:
            metrics = get_test_metrics(
                test,
                db,
                organization_id,
                user_id,
                test_set=test_set,
                test_configuration=test_configuration,
            )
            metric_configs = prepare_metric_configs(metrics, test_id, scope=MetricScope.SINGLE_TURN)
            logger.debug(f"Prepared {len(metric_configs)} metrics for test {test_id}")

        # --- Entity 1: Get output ---
        if output_provider is None:
            output_provider = SingleTurnOutput()

        output = await output_provider.get_output(
            db=db,
            endpoint_id=endpoint_id,
            prompt_content=prompt_content,
            organization_id=organization_id,
            user_id=user_id,
            test_execution_context=test_execution_context,
            test_id=test_id,
        )

        execution_time = output.execution_time
        processed_result = output.response

        # --- Entity 2: Evaluate metrics ---
        metrics_results = {}
        if evaluate_metrics and metric_configs:
            # Extract and normalize context to List[str]
            raw_context = processed_result.get("context") if processed_result else None
            context = normalize_context_to_list(raw_context)

            ep_project_id, ep_environment = _get_endpoint_routing(db, endpoint_id, organization_id)

            metrics_evaluator = MetricEvaluator(
                model=model,
                db=db,
                organization_id=organization_id,
                connector_metric_sender=_build_connector_metric_sender(
                    ep_project_id, ep_environment
                ),
            )

            if model:
                logger.debug(f"[SingleTurnRunner] Using model: {model}")

            metrics_results = evaluate_single_turn_metrics(
                metrics_evaluator=metrics_evaluator,
                prompt_content=prompt_content,
                expected_response=expected_response,
                context=context,
                result=processed_result,
                metrics=metric_configs,
            )

        return execution_time, processed_result, metrics_results


def _signal_penelope_conversation_complete(
    db: Session,
    penelope_trace: Dict[str, Any],
    project_id: str,
    organization_id: str,
) -> None:
    """Signal that a Penelope multi-turn conversation is finished.

    Extracts the conversation_id from the Penelope trace, resolves the
    corresponding trace_id, and dispatches an immediate conversation-level
    trace metrics evaluation (bypassing the production debounce timeout).
    """
    conversation_id = None
    for turn in penelope_trace.get("conversation_summary", []):
        if turn.get("conversation_id"):
            conversation_id = turn["conversation_id"]
            break

    if not conversation_id:
        return

    try:
        from rhesis.backend.app import crud
        from rhesis.backend.app.services.telemetry.trace_metrics_cache import (
            signal_conversation_complete,
        )

        trace_id = crud.get_trace_id_for_conversation(
            db,
            conversation_id,
            project_id,
            organization_id,
        )
        if not trace_id:
            return

        signal_conversation_complete(trace_id, project_id, organization_id)
        logger.info(
            f"[MultiTurnRunner] Signaled conversation complete "
            f"for trace {trace_id} (conversation_id={conversation_id})"
        )
    except Exception as e:
        logger.warning(
            f"[MultiTurnRunner] Failed to signal conversation complete "
            f"for conversation_id={conversation_id}: {e}"
        )


class MultiTurnRunner(BaseRunner):
    """
    Core multi-turn test execution logic using Penelope.

    Shared by MultiTurnTestExecutor (with DB persistence) and
    in-place execution service (ephemeral results).
    """

    async def run(
        self,
        db: Session,
        test: Test,
        endpoint_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
        model: Optional[Any] = None,
        test_execution_context: Optional[Dict[str, str]] = None,
        test_set: Optional[Any] = None,
        test_configuration: Optional[Any] = None,
        output_provider: Optional[OutputProvider] = None,
    ) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
        """
        Execute multi-turn test with Penelope.

        Args:
            db: Database session
            test: Test model instance
            endpoint_id: Endpoint to test
            organization_id: Organization ID
            user_id: User ID
            model: Optional model override for Penelope
            test_execution_context: Optional dict with test_run_id,
                test_result_id, test_id
            test_set: Optional TestSet model instance for metric override
            test_configuration: Optional TestConfiguration for
                execution-time metric override
            output_provider: Optional OutputProvider to obtain output.
                If None, uses default MultiTurnOutput (live Penelope).

        Returns:
            Tuple of (execution_time_ms, penelope_trace, metrics_results)

        Note:
            When output_provider is None (live execution), multi-turn
            metrics are evaluated by Penelope internally. When a stored
            provider is injected, metrics are evaluated externally via
            evaluate_multi_turn_metrics().
        """
        # --- Entity 1: Get output ---
        if output_provider is None:
            output_provider = MultiTurnOutput(model=model)

        output = await output_provider.get_output(
            db=db,
            test=test,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
            test_execution_context=test_execution_context,
            test_id=str(test.id),
        )

        execution_time = output.execution_time
        penelope_trace = output.response

        # --- Entity 2: Evaluate metrics ---
        ep_project_id, ep_environment = _get_endpoint_routing(db, endpoint_id, organization_id)

        if output.source == "live" and ep_project_id:
            _signal_penelope_conversation_complete(
                db, penelope_trace, ep_project_id, organization_id
            )

        if output.metrics:
            # Live execution: Penelope already evaluated Goal Achievement
            metrics_results = output.metrics

            # Evaluate additional multi-turn metrics from three-tier model
            # (excluding GoalAchievementJudge which Penelope already evaluated)
            additional_metrics = evaluate_multi_turn_metrics(
                stored_output=penelope_trace,
                test=test,
                db=db,
                organization_id=organization_id,
                user_id=user_id,
                model=model,
                test_set=test_set,
                test_configuration=test_configuration,
                exclude_class_names=PENELOPE_EVALUATED_METRICS,
                project_id=ep_project_id,
                environment=ep_environment,
            )
            if additional_metrics:
                metrics_results.update(additional_metrics)
        else:
            # Re-score / trace: evaluate ALL metrics externally
            metrics_results = evaluate_multi_turn_metrics(
                stored_output=penelope_trace,
                test=test,
                db=db,
                organization_id=organization_id,
                user_id=user_id,
                model=model,
                test_set=test_set,
                test_configuration=test_configuration,
                project_id=ep_project_id,
                environment=ep_environment,
            )

        if output.source == "live":
            logger.debug(f"[MultiTurnRunner] Completed in {execution_time:.2f}ms")

        return execution_time, penelope_trace, metrics_results
