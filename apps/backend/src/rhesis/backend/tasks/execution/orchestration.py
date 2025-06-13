from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID

from celery import chord, group
from celery.result import GroupResult
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.services.test_set import get_test_set
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.results import collect_results
from rhesis.backend.tasks.execution.test import execute_single_test


def execute_test_cases(
    session: Session, test_config: TestConfiguration, test_run: TestRun
) -> Dict[str, Any]:
    """Execute test cases in parallel using Celery workers with Redis native chord support."""
    # Using the service helper because it loads tests properly
    test_set = get_test_set(session, str(test_config.test_set_id))
    start_time = datetime.utcnow()

    # Retrieve all tests from the test set
    tests = test_set.tests
    
    if not tests:
        logger.warning(f"No tests found in test set {test_set.id}")
        return {
            "test_run_id": str(test_run.id),
            "test_configuration_id": str(test_config.id),
            "test_set_id": str(test_config.test_set_id),
            "total_tests": 0,
        }

    # Create tasks for parallel execution
    tasks = []
    for test in tests:
        # Pass organization_id and user_id to ensure proper tenant context
        task = execute_single_test.s(
            test_config_id=str(test_config.id),
            test_run_id=str(test_run.id),
            test_id=str(test.id),
            endpoint_id=str(test_config.endpoint_id),
            organization_id=str(test_config.organization_id) if test_config.organization_id else None,
            user_id=str(test_config.user_id) if test_config.user_id else None,
        )
        # Note: Using default queue routing
        tasks.append(task)

    # Create the callback task with correct signature for Redis chord
    callback = collect_results.s(
        start_time.isoformat(),
        str(test_config.id),
        str(test_run.id),
        str(test_config.test_set_id),
        len(tasks),
        organization_id=str(test_config.organization_id) if test_config.organization_id else None,
        user_id=str(test_config.user_id) if test_config.user_id else None,
    )

    # Note: Using default queue routing

    # Execute the chord
    logger.info(f"Starting chord execution for test run {test_run.id} with {len(tasks)} tasks")
    job = chord(tasks, callback).apply_async()
    
    logger.info(f"Chord job created successfully with ID: {job.id}")
    if hasattr(job, 'parent'):
        logger.info(f"Group ID: {job.parent.id if job.parent else 'None'}")
    
    # Update test run attributes to track chord execution
    updated_attributes = test_run.attributes.copy()
    updated_attributes.update({
        "chord_id": job.id,
        "chord_parent_id": job.parent.id if job.parent else None,
        "execution_mode": "redis_chord",
        "started_at": start_time.isoformat(),
        "total_tests": len(tasks),
        "callback_task": callback.task,
        "callback_queue": callback.options.get('queue', 'default'),
        "updated_at": datetime.utcnow().isoformat()
    })
    
    # Update test run with chord information
    update_data = {
        "attributes": updated_attributes
    }
    crud.update_test_run(session, test_run.id, crud.schemas.TestRunUpdate(**update_data))
    
    logger.info(f"Chord execution initiated for test run {test_run.id}")
    
    return {
        "test_run_id": str(test_run.id),
        "test_configuration_id": str(test_config.id),
        "test_set_id": str(test_config.test_set_id),
        "total_tests": len(tasks),
        "chord_id": job.id,
        "chord_parent_id": job.parent.id if job.parent else None,
        "execution_mode": "redis_chord"
    } 