"""Core test execution runners - shared by executors and in-place service."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.execution.constants import MetricScope
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
            metrics_evaluator = MetricEvaluator(model=model, db=db, organization_id=organization_id)

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
        if output.metrics:
            # Live execution: Penelope already evaluated metrics
            metrics_results = output.metrics
        else:
            # Re-score / trace: evaluate externally
            metrics_results = evaluate_multi_turn_metrics(
                stored_output=penelope_trace,
                test=test,
                db=db,
                organization_id=organization_id,
                user_id=user_id,
                model=model,
                test_set=test_set,
                test_configuration=test_configuration,
            )

        if output.source == "live":
            logger.debug(f"[MultiTurnRunner] Completed in {execution_time:.2f}ms")

        return execution_time, penelope_trace, metrics_results
