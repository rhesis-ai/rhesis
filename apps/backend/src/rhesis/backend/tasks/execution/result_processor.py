"""
Test result processing utilities.

This module contains helper functions for processing and analyzing test execution results,
calculating statistics, determining status, and formatting data for reporting.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.tasks.utils import format_execution_time, format_execution_time_from_ms


def get_test_statistics(test_run: TestRun) -> Tuple[int, int, int]:
    """
    Calculate test statistics from test run data.

    Args:
        test_run: The test run to analyze

    Returns:
        Tuple of (total_tests, tests_passed, tests_failed)
    """
    # Get all test results for this test run
    test_results = test_run.test_results or []

    # Calculate summary statistics from test results
    total_tests = len(test_results)
    tests_passed = sum(
        1 for result in test_results if result.status and result.status.name == "passed"
    )
    tests_failed = sum(
        1 for result in test_results if result.status and result.status.name == "failed"
    )

    # Check attributes for more accurate counts (updated by individual test tasks)
    if test_run.attributes and isinstance(test_run.attributes, dict):
        attr_completed = test_run.attributes.get("completed_tests", 0)
        attr_failed = test_run.attributes.get("failed_tests", 0)
        attr_total = test_run.attributes.get("total_tests", total_tests)

        # Use attribute counts if they seem more accurate
        if attr_completed > 0 or attr_failed > 0:
            total_tests = attr_total
            tests_failed = attr_failed
            tests_passed = attr_completed - attr_failed

    return total_tests, tests_passed, tests_failed


def determine_overall_status(
    tests_passed: int, tests_failed: int, total_tests: int, logger_func
) -> Tuple[str, str]:
    """
    Determine the overall status of the test run.

    Args:
        tests_passed: Number of passed tests
        tests_failed: Number of failed tests
        total_tests: Total number of tests
        logger_func: Logging function for debug messages

    Returns:
        Tuple of (overall_status, email_status)
    """
    logger_func(
        "debug",
        f"Status calculation: tests_passed={tests_passed}, tests_failed={tests_failed}, total_tests={total_tests}",
    )

    if tests_failed == 0 and tests_passed > 0:
        overall_status, email_status = RunStatus.COMPLETED.value, "success"
        logger_func("debug", "Status logic: All tests passed -> COMPLETED")
    elif tests_failed > 0 and tests_passed > 0:
        overall_status, email_status = RunStatus.PARTIAL.value, "partial"
        logger_func("debug", "Status logic: Some tests failed, some passed -> PARTIAL")
    elif tests_failed > 0:
        overall_status, email_status = RunStatus.FAILED.value, "failed"
        logger_func("debug", "Status logic: Some tests failed -> FAILED")
    else:
        # No tests passed or failed - something went wrong
        overall_status, email_status = RunStatus.FAILED.value, "failed"
        logger_func("debug", "Status logic: No tests passed or failed -> FAILED (fallback)")

    return overall_status, email_status


def get_test_context(test_configuration) -> Tuple[str, str, str, str]:
    """
    Extract test context information from test configuration.

    Args:
        test_configuration: The test configuration object

    Returns:
        Tuple of (test_set_name, endpoint_name, endpoint_url, project_name)
    """
    defaults = ("Unknown Test Set", "Unknown Endpoint", "N/A", "Unknown Project")

    if not test_configuration:
        return defaults

    test_set_name = defaults[0]
    endpoint_name = defaults[1]
    endpoint_url = defaults[2]
    project_name = defaults[3]

    # Get test set information
    if hasattr(test_configuration, "test_set") and test_configuration.test_set:
        test_set_name = test_configuration.test_set.name

    # Get endpoint information
    if hasattr(test_configuration, "endpoint") and test_configuration.endpoint:
        endpoint_name = test_configuration.endpoint.name
        endpoint_url = test_configuration.endpoint.url

        # Get project information
        if hasattr(test_configuration.endpoint, "project") and test_configuration.endpoint.project:
            project_name = test_configuration.endpoint.project.name

    return test_set_name, endpoint_name, endpoint_url, project_name


def calculate_execution_time(
    test_run: TestRun, completion_time: datetime, logger_func
) -> Optional[str]:
    """
    Calculate execution time for the test run.

    Args:
        test_run: The test run to calculate time for
        completion_time: The completion time to use
        logger_func: Logging function for debug messages

    Returns:
        Formatted execution time string or None
    """
    if not (test_run.attributes and isinstance(test_run.attributes, dict)):
        logger_func(
            "debug", f"No test run attributes available or not a dict: {test_run.attributes}"
        )
        return None

    # First try to get pre-calculated execution time
    total_time_ms = test_run.attributes.get("total_execution_time_ms")
    logger_func("debug", f"Found total_execution_time_ms in attributes: {total_time_ms}")

    if total_time_ms:
        execution_time = format_execution_time_from_ms(total_time_ms)
        logger_func(
            "debug", f"Formatted execution time from total_execution_time_ms: {execution_time}"
        )
        return execution_time

    # Calculate from started_at and current completion time
    started_at = test_run.attributes.get("started_at")
    logger_func(
        "debug",
        f"Found started_at: {started_at}, using completion_time: {completion_time.isoformat()}",
    )

    if not started_at:
        logger_func("debug", "No started_at timestamp found in test run attributes")
        return None

    try:
        # Parse start timestamp and use current completion time
        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))

        # Calculate duration in seconds
        duration_seconds = (completion_time - start_time).total_seconds()
        execution_time = format_execution_time(duration_seconds)
        logger_func(
            "debug",
            f"Calculated execution time from started_at to now: {execution_time} ({duration_seconds} seconds)",
        )
        return execution_time
    except Exception as e:
        logger_func("warning", "Failed to calculate execution time from timestamps", error=str(e))
        return None


def update_test_run_status(
    db,
    test_run: TestRun,
    overall_status: str,
    completion_time: datetime,
    execution_time: Optional[str],
    logger_func,
) -> None:
    """
    Update the test run with final status and completion information.

    Args:
        db: Database session
        test_run: The test run to update
        overall_status: The final status to set
        completion_time: The completion time
        execution_time: The calculated execution time
        logger_func: Logging function for debug messages
    """
    from rhesis.backend.app.utils.crud_utils import get_or_create_status

    # Log current status before update
    current_status_name = test_run.status.name if test_run.status else "None"
    logger_func(
        "info", f"Current test run status: {current_status_name}, updating to: {overall_status}"
    )

    new_status = get_or_create_status(db, overall_status, "TestRun")
    logger_func("debug", f"Got status object: {new_status.name} (id: {new_status.id})")

    # Update attributes to mark completion
    completion_time_iso = completion_time.isoformat()
    updated_attributes = test_run.attributes.copy() if test_run.attributes else {}
    updated_attributes.update(
        {
            "completed_at": completion_time_iso,
            "final_status": overall_status,
            "task_state": overall_status,
            "status": overall_status,
            "collect_results_completed": True,
            "updated_at": completion_time_iso,
        }
    )

    # Add total_execution_time_ms for future clients if we calculated it
    if execution_time and updated_attributes.get("started_at"):
        try:
            # Calculate duration in milliseconds from timestamps for storage
            start_time = datetime.fromisoformat(
                updated_attributes["started_at"].replace("Z", "+00:00")
            )
            duration_ms = int((completion_time - start_time).total_seconds() * 1000)
            updated_attributes["total_execution_time_ms"] = duration_ms
            logger_func("debug", f"Added total_execution_time_ms to attributes: {duration_ms}ms")
        except Exception as e:
            logger_func(
                "warning", "Failed to calculate total_execution_time_ms for storage", error=str(e)
            )

    # Update the test run
    update_data = {"status_id": new_status.id, "attributes": updated_attributes}

    logger_func("debug", f"Updating test run with status_id: {new_status.id}")
    updated_test_run = crud.update_test_run(
        db, test_run.id, crud.schemas.TestRunUpdate(**update_data)
    )

    # Verify the update worked
    if updated_test_run and updated_test_run.status:
        logger_func(
            "info", f"Test run status successfully updated to: {updated_test_run.status.name}"
        )
    else:
        logger_func("warning", "Test run status update may have failed - no status returned")

    # Commit the transaction explicitly
    db.commit()


def format_status_details(tests_passed: int, tests_failed: int) -> str:
    """
    Format status details for email display.

    Args:
        tests_passed: Number of passed tests
        tests_failed: Number of failed tests

    Returns:
        Formatted status details string
    """
    status_details = []
    if tests_passed > 0:
        status_details.append(f"{tests_passed} test{'s' if tests_passed != 1 else ''} passed")
    if tests_failed > 0:
        status_details.append(f"{tests_failed} test{'s' if tests_failed != 1 else ''} failed")

    return ", ".join(status_details) if status_details else "No tests executed"


def build_summary_data(
    test_run_id: str,
    email_status: str,
    total_tests: int,
    tests_passed: int,
    tests_failed: int,
    execution_time: Optional[str],
    test_set_name: str,
    endpoint_name: str,
    endpoint_url: str,
    project_name: str,
    completion_time: datetime,
) -> Dict[str, Any]:
    """
    Build the summary data dictionary to return from the task.

    Args:
        test_run_id: ID of the test run
        email_status: Status for email notifications
        total_tests: Total number of tests
        tests_passed: Number of passed tests
        tests_failed: Number of failed tests
        execution_time: Formatted execution time
        test_set_name: Name of the test set
        endpoint_name: Name of the endpoint
        endpoint_url: URL of the endpoint
        project_name: Name of the project
        completion_time: Completion timestamp

    Returns:
        Dictionary containing test execution summary
    """
    return {
        "test_run_id": test_run_id,
        "status": email_status,
        "total_tests": total_tests,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "execution_time": execution_time,
        "status_details": format_status_details(tests_passed, tests_failed),
        "test_set_name": test_set_name,
        "endpoint_name": endpoint_name,
        "endpoint_url": endpoint_url,
        "project_name": project_name,
        "completed_at": completion_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


class TestRunProcessor:
    """
    A processor class for handling test run result collection and analysis.

    This class encapsulates all the logic for processing test execution results,
    making it easier to test and reuse across different contexts.
    """

    def __init__(self, logger_func):
        """
        Initialize the processor with a logging function.

        Args:
            logger_func: Function to use for logging (e.g., self.log_with_context)
        """
        self.logger_func = logger_func

    def process_test_run_results(
        self, db, test_run: TestRun, test_run_id: str, completion_time: datetime
    ) -> Dict[str, Any]:
        """
        Process all aspects of test run result collection.

        Args:
            db: Database session
            test_run: The test run to process
            test_run_id: ID of the test run
            completion_time: When the processing completed

        Returns:
            Dictionary containing test execution summary
        """
        # Calculate test statistics
        total_tests, tests_passed, tests_failed = get_test_statistics(test_run)
        self.logger_func(
            "debug",
            f"Test statistics: total={total_tests}, passed={tests_passed}, failed={tests_failed}",
        )

        # Determine overall status
        overall_status, email_status = determine_overall_status(
            tests_passed, tests_failed, total_tests, self.logger_func
        )
        self.logger_func("info", f"Determined status: {overall_status} (email: {email_status})")

        # Get test context information
        test_configuration = test_run.test_configuration
        test_set_name, endpoint_name, endpoint_url, project_name = get_test_context(
            test_configuration
        )

        # Calculate execution time
        execution_time = calculate_execution_time(test_run, completion_time, self.logger_func)

        # Update test run status and attributes
        update_test_run_status(
            db, test_run, overall_status, completion_time, execution_time, self.logger_func
        )

        # Build and return summary data
        return build_summary_data(
            test_run_id,
            email_status,
            total_tests,
            tests_passed,
            tests_failed,
            execution_time,
            test_set_name,
            endpoint_name,
            endpoint_url,
            project_name,
            completion_time,
        )
