from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.stats import get_individual_test_stats, get_test_stats
from rhesis.backend.app.services.test import bulk_create_tests
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema
from rhesis.backend.logging.rhesis_logger import logger

# Create the detailed schema for Test
TestDetailSchema = create_detailed_schema(schemas.Test, models.Test)

router = APIRouter(prefix="/tests", tags=["tests"], responses={404: {"description": "Not found"}})


@router.post("/", response_model=schemas.Test)
@handle_database_exceptions(
    entity_name="test", custom_unique_message="Test with this name already exists"
)
def create_test(
    test: schemas.TestCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create test with super optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_test(db=db, test=test, organization_id=organization_id, user_id=user_id)


@router.post("/bulk", response_model=schemas.TestBulkCreateResponse)
def create_tests_bulk(
    test_data: schemas.TestBulkCreateRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create multiple tests in a single operation.

    The input format should be:
    {
        "tests": [
            {
                "prompt": {
                    "content": "Prompt text",
                    "language_code": "en",
                    "demographic": "Optional demographic",
                    "dimension": "Optional dimension",
                    "expected_response": "Optional expected response"
                },
                "behavior": "Behavior name",
                "category": "Category name",
                "topic": "Topic name",
                "test_configuration": {},  # Optional test configuration
                "assignee_id": "uuid",  # Optional assignee ID
                "owner_id": "uuid",  # Optional owner ID
                "status": "string",    # Optional status name
                "priority": "number"   # Optional priority value
            }
        ],
        "test_set_id": "optional-uuid"  # Optional test set ID to associate tests with
    }

    Returns:
        200: Tests created successfully
        400: Invalid request format or validation error
        404: Referenced entity not found
        500: Server error during processing
    """
    try:
        if not test_data.tests:
            raise HTTPException(status_code=400, detail="No tests provided in request")

        tests = bulk_create_tests(
            db=db,
            tests_data=test_data.tests,
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
            test_set_id=str(test_data.test_set_id) if test_data.test_set_id else None,
        )

        return schemas.TestBulkCreateResponse(
            success=True, total_tests=len(tests), message=f"Successfully created {len(tests)} tests"
        )
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        # Handle missing required fields
        raise HTTPException(status_code=400, detail=f"Missing required field: {str(e)}")
    except IntegrityError:
        # Handle database integrity errors (e.g., duplicate unique values)
        raise HTTPException(
            status_code=409,
            detail="Database integrity error: A record with the same unique values already exists",
        )
    except Exception as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            # Handle cases where referenced entities (e.g., test set) are not found
            raise HTTPException(status_code=404, detail=error_message)
        else:
            # Handle unexpected server errors
            raise HTTPException(
                status_code=500, detail=f"An error occurred while creating tests: {error_message}"
            )


@router.get("/stats", response_model=schemas.EntityStats)
def generate_test_stats(
    top: Optional[int] = None,
    months: Optional[int] = 6,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get statistics about tests"""
    return get_test_stats(db, current_user.organization_id, top, months)


@router.get("/", response_model=List[TestDetailSchema])
@with_count_header(model=models.Test)
def read_tests(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all tests with their related objects"""
    organization_id, user_id = tenant_context
    tests = crud.get_tests(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    return tests


@router.get("/{test_id}/stats")
def get_individual_test_statistics(
    test_id: UUID,
    recent_runs_limit: Optional[int] = Query(
        5, description="Number of recent test runs to include"
    ),
    months: Optional[int] = Query(None, description="Filter to last N months of data"),
    start_date: Optional[str] = Query(
        None, description="Start date (ISO format, overrides months)"
    ),
    end_date: Optional[str] = Query(None, description="End date (ISO format, overrides months)"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get comprehensive statistics for a specific test across all its test runs.

    Provides:
    - Overall pass/fail statistics
    - Per-metric breakdown of success rates
    - Recent test run details with per-metric results
    - Average execution time

    Query Parameters:
    - recent_runs_limit: Number of recent test runs to include (default: 5)
    - months: Filter to last N months of data (optional)
    - start_date: Custom start date in ISO format (optional, overrides months)
    - end_date: Custom end date in ISO format (optional, overrides months)

    Example usage:
    - GET /tests/{test_id}/stats
    - GET /tests/{test_id}/stats?recent_runs_limit=10
    - GET /tests/{test_id}/stats?months=3
    - GET /tests/{test_id}/stats?start_date=2024-01-01&end_date=2024-12-31
    """
    organization_id, user_id = tenant_context

    # First verify the test exists and belongs to the organization
    db_test = crud.get_test(db, test_id=test_id, organization_id=organization_id, user_id=user_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    return get_individual_test_stats(
        db=db,
        test_id=str(test_id),
        organization_id=organization_id,
        recent_runs_limit=recent_runs_limit,
        months=months,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{test_id}", response_model=TestDetailSchema)
def read_test(
    test_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test by ID with its related objects"""
    organization_id, user_id = tenant_context
    db_test = crud.get_test_detail(
        db, test_id=test_id, organization_id=organization_id, user_id=user_id
    )
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return db_test


@router.put("/{test_id}", response_model=schemas.Test)
def update_test(
    test_id: UUID,
    test: schemas.TestUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update test with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_test = crud.get_test(db, test_id=test_id, organization_id=organization_id, user_id=user_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    # Check if the user has permission to update this test
    if db_test.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this test")

    return crud.update_test(
        db=db, test_id=test_id, test=test, organization_id=organization_id, user_id=user_id
    )


@router.delete("/{test_id}", response_model=schemas.Test)
def delete_test(
    test_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test"""
    organization_id, user_id = tenant_context
    db_test = crud.get_test(db, test_id=test_id, organization_id=organization_id, user_id=user_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    # Check if the user has permission to delete this test
    if db_test.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete this test")

    return crud.delete_test(
        db=db, test_id=test_id, organization_id=organization_id, user_id=user_id
    )


@router.post("/execute", response_model=schemas.TestExecuteResponse)
async def execute_test_endpoint(
    request: schemas.TestExecuteRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Execute a test in-place without worker infrastructure or database persistence.

    This endpoint enables synchronous test execution for development, testing, or
    lightweight scenarios. Results are returned immediately without creating TestRun
    or TestResult database records.

    **Two execution modes:**

    1. **Existing test**: Provide `test_id` to execute an existing test
    2. **Inline test**: Provide complete test definition:
       - For single-turn: `prompt` + `behavior` + `topic` + `category`
       - For multi-turn: `test_configuration` (with goal) + `behavior` + `topic` + `category`

    **Parameters:**
    - `test_id`: Optional UUID of existing test
    - `endpoint_id`: Required UUID of endpoint to execute against
    - `evaluate_metrics`: Whether to evaluate and return test_metrics (default: True)
    - `prompt`: For single-turn tests (if test_id not provided)
    - `test_configuration`: For multi-turn tests (if test_id not provided)
    - `behavior`, `topic`, `category`: Required if test_id not provided
    - `test_type`: Optional, auto-detected if not provided

    **Returns:**
    - `test_id`: Test identifier
    - `prompt_id`: Prompt identifier (single-turn only)
    - `execution_time`: Execution time in milliseconds
    - `test_output`: Raw endpoint output (always returned)
    - `test_metrics`: Evaluated metrics (only if evaluate_metrics=True)
    - `status`: Pass/Fail/Error/Pending status
    - `test_configuration`: Test configuration (multi-turn only)

    **Example requests:**

    ```json
    // Execute existing test
    {
      "test_id": "uuid-here",
      "endpoint_id": "uuid-here",
      "evaluate_metrics": true
    }

    // Execute inline single-turn test
    {
      "endpoint_id": "uuid-here",
      "evaluate_metrics": true,
      "prompt": {
        "content": "What is 2+2?",
        "language_code": "en",
        "expected_response": "4"
      },
      "behavior": "Mathematical Reasoning",
      "topic": "Arithmetic",
      "category": "Math"
    }

    // Execute inline multi-turn test
    {
      "endpoint_id": "uuid-here",
      "evaluate_metrics": true,
      "test_configuration": {
        "goal": "Book a flight to Paris",
        "max_turns": 10
      },
      "behavior": "Task Completion",
      "topic": "Travel",
      "category": "Booking"
    }
    ```

    **Errors:**
    - 400: Invalid request (missing required fields, validation errors)
    - 404: Test or endpoint not found
    - 500: Execution error
    """
    organization_id, user_id = tenant_context

    try:
        # Validate endpoint exists
        db_endpoint = crud.get_endpoint(
            db,
            endpoint_id=request.endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if not db_endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found")

        # Validate request data based on Pydantic model (already validated)
        # The schema's model_post_init handles validation of required fields

        # Convert request to dict for service
        request_data = request.model_dump(mode="json")

        # Execute test in-place
        from rhesis.backend.app.services.test_execution import execute_test_in_place

        result = await execute_test_in_place(
            db=db,
            request_data=request_data,
            endpoint_id=str(request.endpoint_id),
            organization_id=organization_id,
            user_id=user_id,
            evaluate_metrics=request.evaluate_metrics,
        )

        return result

    except ValueError as e:
        # Handle validation and not-found errors
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)

    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Test execution failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")
