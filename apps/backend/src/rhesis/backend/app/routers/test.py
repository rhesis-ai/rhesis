import logging
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.quota_gates import require_quota
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.crud import file as file_crud
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.error_handlers import internal_error
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.services.test import (
    bulk_create_tests,
    extract_test_from_conversation,
    resolve_test_entity_names,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.execution_validation import (
    handle_execution_error,
    validate_execution_model,
)
from rhesis.backend.app.utils.hidden_rows import exclude_metric_owned
from rhesis.backend.app.utils.odata import apply_select

logger = logging.getLogger(__name__)

router = RhesisRouter(
    prefix="/tests", tags=["tests"], responses={404: {"description": "Not found"}}, resource="test"
)


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
    """Create a new test."""
    organization_id, user_id = tenant_context
    test_data = resolve_test_entity_names(db, test.model_dump(), organization_id, user_id)
    return crud.create_test(db=db, test=test_data, organization_id=organization_id, user_id=user_id)


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
                    "expected_response": "Optional expected response"
                },
                "requirement": "Requirement name",
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
    except HTTPException:
        # The empty-request 400 above is raised inside this try; without this
        # arm the broad handler below turns it into a 500.
        raise
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
        if "not found" in str(e).lower():
            # A caller error, so: no stack in the log, and the message names what
            # they can act on. The test set id is the only reference they supplied
            # -- everything else a bulk test refers to is get-or-created.
            logger.warning("Referenced entity missing while creating tests in bulk: %s", e)
            missing = (
                f"Test set {test_data.test_set_id} not found or not accessible"
                if test_data.test_set_id
                else "A referenced entity was not found"
            )
            raise HTTPException(status_code=404, detail=missing) from e
        raise internal_error(e, context="creating tests in bulk") from e


@router.delete("/bulk", response_model=schemas.TestBulkDeleteResponse)
def bulk_delete_tests(
    request: schemas.TestBulkDeleteRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete multiple tests at once.

    Soft-deletes every test in one transaction and recomputes each affected
    test set's attributes once, rather than once per deleted test.

    Registered before /{test_id} routes below -- FastAPI matches routes in
    registration order, so a literal /bulk path must come first or a
    /{test_id}-shaped route would swallow it (treating "bulk" as an id).
    """
    organization_id, user_id = tenant_context
    return crud.bulk_delete_tests(
        db=db, test_ids=request.test_ids, organization_id=organization_id, user_id=user_id
    )


@router.post(
    "/extract-from-conversation",
    response_model=schemas.ConversationTestExtractionResponse,
)
def extract_test_from_conversation_endpoint(
    request: schemas.ConversationToTestRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Extract test metadata from a conversation without creating a test.

    Returns pre-filled fields that the user can review and edit in a
    drawer before saving.
    """
    try:
        return extract_test_from_conversation(
            db=db,
            messages=request.messages,
            user=current_user,
            test_type=request.test_type or "Multi-Turn",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/", response_model=List[schemas.TestDetail])
# Both mirror the filters crud.get_tests applies, so the count matches the rows.
@with_count_header(
    model=models.Test,
    exclude_explorer_rows=True,
    extra_filter=exclude_metric_owned(models.Test),
)
def read_tests(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    select: str | None = Query(
        None,
        alias="$select",
        description="Comma-separated list of fields to return (e.g. id,prompt,requirement)",
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all tests with their related objects.

    Explorer tests (flagged via explorer_row) are omitted; they are reachable
    through the /explorer API only.
    """
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
    if select:
        serialized = jsonable_encoder(tests)
        return JSONResponse(content=apply_select(serialized, select))
    return tests


@router.get("/{test_id}/test_sets", response_model=List[schemas.TestSet])
def get_test_test_sets(
    test_id: UUID,
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: Optional[str] = None,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test sets that contain the given test with optional filtering."""
    organization_id, user_id = tenant_context
    db_test = crud.get_test(db, test_id=test_id, organization_id=organization_id, user_id=user_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    items, count = crud.get_test_sets_for_test(
        db=db,
        test_id=test_id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        organization_id=organization_id,
        user_id=user_id,
        filter=filter,
    )
    response.headers["X-Total-Count"] = str(count)
    return items


@router.get("/{test_id}", response_model=schemas.TestDetail)
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
    # A metric's tuning cases are reachable only through their metric, so the
    # identifier must not work here either.
    if db_test.metric_id is not None:
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
    """Update an existing test."""
    organization_id, user_id = tenant_context
    db_test = crud.get_test(db, test_id=test_id, organization_id=organization_id, user_id=user_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    test_data = resolve_test_entity_names(
        db, test.model_dump(exclude_unset=True), organization_id, user_id, is_create=False
    )
    return crud.update_test(
        db=db, test_id=test_id, test=test_data, organization_id=organization_id, user_id=user_id
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

    return crud.delete_test(
        db=db, test_id=test_id, organization_id=organization_id, user_id=user_id
    )


@router.post(
    "/execute",
    response_model=schemas.TestExecuteResponse,
    **capability(Permission.TestSet.EXECUTE),
)
async def execute_test_endpoint(
    request: schemas.TestExecuteRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_execution_model),
    _quota_gate: Organization = Depends(require_quota(QuotaResource.TEST_EXECUTIONS)),
):
    """
    Execute a test in-place without worker infrastructure or database persistence.

    This endpoint enables synchronous test execution for development, testing, or
    lightweight scenarios. Results are returned immediately without creating TestRun
    or TestResult database records.

    **Two execution modes:**

    1. **Existing test**: Provide `test_id` to execute an existing test
    2. **Inline test**: Provide complete test definition:
       - For single-turn: `prompt` + `requirement` + `topic` + `category`
       - For multi-turn: `test_configuration` (with goal) + `requirement` + `topic` + `category`

    **Parameters:**
    - `test_id`: Optional UUID of existing test
    - `endpoint_id`: Required UUID of endpoint to execute against
    - `evaluate_metrics`: Whether to evaluate and return test_metrics (default: True)
    - `prompt`: For single-turn tests (if test_id not provided)
    - `test_configuration`: For multi-turn tests (if test_id not provided)
    - `requirement`, `topic`, `category`: Required if test_id not provided
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
      "requirement": "Mathematical Reasoning",
      "topic": "Arithmetic",
      "category": "Math"
    }

    // Execute inline multi-turn test
    {
      "endpoint_id": "uuid-here",
      "evaluate_metrics": true,
      "test_configuration": {
        "goal": "Book a flight to Paris",
        "max_turns": 10,
        "min_turns": 5
      },
      "requirement": "Task Completion",
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
        # Validate user's evaluation model configuration before execution
        from rhesis.backend.app.utils.user_model_utils import validate_user_evaluation_model

        validate_user_evaluation_model(db, current_user)

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

    except HTTPException:
        raise
    except Exception as e:
        http_exception = handle_execution_error(e, operation="execute test")
        raise http_exception


@router.get("/{test_id}/files", response_model=List[schemas.FileResponse])
def list_test_files(
    test_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """List input files attached to a test."""
    organization_id, user_id = tenant_context
    return file_crud.get_files_for_entity(db, test_id, "Test", organization_id, user_id)
