"""Multi-turn test executor using Penelope."""

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.executors.base import BaseTestExecutor
from rhesis.backend.tasks.execution.executors.data import get_test_and_prompt
from rhesis.backend.tasks.execution.executors.output_providers import (
    OutputProvider,
    get_provider_metadata,
)
from rhesis.backend.tasks.execution.executors.results import (
    check_existing_result,
    create_test_result_record,
)
from rhesis.backend.tasks.execution.executors.runners import MultiTurnRunner


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

    async def execute(
        self,
        db: Session,
        test_config_id: str,
        test_run_id: str,
        test_id: str,
        endpoint_id: str,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[Any] = None,
        output_provider: Optional[OutputProvider] = None,
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
            output_provider: Optional OutputProvider. If provided, used
                instead of live Penelope execution (e.g., for re-scoring).

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

            # Load test_configuration for metric override support
            # Metric resolution priority: execution-time > test set > behavior
            test_config = None
            test_set = None
            if test_config_id:
                test_config = (
                    db.query(TestConfiguration)
                    .filter(TestConfiguration.id == UUID(test_config_id))
                    .first()
                )
                if test_config:
                    test_set = test_config.test_set

            # Create test execution context for trace linking
            test_execution_context = {
                "test_run_id": test_run_id,
                "test_id": test_id,
                "test_configuration_id": test_config_id,
            }

            # Run core execution (shared with in-place service)
            runner = MultiTurnRunner()
            execution_time, penelope_trace, metrics_results = await runner.run(
                db=db,
                test=test,
                endpoint_id=endpoint_id,
                organization_id=organization_id,
                user_id=user_id,
                model=model,
                test_execution_context=test_execution_context,
                test_set=test_set,
                test_configuration=test_config,
                output_provider=output_provider,
            )

            # Store result and link traces
            test_result_id = create_test_result_record(
                db=db,
                test=test,
                test_config_id=test_config_id,
                test_run_id=test_run_id,
                test_id=test_id,
                organization_id=organization_id,
                user_id=user_id,
                execution_time=execution_time,
                metrics_results=metrics_results,
                processed_result=penelope_trace,
                metadata=get_provider_metadata(output_provider),
            )

            # Return execution summary
            result_summary = {
                "test_id": test_id,
                "test_result_id": str(test_result_id) if test_result_id else None,
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
