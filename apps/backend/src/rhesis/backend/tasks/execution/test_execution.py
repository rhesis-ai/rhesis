"""
Core test execution logic for running tests against endpoints and evaluating them.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.app.services.endpoint import EndpointService
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.app.database import set_tenant
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.metrics.base import MetricConfig
from rhesis.backend.metrics.config import load_default_metrics
from rhesis.backend.tasks.enums import ResultStatus
from rhesis.backend.tasks.execution.metrics_utils import create_metric_config_from_model


def setup_tenant_context(db: Session, organization_id: Optional[str], user_id: Optional[str]) -> None:
    """
    Set up tenant context for database operations if organization_id is provided.
    
    Args:
        db: Database session
        organization_id: UUID string of the organization (optional)
        user_id: UUID string of the user (optional)
    """
    if not organization_id:
        return
        
    # Verify PostgreSQL has the parameter defined
    try:
        db.execute(text('SHOW "app.current_organization"'))
    except Exception as e:
        logger.warning(f"The database parameter 'app.current_organization' may not be defined: {e}")
        # Continue without setting tenant context - will use normal filters instead
        return
    
    # Set the tenant context for this session
    set_tenant(db, organization_id, user_id)
    
    # Verify tenant context is set
    logger.debug(f"Set tenant context: organization_id={organization_id}, user_id={user_id}")


def get_test_and_prompt(db: Session, test_id: str, organization_id: Optional[str] = None) -> tuple:
    """
    Get test and its associated prompt.
    
    Args:
        db: Database session
        test_id: UUID string of the test
        organization_id: UUID string of the organization (optional)
    
    Returns:
        Tuple of (test, prompt_content, expected_response)
        
    Raises:
        ValueError: If test or prompt is not found
    """
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
    
    return test, prompt_content, expected_response


def get_test_metrics(test) -> List[Dict]:
    """
    Get metrics for a test from its associated behavior.
    
    Args:
        test: Test model instance
    
    Returns:
        List of metric configuration dictionaries (excluding invalid/None metrics)
    """
    metrics = []
    behavior = test.behavior
    
    if behavior and behavior.metrics:
        # Access metrics directly from behavior.metrics relationship
        # Filter out None values returned by create_metric_config_from_model
        raw_metrics = [create_metric_config_from_model(metric) for metric in behavior.metrics]
        metrics = [metric for metric in raw_metrics if metric is not None]
        
        # Log if any metrics were invalid
        invalid_count = len(raw_metrics) - len(metrics)
        if invalid_count > 0:
            logger.warning(f"Filtered out {invalid_count} invalid metrics for test {test.id}")
    
    if not metrics:
        logger.warning(f"No valid metrics found for test {test.id}, using defaults")
        # Load default metrics from configuration file
        metrics = load_default_metrics()
    
    return metrics


def check_existing_result(
    db: Session, 
    test_config_id: str, 
    test_run_id: str, 
    test_id: str
) -> Optional[Dict[str, Any]]:
    """
    Check if a result already exists for the test configuration.
    
    Args:
        db: Database session
        test_config_id: UUID string of the test configuration
        test_run_id: UUID string of the test run
        test_id: UUID string of the test
        
    Returns:
        Result dict if exists, None otherwise
    """
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
    
    return None


def execute_test(
    db: Session,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    endpoint_id: str,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a single test and return its results.
    
    Args:
        db: Database session
        test_config_id: UUID string of the test configuration
        test_run_id: UUID string of the test run
        test_id: UUID string of the test
        endpoint_id: UUID string of the endpoint
        organization_id: UUID string of the organization (optional)
        user_id: UUID string of the user (optional)
        
    Returns:
        Dictionary with test execution results
        
    Raises:
        ValueError: If test or prompt is not found
    """
    logger.info(f"🔍 DEBUG: execute_test starting for test {test_id}")
    logger.debug(f"🔍 DEBUG: execute_test params - config_id={test_config_id}, run_id={test_run_id}, endpoint_id={endpoint_id}")
    logger.debug(f"🔍 DEBUG: execute_test context - org_id={organization_id}, user_id={user_id}")
    
    try:
        # Set up tenant context if needed
        logger.debug(f"🔍 DEBUG: Setting up tenant context for test {test_id}")
        setup_tenant_context(db, organization_id, user_id)
        
        # Initialize services and evaluators
        logger.debug(f"🔍 DEBUG: Initializing services for test {test_id}")
        endpoint_service = get_endpoint_service()
        metrics_evaluator = MetricEvaluator()
        start_time = datetime.utcnow()
        
        # Check for existing result
        logger.debug(f"🔍 DEBUG: Checking for existing result for test {test_id}")
        existing_result = check_existing_result(db, test_config_id, test_run_id, test_id)
        if existing_result:
            logger.info(f"✅ DEBUG: Found existing result for test {test_id}, returning it")
            return existing_result
        
        # Get test and prompt
        logger.debug(f"🔍 DEBUG: Getting test and prompt for test {test_id}")
        test, prompt_content, expected_response = get_test_and_prompt(db, test_id, organization_id)
        logger.debug(f"🔍 DEBUG: Got test and prompt for test {test_id} - prompt length: {len(prompt_content) if prompt_content else 0}")
        
        # Get metrics for the test
        logger.debug(f"🔍 DEBUG: Getting metrics for test {test_id}")
        metrics = get_test_metrics(test)
        logger.debug(f"🔍 DEBUG: Got {len(metrics)} metrics for test {test_id}")
        
        # Convert metrics to MetricConfig objects, filtering out None/invalid ones
        metric_configs = []
        invalid_metrics_count = 0
        
        logger.debug(f"🔍 DEBUG: Converting metrics to configs for test {test_id}")
        for i, metric in enumerate(metrics):
            try:
                config = MetricConfig.from_dict(metric)
                if config is not None:
                    metric_configs.append(config)
                else:
                    invalid_metrics_count += 1
                    logger.warning(f"Skipped invalid metric {i} for test {test_id}: missing required fields")
            except Exception as e:
                invalid_metrics_count += 1
                logger.warning(f"Failed to parse metric {i} for test {test_id}: {str(e)}")
        
        if invalid_metrics_count > 0:
            logger.warning(f"Skipped {invalid_metrics_count} invalid metrics for test {test_id}")
        
        logger.debug(f"🔍 DEBUG: Using {len(metric_configs)} valid metrics for test {test_id}")
        
        # If no valid metrics found, log a warning but continue execution
        if not metric_configs:
            logger.warning(f"No valid metrics found for test {test_id}, proceeding without metric evaluation")
        
        # Get required statuses
        logger.debug(f"🔍 DEBUG: Getting test result status for test {test_id}")
        test_result_status = get_or_create_status(db, ResultStatus.PASS.value, "TestResult")

        logger.info(f"🔍 DEBUG: Starting endpoint invocation for test {test_id}")

        # Execute prompt against endpoint
        input_data = {"input": prompt_content}
        logger.debug(f"🔍 DEBUG: Invoking endpoint {endpoint_id} for test {test_id}")
        result = endpoint_service.invoke_endpoint(db=db, endpoint_id=endpoint_id, input_data=input_data)
        logger.debug(f"🔍 DEBUG: Endpoint invocation completed for test {test_id}, result type: {type(result)}")

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.debug(f"🔍 DEBUG: Execution time for test {test_id}: {execution_time}ms")

        # Get context from result
        context = result.get("context", []) if result else []
        logger.debug(f"🔍 DEBUG: Got context for test {test_id}, length: {len(context)}")

        # Import evaluation function from evaluation module
        from rhesis.backend.tasks.execution.evaluation import evaluate_prompt_response

        # Evaluate metrics
        logger.debug(f"🔍 DEBUG: Evaluating metrics for test {test_id}")
        metrics_results = evaluate_prompt_response(
            metrics_evaluator=metrics_evaluator,
            prompt_content=prompt_content,
            expected_response=expected_response,
            context=context,
            result=result,
            metrics=metric_configs,
        )
        logger.debug(f"🔍 DEBUG: Metrics evaluation completed for test {test_id}")

        # Create test result with CRUD operation
        logger.debug(f"🔍 DEBUG: Creating test result record for test {test_id}")
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
        
        logger.debug(f"🔍 DEBUG: Calling crud.create_test_result for test {test_id}")
        crud.create_test_result(db, schemas.TestResultCreate(**test_result_data))
        logger.debug(f"🔍 DEBUG: Test result created successfully for test {test_id}")

        # Prepare return value
        return_value = {
            "test_id": test_id,
            "execution_time": execution_time,
            "metrics": metrics_results,
        }
        
        logger.info(f"✅ DEBUG: execute_test completed successfully for test {test_id}")
        logger.debug(f"✅ DEBUG: Returning result for test {test_id}: {return_value}")
        return return_value
        
    except Exception as e:
        logger.error(f"🚨 DEBUG: Exception in execute_test for test {test_id}: {str(e)}", exc_info=True)
        logger.error(f"🚨 DEBUG: Exception type: {type(e).__name__}")
        logger.error(f"🚨 DEBUG: Exception args: {e.args}")
        
        # Re-raise the exception so it's handled by execute_single_test
        raise 