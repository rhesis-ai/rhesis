"""
Multi-turn test executor using Penelope.

Handles agentic multi-turn test execution where Penelope orchestrates
conversations to achieve test goals.
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
    4. Parse Penelope's execution trace
    5. Store results in standard format

    Unlike single-turn tests, metrics are evaluated by Penelope during execution,
    not by the worker afterward.
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

            # Retrieve test data
            test, prompt_content, expected_response = get_test_and_prompt(
                db, test_id, organization_id
            )

            # Extract multi-turn configuration from test
            test_config = test.test_configuration or {}
            
            # Get test parameters from configuration
            goal = test_config.get("goal", prompt_content)  # Use prompt as fallback goal
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

            # Parse Penelope result into standard format
            metrics_results = self._parse_penelope_metrics(penelope_result)
            processed_result = self._parse_penelope_output(penelope_result)

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

    def _parse_penelope_metrics(self, penelope_result) -> Dict[str, Any]:
        """
        Parse Penelope's TestResult into standard metrics format.

        Args:
            penelope_result: Penelope's TestResult object

        Returns:
            Dictionary of metrics in standard format matching single-turn structure
        """
        metrics = {}

        # Add Goal Achievement metric (primary metric for multi-turn tests)
        if (
            hasattr(penelope_result, "goal_evaluation")
            and penelope_result.goal_evaluation
        ):
            eval_data = penelope_result.goal_evaluation

            metrics["Goal Achievement"] = {
                "name": "Goal Achievement",
                "score": 1.0 if eval_data.all_criteria_met else 0.0,
                "is_successful": eval_data.all_criteria_met,
                "reason": eval_data.reasoning,
                "backend": "penelope",
                "criteria_met": len([c for c in eval_data.criteria_evaluations if c.met]),
                "criteria_total": len(eval_data.criteria_evaluations),
                "confidence": eval_data.confidence,
                "evidence": eval_data.evidence,
            }

        # Add any additional metrics from Penelope (if future versions include them)
        if hasattr(penelope_result, "metrics") and penelope_result.metrics:
            for metric_name, metric_data in penelope_result.metrics.items():
                if metric_name not in metrics:  # Don't override Goal Achievement
                    metrics[metric_name] = metric_data

        return metrics

    def _parse_penelope_output(self, penelope_result) -> Dict[str, Any]:
        """
        Parse Penelope's TestResult into standard output format.

        Args:
            penelope_result: Penelope's TestResult object

        Returns:
            Dictionary with test output in standard format
        """
        return {
            "status": (
                penelope_result.status.value
                if hasattr(penelope_result.status, "value")
                else str(penelope_result.status)
            ),
            "goal_achieved": penelope_result.goal_achieved,
            "turns_used": penelope_result.turns_used,
            "findings": penelope_result.findings,
            "history": [
                {
                    "turn_number": turn.turn_number,
                    "reasoning": turn.reasoning,
                    "assistant_content": (
                        turn.assistant_message.content if turn.assistant_message else None
                    ),
                    "tool_calls": (
                        len(turn.assistant_message.tool_calls)
                        if (
                            turn.assistant_message
                            and turn.assistant_message.tool_calls
                        )
                        else 0
                    ),
                    "tool_response": (
                        turn.tool_message.content if turn.tool_message else None
                    ),
                }
                for turn in penelope_result.history
            ],
            "execution_stats": {
                "total_turns": penelope_result.turns_used,
                "goal_evaluation": (
                    penelope_result.goal_evaluation.dict()
                    if penelope_result.goal_evaluation
                    else None
                ),
            },
        }

