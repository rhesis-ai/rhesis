from collections import defaultdict
from datetime import datetime
from typing import Dict, List
from uuid import UUID

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.run import update_test_run_status
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.worker import app


# Configure the chord_unlock task to have reasonable retry limits
app.conf.chord_unlock_max_retries = 3


@app.task
def collect_results(results, start_time, test_config_id, test_run_id, test_set_id, total_tests):
    """Collect and aggregate results from test execution."""
    session = None
    try:
        session = next(get_db())

        # Check for failed tasks and count them
        failed_tasks = sum(1 for result in results if result is None)
        if failed_tasks > 0:
            logger.warning(f"{failed_tasks} tasks failed out of {total_tests} for test run {test_run_id}")

        # Calculate aggregated metrics
        execution_times = [result.get("execution_time", 0) for result in results if result]
        mean_execution_time = (
            sum(execution_times) / len(execution_times) if execution_times else 0
        )

        # Aggregate metrics from all tests
        metrics_by_type = defaultdict(list)
        for result in results:
            metrics = result.get("metrics", {}) if result else {}
            for metric_name, metric_value in metrics.items():
                if isinstance(metric_value, (int, float)):
                    metrics_by_type[metric_name].append(metric_value)

        # Calculate average for each metric
        aggregated_metrics = {}
        for metric_name, values in metrics_by_type.items():
            if values:
                aggregated_metrics[metric_name] = sum(values) / len(values)

        # Get the test run using crud
        test_run = crud.get_test_run(session, UUID(test_run_id))
        
        if test_run:
            # Update attributes with summary statistics
            test_run.attributes.update(
                {
                    "completed_at": datetime.utcnow().isoformat(),
                    "total_tests": total_tests,
                    "completed_tests": len(results) - failed_tasks,
                    "failed_tasks": failed_tasks,
                    "mean_execution_time_ms": mean_execution_time,
                    "aggregated_metrics": aggregated_metrics,
                }
            )

            # Determine status based on failures
            status = RunStatus.COMPLETED.value
            if failed_tasks > 0:
                status = RunStatus.PARTIAL.value if failed_tasks < total_tests else RunStatus.FAILED.value
                
            update_test_run_status(session, test_run, status)

        return {
            "test_run_id": test_run_id,
            "test_config_id": test_config_id,
            "total_tests": total_tests,
            "completed_tests": len(results) - failed_tasks,
            "failed_tasks": failed_tasks,
            "mean_execution_time_ms": mean_execution_time,
            "aggregated_metrics": aggregated_metrics,
        }

    except Exception as e:
        logger.error(f"Error collecting results: {str(e)}", exc_info=True)
        if session:
            # Update test run status to failed
            test_run = crud.get_test_run(session, UUID(test_run_id))
            if test_run:
                update_test_run_status(session, test_run, RunStatus.FAILED.value, str(e))
        raise
    finally:
        if session:
            session.close() 