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
    """
    Collect and aggregate results from test execution.
    
    This task is called as a callback after all individual test execution tasks have completed.
    It updates the test run status and aggregates metrics from all tests.
    """
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
        metrics_by_name = defaultdict(list)
        error_metrics = defaultdict(list)  # Separate tracking for error metrics
        
        for result in results:
            metrics = result.get("metrics", {}) if result else {}
            for metric_key, metric_data in metrics.items():
                if metric_data and isinstance(metric_data, dict):
                    # Extract the actual metric name from the metric data
                    # Priority: 1. name from metric_data, 2. name from details, 3. fallback to key
                    metric_name = None
                    
                    # Check if there's a name in the metric data itself first
                    if "name" in metric_data:
                        metric_name = metric_data["name"]
                    
                    # If no name in metric data, check if there's a name in the details
                    elif "details" in metric_data and isinstance(metric_data["details"], dict):
                        metric_name = metric_data["details"].get("name")
                    
                    # Fallback to the metric key if no name is found
                    if not metric_name:
                        metric_name = metric_key
                    
                    # Store the complete metric information including class name
                    metric_info = {
                        "score": metric_data.get("score"),
                        "class_name": metric_data.get("class_name", metric_key),  # Use actual class_name from metric data
                        "name": metric_name,
                        "details": metric_data.get("details", {}),
                        "is_error": metric_data.get("error") is not None or metric_data.get("is_successful") is False
                    }
                    
                    # Check if this is an error metric or has valid score for aggregation
                    if metric_info["is_error"] or not isinstance(metric_info["score"], (int, float)):
                        # This is an error metric - track separately
                        error_metrics[metric_name].append(metric_info)
                    else:
                        # Valid metric with numeric score
                        metrics_by_name[metric_name].append(metric_info)
                elif isinstance(metric_data, (int, float)):
                    # Handle case where metric_data is directly a numeric value
                    metric_info = {
                        "score": metric_data,
                        "class_name": metric_key,
                        "name": metric_key,
                        "details": {},
                        "is_error": False
                    }
                    metrics_by_name[metric_key].append(metric_info)

        # Calculate average and preserve detailed information for each metric
        aggregated_metrics = {}
        
        # Process valid metrics with numeric scores
        for metric_name, metric_instances in metrics_by_name.items():
            if metric_instances:
                scores = [instance["score"] for instance in metric_instances]
                # Get class name from first instance (should be consistent)
                class_name = metric_instances[0]["class_name"]
                
                aggregated_metrics[metric_name] = {
                    "name": metric_name,
                    "class_name": class_name,
                    "average_score": sum(scores) / len(scores),
                    "score_count": len(scores),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "all_scores": scores,
                    "sample_details": metric_instances[0]["details"],
                    "status": "success"
                }

        # Process error metrics
        for metric_name, error_instances in error_metrics.items():
            if error_instances:
                # Get class name from first instance
                class_name = error_instances[0]["class_name"]
                
                # Collect all error reasons
                error_reasons = []
                for instance in error_instances:
                    if instance["details"].get("reason"):
                        error_reasons.append(instance["details"]["reason"])
                    elif instance.get("error"):
                        error_reasons.append(str(instance["error"]))
                
                aggregated_metrics[metric_name] = {
                    "name": metric_name,
                    "class_name": class_name,
                    "error_count": len(error_instances),
                    "error_reasons": error_reasons,
                    "sample_details": error_instances[0]["details"],
                    "status": "error"
                }

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
                
            # Update test run status - this will also update task_state
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