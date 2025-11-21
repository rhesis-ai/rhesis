"""
Multi-turn test executor using Penelope.

Handles agentic multi-turn test execution where Penelope orchestrates
conversations to achieve test goals.

This executor is intentionally simple and loosely coupled:
- It extracts only the metrics from Penelope's result
- It stores the complete Penelope trace as-is without processing
- This preserves all information and avoids tight coupling to Penelope's structure
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.executors.base import BaseTestExecutor
from rhesis.backend.tasks.execution.executors.shared import (
    check_existing_result,
    create_test_result_record,
    get_test_and_prompt,
)
from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget


class MultiTurnTestExecutor(BaseTestExecutor):
    """
    Executor for multi-turn tests using Penelope agent.

    This executor handles agentic multi-turn test execution:
    1. Initialize Penelope agent with test configuration
    2. Create BackendEndpointTarget for the endpoint
    3. Execute test using Penelope
    4. Extract metrics from Penelope's result
    5. Store complete trace as-is (no processing)

    Design principle: Loose coupling
    - We only extract metrics (same field used by both single and multi-turn)
    - All other Penelope data is stored unchanged
    - No dependencies on Penelope's internal structure
    - Penelope can evolve without breaking this code
    """

    def execute(
        self,
        db: Session,
        test_config_id: str,
        test_run_id: str,
        test_id: str,
        endpoint_id: str,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute a multi-turn test using Penelope.

        Args:
            db: Database session
            test_config_id: UUID string of the test configuration
            test_run_id: UUID string of the test run
            test_id: UUID string of the test
            endpoint_id: UUID string of the endpoint
            organization_id: UUID string of the organization (optional)
            user_id: UUID string of the user (optional)
            model: Optional model override for Penelope (uses Penelope's default if None)

        Returns:
            Dictionary with test execution results:
            {
                "test_id": str,
                "execution_time": float (milliseconds),
                "metrics": Dict[str, Any]  # From Penelope goal evaluation
            }

        Raises:
            ValueError: If test configuration is invalid
            Exception: If Penelope execution fails
        """
        logger.info(f"[MultiTurnExecutor] Starting multi-turn test execution for test {test_id}")
        start_time = datetime.utcnow()

        try:
            # Check for existing result to avoid duplicates
            existing_result = check_existing_result(
                db, test_config_id, test_run_id, test_id, organization_id, user_id
            )
            if existing_result:
                logger.info(f"[MultiTurnExecutor] Found existing result for test {test_id}")
                return existing_result

            # Retrieve test data - validation ensures goal exists in test_configuration
            test, _, _ = get_test_and_prompt(db, test_id, organization_id)

            # Extract multi-turn configuration from test
            # Validation in get_test_and_prompt ensures goal exists for multi-turn tests
            test_config = test.test_configuration or {}

            # Get test parameters from configuration
            goal = test_config["goal"]  # Required field, validated in get_test_and_prompt
            instructions = test_config.get("instructions")
            scenario = test_config.get("scenario")
            restrictions = test_config.get("restrictions")
            context = test_config.get("context")
            max_turns = test_config.get("max_turns", 10)

            logger.debug(
                f"[MultiTurnExecutor] Configuration - goal: {goal[:50]}..., "
                f"max_turns: {max_turns}, has_instructions: {instructions is not None}"
            )

            # Initialize Penelope agent
            from rhesis.penelope import PenelopeAgent

            # Use provided model or let Penelope use its default
            agent = PenelopeAgent(model=model) if model else PenelopeAgent()
            logger.debug("[MultiTurnExecutor] Initialized Penelope agent")

            # Create backend-specific target
            target = BackendEndpointTarget(
                db=db,
                endpoint_id=endpoint_id,
                organization_id=organization_id,
                user_id=user_id,
            )
            logger.debug(
                f"[MultiTurnExecutor] Created BackendEndpointTarget for endpoint {endpoint_id}"
            )

            # Execute test with Penelope
            logger.info("[MultiTurnExecutor] Executing Penelope test...")
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
                f"[MultiTurnExecutor] Penelope execution completed in {execution_time:.2f}ms "
                f"({penelope_result.turns_used} turns)"
            )

            # Convert Penelope result to dict using Pydantic v2's model_dump
            # mode="json" ensures all data (including datetime) is JSON-serializable
            penelope_trace = penelope_result.model_dump(mode="json")

            # Extract metrics (pop them from the trace)
            metrics_results = penelope_trace.pop("metrics", {})

            # Store the complete Penelope trace as-is (no processing, no loss of information)
            processed_result = penelope_trace

            # Store result
            create_test_result_record(
                db=db,
                test=test,
                test_config_id=test_config_id,
                test_run_id=test_run_id,
                test_id=test_id,
                organization_id=organization_id,
                user_id=user_id,
                execution_time=execution_time,
                metrics_results=metrics_results,
                processed_result=processed_result,
            )

            # Return execution summary
            result_summary = {
                "test_id": test_id,
                "execution_time": execution_time,
                "metrics": metrics_results,
            }

            logger.info(
                f"[MultiTurnExecutor] Multi-turn test execution completed successfully "
                f"for test {test_id}"
            )
            return result_summary

        except Exception as e:
            logger.error(
                f"[MultiTurnExecutor] Multi-turn test execution failed for test "
                f"{test_id}: {str(e)}",
                exc_info=True,
            )
            raise
