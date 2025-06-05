from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID

from celery import chord, group
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.services.test_set import get_test_set
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.results import collect_results
from rhesis.backend.tasks.execution.test import execute_single_test
from rhesis.backend.tasks.execution.db_chord_coordinator import coordinate_database_chord


def execute_test_cases(
    session: Session, test_config: TestConfiguration, test_run: TestRun
) -> Dict[str, Any]:
    """Execute test cases in parallel using Celery workers with database-specific chord coordination."""
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
        tasks.append(task)

    # Prepare callback information for database chord coordinator
    callback_info = {
        'args': [
            datetime.utcnow().isoformat(),
            str(test_config.id),
            str(test_run.id),
            str(test_config.test_set_id),
            len(tasks),
        ],
        'kwargs': {
            'organization_id': str(test_config.organization_id) if test_config.organization_id else None,
            'user_id': str(test_config.user_id) if test_config.user_id else None,
        }
    }

    # Try database backend compatible approach first
    try:
        logger.info(f"Starting database chord coordination for test run {test_run.id} with {len(tasks)} tasks")
        
        # Execute tasks as a group (without callback)
        group_job = group(tasks)
        group_result = group_job.apply_async()
        
        # Get the group ID and individual task IDs
        group_id = group_result.id
        task_ids = [result.id for result in group_result.results]
        
        logger.info(f"Started group execution for test run {test_run.id}")
        logger.info(f"Group ID: {group_id}")
        logger.debug(f"Task IDs: {task_ids}")
        
        # Start database chord coordinator to monitor completion and execute callback
        coordinator_task = coordinate_database_chord.delay(
            group_id=group_id,
            task_ids=task_ids,
            callback_info=callback_info
        )
        
        logger.info(f"Started database chord coordinator: {coordinator_task.id}")
        
        return {
            "test_run_id": str(test_run.id),
            "test_configuration_id": str(test_config.id),
            "test_set_id": str(test_config.test_set_id),
            "total_tests": len(tasks),
            "group_id": group_id,
            "coordinator_task_id": coordinator_task.id,
            "coordination_mode": "database_backend"
        }
        
    except Exception as e:
        logger.error(f"Failed to start database chord coordination: {str(e)}", exc_info=True)
        
        # Fallback: Try traditional Celery chord (might work in some database configurations)
        try:
            logger.warning("Falling back to traditional Celery chord")
            
            callback = collect_results.s(
                datetime.utcnow().isoformat(),
                str(test_config.id),
                str(test_run.id),
                str(test_config.test_set_id),
                len(tasks),
                organization_id=str(test_config.organization_id) if test_config.organization_id else None,
                user_id=str(test_config.user_id) if test_config.user_id else None,
            )
            
            # Create traditional chord
            job = chord(tasks, body=callback)
            result = job.apply_async()
            
            logger.info(f"Started fallback chord execution for test run {test_run.id}")
            logger.info(f"Chord job ID: {result.id if hasattr(result, 'id') else 'unknown'}")
            
            if hasattr(result, 'parent') and result.parent:
                logger.debug(f"Chord parent group ID: {result.parent}")
            
            return {
                "test_run_id": str(test_run.id),
                "test_configuration_id": str(test_config.id),
                "test_set_id": str(test_config.test_set_id),
                "total_tests": len(tasks),
                "coordination_mode": "traditional_chord"
            }
            
        except Exception as chord_error:
            logger.error(f"Traditional chord also failed: {str(chord_error)}")
            
            # Final fallback: Execute callback directly with empty results
            try:
                logger.warning("Executing final fallback: direct callback with empty results")
                
                # Update test run to indicate failure mode
                from rhesis.backend.app.utils.crud_utils import get_or_create_status
                from rhesis.backend.tasks.enums import RunStatus
                
                fallback_status = get_or_create_status(session, RunStatus.IN_PROGRESS.value, "TestRun")
                error_attributes = test_run.attributes.copy()
                error_attributes.update({
                    "error": f"All chord execution methods failed: {str(e)}, {str(chord_error)}",
                    "fallback_mode": True,
                    "updated_at": datetime.utcnow().isoformat()
                })
                
                update_data = {
                    "status_id": fallback_status.id,
                    "attributes": error_attributes
                }
                
                crud.update_test_run(session, test_run.id, crud.schemas.TestRunUpdate(**update_data))
                
                # Execute callback directly with empty results
                collect_results.delay(
                    [],  # Empty results to indicate failure
                    datetime.utcnow().isoformat(),
                    str(test_config.id),
                    str(test_run.id),
                    str(test_config.test_set_id),
                    len(tasks),
                    organization_id=str(test_config.organization_id) if test_config.organization_id else None,
                    user_id=str(test_config.user_id) if test_config.user_id else None,
                )
                
                return {
                    "test_run_id": str(test_run.id),
                    "test_configuration_id": str(test_config.id),
                    "test_set_id": str(test_config.test_set_id),
                    "total_tests": len(tasks),
                    "coordination_mode": "direct_fallback",
                    "error": "Chord execution failed, using direct callback"
                }
                
            except Exception as fallback_error:
                logger.error(f"Final fallback execution also failed: {str(fallback_error)}")
                raise

    return {
        "test_run_id": str(test_run.id),
        "test_configuration_id": str(test_config.id),
        "test_set_id": str(test_config.test_set_id),
        "total_tests": len(tasks),
    } 