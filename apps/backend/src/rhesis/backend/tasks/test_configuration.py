"""
This module contains the main entry point for test configuration execution,
with detailed implementation in the execution/ directory modules.
"""

from uuid import UUID

from rhesis.backend.app import crud
from rhesis.backend.app.models import TestRun
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.base import BaseTask, with_tenant_context
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.worker import app

# Import functionality from execution modules
from rhesis.backend.tasks.execution.config import (
    TestConfigurationError,
    get_test_configuration
)
from rhesis.backend.tasks.execution.run import (
    TestExecutionError,
    create_test_run,
    update_test_run_status
)
from rhesis.backend.tasks.execution.test import (
    execute_single_test
)
from rhesis.backend.tasks.execution.orchestration import (
    execute_test_cases
)
from rhesis.backend.tasks.execution.results import (
    collect_results
)
from rhesis.backend.tasks.execution.evaluation import (
    evaluate_prompt_response
)

# Re-export all the public APIs for backward compatibility
__all__ = [
    'TestConfigurationError',
    'TestExecutionError',
    'get_test_configuration',
    'create_test_run',
    'execute_single_test',
    'execute_test_cases',
    'collect_results',
    'evaluate_prompt_response',
    'update_test_run_status',
    'execute_test_configuration',
]


@app.task(base=BaseTask, name="rhesis.backend.tasks.execute_test_configuration", bind=True)
@with_tenant_context
def execute_test_configuration(self, test_configuration_id: str, db=None):
    """
    Execute a test configuration by running all associated test cases.
    
    This task uses the with_tenant_context decorator to automatically
    handle database sessions with the proper tenant context.
    """
    logger.info(f"Starting test configuration execution: {test_configuration_id}")
    
    # Access context from task request
    task = self.request
    user_id = getattr(task, 'user_id', None)
    organization_id = getattr(task, 'organization_id', None)
    retries = getattr(task, 'retries', 0)
    
    logger.debug(f"Task context: user_id={user_id}, organization_id={organization_id}, retries={retries}")
    
    try:
        # Get test configuration with tenant context
        test_config = get_test_configuration(db, test_configuration_id)
        
        # Create test run with proper tracking
        test_run = create_test_run(
            db,
            test_config,
            {"id": self.request.id}
        )
        
        # Execute test cases in parallel
        result = execute_test_cases(db, test_config, test_run)
        
        # Include task info in the result
        result["task_id"] = self.request.id
        
        return result
        
    except Exception as e:
        logger.error(f"Error executing test configuration {test_configuration_id}: {str(e)}", 
                    exc_info=True)
        
        # Attempt to update test run status to failed if possible
        try:
            # Get the most recent test run for this configuration using crud
            test_runs = crud.get_test_runs(
                db, 
                limit=1, 
                filter=f"test_configuration_id eq {test_configuration_id}",
                sort_by="created_at",
                sort_order="desc"
            )
            
            test_run = test_runs[0] if test_runs else None
            
            if test_run:
                update_test_run_status(db, test_run, RunStatus.FAILED.value, str(e))
        except Exception as update_error:
            logger.error(f"Failed to update test run status: {str(update_error)}")
        
        # Check if we've exceeded max_retries (from BaseTask)
        if retries >= self.max_retries:
            logger.warning(f"Maximum retries ({self.max_retries}) reached for task {self.request.id}. Giving up.")
            # Raise a specific error that should not trigger retry
            raise TestExecutionError(f"Failed after {self.max_retries} retries: {str(e)}")
        
        # Re-raise the original error to trigger retry behavior from BaseTask
        raise
