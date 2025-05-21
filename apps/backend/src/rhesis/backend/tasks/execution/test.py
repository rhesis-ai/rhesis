from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_result import TestResult
from rhesis.backend.app.services.endpoint import invoke
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.app.database import set_tenant
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.base import BaseTask, with_tenant_context
from rhesis.backend.tasks.enums import ResultStatus
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
        # Explicitly set tenant context to ensure it's active for all queries
        if organization_id:
            # Verify PostgreSQL has the parameter defined
            try:
                db.execute(text('SHOW "app.current_organization"'))
            except Exception as e:
                logger.warning(f"The database parameter 'app.current_organization' may not be defined: {e}")
                # Continue without setting tenant context - will use normal filters instead
            
            # Set the tenant context for this session
            set_tenant(db, organization_id, user_id)
            
            # Verify tenant context is set
            logger.debug(f"Set tenant context for task: organization_id={organization_id}, user_id={user_id}")

        # Initialize metrics evaluator outside of database operations
        metrics_evaluator = MetricEvaluator()
        start_time = datetime.utcnow()

        # Get the test being executed
        test = crud.get_test(db, UUID(test_id))
        if not test:
            # Fallback to direct query with filter if crud method fails due to tenant context
            test_query = db.query(Test).filter(Test.id == UUID(test_id))
            if organization_id and isinstance(organization_id, str):
                test_query = test_query.filter(Test.organization_id == UUID(organization_id))
            test = test_query.first()
            
            if not test:
                raise ValueError(f"Test with ID {test_id} not found")
        
        # Get the prompt associated with the test
        prompt = test.prompt
        if not prompt:
            raise ValueError(f"Test {test_id} has no associated prompt")
        
        prompt_content = prompt.content
        expected_response = prompt.expected_response or ""

        # Check if result already exists for this combination
        filter_str = f"test_configuration_id eq {test_config_id} and test_run_id eq {test_run_id} and test_id eq {test_id}"
        existing_results = crud.get_test_results(db, limit=1, filter=filter_str)
        existing_result = existing_results[0] if existing_results else None

        if existing_result:
            # Return existing result data without creating duplicate
            return {
                "test_id": test_id,
                "execution_time": existing_result.test_metrics.get("execution_time"),
                "metrics": existing_result.test_metrics.get("metrics", {}),
            }

        # Get required statuses
        test_result_status = get_or_create_status(db, ResultStatus.PASS.value, "TestResult")

        logger.info(f"Starting execute task for test: {test_id}")

        # Execute prompt against endpoint
        input_data = {"input": prompt_content}
        result = invoke(db=db, endpoint_id=endpoint_id, input_data=input_data)

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Get context from result
        context = result.get("context", []) if result else []

        # Import evaluation function from evaluation module
        from rhesis.backend.tasks.execution.evaluation import evaluate_prompt_response

        # Evaluate metrics - this is CPU-bound work, not DB-bound
        metrics_results = evaluate_prompt_response(
            metrics_evaluator=metrics_evaluator,
            prompt_content=prompt_content,
            expected_response=expected_response,
            context=context,
            result=result,
        )

        # Create test result with CRUD operation
        test_result_data = {
            "test_configuration_id": UUID(test_config_id),
            "test_run_id": UUID(test_run_id),
            "test_id": UUID(test_id),
            "prompt_id": test.prompt_id,
            "status_id": test_result_status.id,
            "user_id": UUID(user_id) if user_id else None,
            "organization_id": UUID(organization_id) if organization_id else None,
            "test_metrics": {"execution_time": execution_time, "metrics": metrics_results},
            "test_output": result,
        }
        
        crud.create_test_result(db, schemas.TestResultCreate(**test_result_data))

        logger.debug(f"Test execution completed successfully for test_id={test_id}")
        return {
            "test_id": test_id,
            "execution_time": execution_time,
            "metrics": metrics_results,
        }

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