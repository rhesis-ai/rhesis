from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from celery import chord
from sqlalchemy.orm import Session

from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_result import TestResult
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.services.endpoint import invoke
from rhesis.backend.app.services.test_set import get_test_set
from rhesis.backend.app.utils.status import get_or_create_status
from rhesis.backend.celery_app import app
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks import BaseTask

# Constants
DEFAULT_METRIC_WORKERS = 5
DEFAULT_RESULT_STATUS = "Pass"
DEFAULT_RUN_STATUS_PROGRESS = "Progress"
DEFAULT_RUN_STATUS_COMPLETED = "Completed"
DEFAULT_RUN_STATUS_FAILED = "Failed"


class TestConfigurationError(Exception):
    """Exception raised for errors in test configuration."""

    pass


class TestExecutionError(Exception):
    """Exception raised for errors during test execution."""

    pass


def get_test_configuration(session: Session, test_configuration_id: str) -> TestConfiguration:
    """Retrieve and validate test configuration."""
    test_config = (
        session.query(TestConfiguration)
        .filter(TestConfiguration.id == UUID(test_configuration_id))
        .first()
    )

    if not test_config:
        raise ValueError(f"Test configuration {test_configuration_id} not found")

    if not test_config.test_set_id:
        raise ValueError(f"Test configuration {test_configuration_id} has no test set assigned")

    return test_config


def create_test_run(session: Session, test_config: TestConfiguration, task_info: Dict) -> TestRun:
    """Create a new test run with initial status and metadata."""
    initial_status = get_or_create_status(session, "Progress", "TestRun")

    test_run = TestRun(
        test_configuration_id=test_config.id,
        user_id=test_config.user_id,
        status=initial_status,
        attributes={
            "started_at": datetime.utcnow().isoformat(),
            "configuration_id": str(test_config.id),
            "task_id": task_info.get("id"),
            "task_state": "PROGRESS",
        },
    )
    session.add(test_run)
    session.flush()
    return test_run


@app.task(name="rhesis.tasks.execute_single_prompt")
def execute_single_prompt(
    test_config_id: str,
    test_run_id: str,
    prompt_id: str,
    prompt_content: str,
    expected_response: str,
    endpoint_id: str,
    user_id: str,
) -> Dict:
    """Execute a single prompt and return its results."""
    # Create session only when needed
    session = None

    try:
        # Initialize metrics evaluator outside of database operations
        metrics_evaluator = MetricEvaluator()
        start_time = datetime.utcnow()

        # First database operation - create session
        session = next(get_db())

        # Check if result already exists for this combination
        existing_result = (
            session.query(TestResult)
            .filter(
                TestResult.test_configuration_id == UUID(test_config_id),
                TestResult.test_run_id == UUID(test_run_id),
                TestResult.prompt_id == UUID(prompt_id),
            )
            .first()
        )

        if existing_result:
            # Return existing result data without creating duplicate
            # Close session early since we're done with database operations
            session.close()
            session = None
            return {
                "prompt_id": prompt_id,
                "execution_time": existing_result.test_metrics.get("execution_time"),
                "metrics": existing_result.test_metrics.get("metrics", {}),
            }

        # Get required statuses
        test_result_status = get_or_create_status(session, "Pass", "TestResult")

        logger.info(f"Starting execute task for prompt: {prompt_id}")

        # Execute prompt - this might involve external API calls
        # Close session during potentially long-running operations
        session.close()
        session = None

        input_data = {"input": prompt_content}
        # Create a new session for the invoke operation
        session = next(get_db())
        result = invoke(db=session, endpoint_id=endpoint_id, input_data=input_data)

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Get context from result
        context = result.get("context", []) if result else []

        # Close session during metrics evaluation (potentially CPU-intensive)
        session.close()
        session = None

        # Evaluate metrics - this is CPU-bound work, not DB-bound
        metrics_results = evaluate_prompt_response(
            metrics_evaluator=metrics_evaluator,
            prompt_content=prompt_content,
            expected_response=expected_response,
            context=context,
            result=result,
        )

        # Create a new session for the final database operation
        session = next(get_db())

        # Store result in database
        test_result = TestResult(
            test_configuration_id=UUID(test_config_id),
            test_run_id=UUID(test_run_id),
            prompt_id=UUID(prompt_id),
            status=test_result_status,
            user_id=UUID(user_id),
            test_metrics={"execution_time": execution_time, "metrics": metrics_results},
            test_output=result,
        )
        session.add(test_result)
        session.commit()

        logger.debug(f"Prompt execution completed successfully for prompt_id={prompt_id}")
        return {
            "prompt_id": prompt_id,
            "execution_time": execution_time,
            "metrics": metrics_results,
        }

    except Exception as e:
        logger.error(f"Error executing prompt {prompt_id}: {str(e)}", exc_info=True)
        if session:
            session.rollback()
        raise
    finally:
        if session:
            session.close()


def execute_test_cases(
    session: Session, test_config: TestConfiguration, test_run: TestRun
) -> Dict[str, Any]:
    """Execute test cases in parallel using Celery workers."""
    test_set = get_test_set(session, str(test_config.test_set_id))
    start_time = datetime.utcnow()

    # Create tasks for parallel execution
    tasks = []
    for prompt in test_set.prompts:
        task = execute_single_prompt.s(
            test_config_id=str(test_config.id),
            test_run_id=str(test_run.id),
            prompt_id=str(prompt.id),
            prompt_content=prompt.content,
            expected_response=prompt.expected_response,
            endpoint_id=str(test_config.endpoint_id),
            user_id=str(test_config.user_id),
        )
        tasks.append(task)

    # Use chord to execute tasks in parallel and collect results
    callback = collect_results.s(
        start_time=start_time.isoformat(),
        test_config_id=str(test_config.id),
        test_run_id=str(test_run.id),
        test_set_id=str(test_set.id),
        total_prompts=len(test_set.prompts),
    )
    chord(tasks)(callback)

    # Return empty results - the actual results will be processed in the callback
    return {}


@app.task
def collect_results(results, start_time, test_config_id, test_run_id, test_set_id, total_prompts):
    """Callback task to process results after all prompts are executed."""
    end_time = datetime.utcnow()
    start_dt = datetime.fromisoformat(start_time)
    total_execution_time = (end_time - start_dt).total_seconds() * 1000

    logger.info(f"Collecting results for test configuration: {test_config_id}")

    # Aggregate metrics from all results - no database needed for this
    # We use defaultdict to automatically create empty lists for new metric names
    total_metrics = defaultdict(list)
    for result in results:
        for metric_name, metric_data in result["metrics"].items():
            total_metrics[metric_name].append(metric_data["score"])

    # Calculate average, min, and max for each metric
    average_metrics = {
        metric_name: {
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
        }
        for metric_name, scores in total_metrics.items()
    }

    # Only create session when needed for database operations
    session = None
    try:
        session = next(get_db())
        test_run = session.query(TestRun).filter(TestRun.id == UUID(test_run_id)).first()
        if test_run:
            test_run.attributes.update(
                {
                    "completed_at": end_time.isoformat(),
                    "total_execution_time_ms": total_execution_time,
                    "average_prompt_time_ms": total_execution_time / total_prompts,
                    "metrics_summary": average_metrics,
                }
            )
            session.commit()
            logger.info(f"Updated test run {test_run_id} with summary metrics")
    except Exception as e:
        logger.error(f"Error updating test run with summary: {str(e)}", exc_info=True)
        if session:
            session.rollback()
    finally:
        if session:
            session.close()

    return {
        "test_set_id": test_set_id,
        "test_run_id": test_run_id,
        "total_prompts": total_prompts,
        "total_execution_time_ms": total_execution_time,
        "average_prompt_time_ms": total_execution_time / total_prompts,
        "metrics_summary": average_metrics,
    }


def evaluate_prompt_response(
    metrics_evaluator: MetricEvaluator,
    prompt_content: str,
    expected_response: str,
    context: List[str],
    result: Dict,
) -> Dict:
    """
    Evaluate the response against the prompt using metrics evaluator.

    Args:
        metrics_evaluator: Initialized metrics evaluator
        prompt_content: The prompt text sent to the model
        expected_response: The expected response for comparison
        context: List of context strings used for evaluation
        result: Dictionary containing the model's response

    Returns:
        Dictionary of metric results with scores and details

    Example:
        >>> evaluator = MetricEvaluator()
        >>> result = {"output": "Paris is the capital of France"}
        >>> metrics = evaluate_prompt_response(
        ...     evaluator,
        ...     "What is the capital of France?",
        ...     "Paris",
        ...     [],
        ...     result
        ... )
    """
    metrics_results = {}

    if result and "output" in result:
        metrics_results = metrics_evaluator.evaluate(
            input_text=prompt_content,
            output_text=result["output"],
            expected_output=expected_response,
            context=context,
        )

    return metrics_results


def update_test_run_status(
    session: Session, test_run: TestRun, status_name: str, error: str = None
) -> None:
    """Update the test run status and related attributes."""
    try:
        status = get_or_create_status(session, status_name, "TestRun")
        test_run.status = status
        test_run.attributes["task_state"] = status_name.upper()
        if error:
            test_run.attributes["error"] = error
        session.commit()
        logger.info(f"Updated test run {test_run.id} status to {status_name}")
    except Exception as e:
        logger.error(f"Failed to update test run status: {str(e)}")
        session.rollback()
        raise


@app.task(base=BaseTask, name="rhesis.tasks.execute_test_configuration", bind=True)
def execute_test_configuration(self, test_configuration_id: str) -> Dict:
    """
    Task that executes a test configuration by running its test set through its endpoint.

    Args:
        test_configuration_id: UUID string of the test configuration to execute
    Returns:
        Dict containing execution results and metadata
    """
    logger.info(f"Starting execute task for test configuration: {test_configuration_id}")

    session = None
    try:
        session = next(get_db())
        logger.info("Successfully obtained database session")

        self.update_state(state="PROGRESS", meta={"status": "Processing test configuration"})

        # Initialize test configuration and run
        test_config = get_test_configuration(session, test_configuration_id)
        task_info = {
            "id": self.request.id,
        }
        test_run = create_test_run(session, test_config, task_info)

        # Execute tests
        results = execute_test_cases(session, test_config, test_run)

        # Update status to completed
        update_test_run_status(session, test_run, "Completed")

        logger.info("Successfully executed test cases")
        return {
            "test_configuration_id": test_configuration_id,
            "test_run_id": str(test_run.id),
            "test_set_id": str(test_config.test_set_id),
            "endpoint_id": str(test_config.endpoint_id),
            "results": results,
            "status": "completed",
        }

    except Exception as e:
        if session and "test_run" in locals():
            update_test_run_status(session, test_run, "Failed", str(e))
        logger.error(f"Error during test execution: {str(e)}", exc_info=True)
        raise
    finally:
        if session:
            logger.info("Closing database session")
            session.close()


def create_session() -> Session:
    """Create and return a new database session."""
    return next(get_db())


def close_session_safely(session: Optional[Session]) -> None:
    """Safely close a session if it exists."""
    if session:
        try:
            session.close()
        except Exception as e:
            logger.error(f"Error closing session: {str(e)}")
