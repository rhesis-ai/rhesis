from typing import Optional
from uuid import UUID

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.base import BaseTask, with_tenant_context
from rhesis.backend.tasks.execution.metrics_utils import get_behavior_metrics
from rhesis.backend.tasks.execution.test_execution import execute_test
from rhesis.backend.worker import app


@app.task(name="rhesis.backend.tasks.execute_single_test", base=BaseTask, bind=True)
@with_tenant_context
def execute_single_test(
    self,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    endpoint_id: str,
    organization_id: str = None,  # Make this explicit so it's preserved on retries
    user_id: str = None,          # Make this explicit so it's preserved on retries
    db=None,
):
    """
    Execute a single test and return its results.
    
    This task uses the with_tenant_context decorator to automatically
    handle database sessions with the proper tenant context.
    """
    # Access context from task request - task headers take precedence over kwargs
    task = self.request
    request_user_id = getattr(task, 'user_id', None)
    request_org_id = getattr(task, 'organization_id', None)
    
    # Use passed parameters if available, otherwise use request context
    # This ensures context is preserved during retries
    user_id = user_id or request_user_id
    organization_id = organization_id or request_org_id
    
    logger.debug(f"Executing test {test_id} with user_id={user_id}, organization_id={organization_id}")
    
    try:
        # Call the main execution function from the dedicated module
        return execute_test(
            db=db,
            test_config_id=test_config_id,
            test_run_id=test_run_id,
            test_id=test_id,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id
        )

    except Exception as e:
        logger.error(f"Error executing test {test_id}: {str(e)}", exc_info=True)
        db.rollback()
        # Pass explicit organization_id and user_id on retry to ensure context is preserved
        if self.request.retries < self.max_retries:
            # Use explicit raise with retry=True to preserve context
            self.retry(
                exc=e, 
                kwargs={
                    "test_config_id": test_config_id,
                    "test_run_id": test_run_id,
                    "test_id": test_id,
                    "endpoint_id": endpoint_id,
                    "organization_id": organization_id,
                    "user_id": user_id
                }
            )
        raise 