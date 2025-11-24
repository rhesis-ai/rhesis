"""Core test execution runners - shared by executors and in-place service."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.app.models.test import Test
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.execution.constants import MetricScope
from rhesis.backend.tasks.execution.evaluation import evaluate_prompt_response
from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget
from rhesis.backend.tasks.execution.response_extractor import normalize_context_to_list

from .data import get_test_metrics
from .metrics import prepare_metric_configs
from .results import process_endpoint_result


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

        Returns:
            Tuple of (execution_time_ms, processed_result, metrics_results)
        """
        start_time = datetime.utcnow()
        test_id = str(test.id)

        # Prepare metrics if evaluation requested
        metric_configs = []
        if evaluate_metrics:
            metrics = get_test_metrics(test, db, organization_id, user_id)
            metric_configs = prepare_metric_configs(metrics, test_id, scope=MetricScope.SINGLE_TURN)
            logger.debug(f"[SingleTurnRunner] Prepared {len(metric_configs)} metrics")

        # Execute endpoint
        endpoint_service = get_endpoint_service()
        result = await endpoint_service.invoke_endpoint(
            db=db,
            endpoint_id=endpoint_id,
            input_data={"input": prompt_content},
            organization_id=organization_id,
            user_id=user_id,
        )

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.debug(f"[SingleTurnRunner] Completed in {execution_time:.2f}ms")

        # Process result (converts ErrorResponse to dict if needed)
        processed_result = process_endpoint_result(result)

        # Evaluate metrics if requested
        metrics_results = {}
        if evaluate_metrics and metric_configs:
            # Extract and normalize context to List[str]
            # SDK functions may return context as string, JSON string, list, etc.
            raw_context = processed_result.get("context") if processed_result else None
            context = normalize_context_to_list(raw_context)
            metrics_evaluator = MetricEvaluator(model=model, db=db, organization_id=organization_id)

            if model:
                logger.debug(f"[SingleTurnRunner] Using model: {model}")

            # Pass processed_result (dict) instead of raw result
            metrics_results = evaluate_prompt_response(
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

        Returns:
            Tuple of (execution_time_ms, penelope_trace, metrics_results)
        """
        start_time = datetime.utcnow()

        # Extract multi-turn configuration
        test_config = test.test_configuration or {}
        goal = test_config["goal"]  # Required, validated by get_test_and_prompt
        instructions = test_config.get("instructions")
        scenario = test_config.get("scenario")
        restrictions = test_config.get("restrictions")
        context = test_config.get("context")
        max_turns = test_config.get("max_turns", 10)

        logger.debug(f"[MultiTurnRunner] Config - goal: {goal[:50]}..., max_turns: {max_turns}")

        # Initialize Penelope agent
        from rhesis.penelope import PenelopeAgent

        agent = PenelopeAgent(model=model) if model else PenelopeAgent()
        logger.debug("[MultiTurnRunner] Initialized Penelope")

        # Create backend target
        target = BackendEndpointTarget(
            db=db,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
        )

        # Execute test
        logger.info("[MultiTurnRunner] Executing Penelope test...")
        penelope_result = agent.execute_test(
            target=target,
            goal=goal,
            instructions=instructions,
            scenario=scenario,
            restrictions=restrictions,
            context=context,
            max_turns=max_turns,
        )

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.debug(
            f"[MultiTurnRunner] Completed in {execution_time:.2f}ms "
            f"({penelope_result.turns_used} turns)"
        )

        # Extract results
        penelope_trace = penelope_result.model_dump(mode="json")
        metrics_results = penelope_trace.pop("metrics", {})

        return execution_time, penelope_trace, metrics_results
