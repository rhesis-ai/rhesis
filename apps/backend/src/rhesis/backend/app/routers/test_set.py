import uuid
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.decorators import check_resource_permission
from rhesis.backend.app.auth.permissions import ResourceAction
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas import services as services_schemas
from rhesis.backend.app.services.prompt import get_prompts_for_test_set, prompts_to_csv
from rhesis.backend.app.services.test import (
    create_test_set_associations,
    remove_test_set_associations,
)
from rhesis.backend.app.services.test_set import (
    bulk_create_test_set,
    execute_test_set_on_endpoint,
    get_test_set_stats,
    get_test_set_test_stats,
    update_test_set_attributes,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema
from rhesis.backend.logging import logger
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.test_set import generate_and_save_test_set

# Create the detailed schema for TestSet and Test
TestSetDetailSchema = create_detailed_schema(schemas.TestSet, models.TestSet)
TestDetailSchema = create_detailed_schema(schemas.Test, models.Test)

router = APIRouter(
    prefix="/test_sets", tags=["test_sets"], responses={404: {"description": "Not found the page"}}
)


class StatsMode(str, Enum):
    ENTITY = "entity"
    RELATED_ENTITY = "related_entity"


class TestSetGenerationResponse(BaseModel):
    """Response for test set generation task."""

    task_id: str
    message: str
    estimated_tests: int


def resolve_test_set_or_raise(identifier: str, db: Session, organization_id: str = None) -> TestSet:
    """
    Helper function to resolve a test set by identifier and raise 404 if not found.

    Args:
        identifier: The test set identifier (UUID, nano_id, or slug)
        db: The database session
        organization_id: Organization ID for filtering

    Returns:
        The resolved TestSet

    Raises:
        HTTPException: 404 error if test set is not found
    """
    db_test_set = crud.resolve_test_set(identifier, db, organization_id)
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found with provided identifier")
    return db_test_set


@router.post("/generate", response_model=TestSetGenerationResponse)
async def generate_test_set(
    request: services_schemas.GenerateTestsRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Generate test set using ConfigSynthesizer.

    - Small requests (num_tests ≤ 10): Could run synchronously (currently all async)
    - Large requests (num_tests > 10): Run as background task

    Args:
        request: Unified generation request with config, num_tests, sources
        db: Database session
        current_user: Current authenticated user

    Returns:
        Task information including task ID and estimated test count
    """
    try:
        # Validate config
        if not request.config.behaviors:
            raise HTTPException(status_code=400, detail="At least one behavior must be specified")

        test_type = request.test_type

        # Launch background task with explicit parameters
        task_result = task_launcher(
            generate_and_save_test_set,
            current_user=current_user,
            config=request.config.model_dump(),
            num_tests=request.num_tests,
            batch_size=request.batch_size,
            sources=[s.model_dump() for s in request.sources] if request.sources else None,
            name=request.name,
            test_type=test_type,
        )

        logger.info(
            "Test set generation task launched",
            extra={
                "task_id": task_result.id,
                "user_id": current_user.id,
                "organization_id": current_user.organization_id,
                "num_tests": request.num_tests,
            },
        )

        return TestSetGenerationResponse(
            task_id=task_result.id,
            message=f"Test set generation started. "
            f"You will be notified when {request.num_tests} tests are ready.",
            estimated_tests=request.num_tests,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start test set generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to start test set generation: {str(e)}"
        )


@router.post("/bulk", response_model=schemas.TestSetBulkResponse)
async def create_test_set_bulk(
    test_set_data: schemas.TestSetBulkCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create a test set with multiple tests in a single operation.

    The input format should be:
    {
        "name": "Test Set Name",
        "description": "Optional description",
        "short_description": "Optional short description",
        "tests": [
            {
                "prompt": {
                    "content": "Prompt text",
                    "language_code": "en",
                    "demographic": "Optional demographic (e.g., 'Caucasian')",
                    "dimension": "Optional dimension (e.g., 'Ethnicity')",
                    "expected_response": "Optional expected response text"
                },
                "behavior": "Behavior name",
                "category": "Category name",
                "topic": "Topic name",
                "test_configuration": {}  # Optional test configuration,
                "metadata": {
                    "sources": [
                        {
                            "source": "doc1.pdf",
                            "name": "Document Name",
                            "description": "Document description",
                            "content": "Document content used for this test"
                        }
                    ],
                    "generated_by": "DocumentSynthesizer",
                    "context_index": 0,
                    "context_length": 1500
                }
            }
        ]
    }

    Notes:
    - demographic and dimension are optional fields that work together
    - If both demographic and dimension are provided, they will be properly associated
    - The dimension will be created first, then the demographic will be linked to it
    - expected_response is an optional field to specify the expected model response
    """
    try:
        # Extract test_set_type from request if provided
        test_set_type = None
        if test_set_data.test_set_type:
            from rhesis.backend.app.constants import TestType

            # Convert string to TestType enum using from_string helper
            test_set_type = TestType.from_string(test_set_data.test_set_type)

        test_set = bulk_create_test_set(
            db=db,
            test_set_data=test_set_data,
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
            test_set_type=test_set_type,
        )
        return test_set
    except Exception as e:
        logger.error(f"Failed to create test set: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create test set: {str(e)}")


@router.post("/", response_model=schemas.TestSet)
@handle_database_exceptions(
    entity_name="test set", custom_unique_message="Test set with this name already exists"
)
async def create_test_set(
    test_set: schemas.TestSetCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create test set with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_test_set(
        db=db, test_set=test_set, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[TestSetDetailSchema])
@with_count_header(model=models.TestSet)
async def read_test_sets(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    has_runs: bool | None = Query(
        None, description="Filter test sets by whether they have test runs"
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get test sets with flexible filtering.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string (use $filter in the query)
        has_runs: Filter test sets by whether they have test runs.
                 If True, only return test sets that have associated test runs.
                 If False, only return test sets that don't have test runs.
                 If None/omitted, return all test sets.
        db: Database session
        current_user: Current user
    """
    from rhesis.backend.logging import logger

    logger.info(f"test_sets endpoint called with has_runs={has_runs}")

    organization_id, user_id = tenant_context
    return crud.get_test_sets(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        has_runs=has_runs,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/stats", response_model=schemas.EntityStats)
def generate_test_set_stats(
    top: Optional[int] = None,
    months: Optional[int] = 6,
    mode: StatsMode = StatsMode.ENTITY,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get statistics about test sets and their tests

    Args:
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical stats (default: 6)
        mode: Stats mode to use - either 'entity' (default) or 'related_entity'
        db: Database session
        current_user: Current user
    """
    if mode == StatsMode.ENTITY:
        return get_test_set_stats(
            db=db, current_user_organization_id=current_user.organization_id, top=top, months=months
        )
    else:
        return get_test_set_test_stats(
            db=db,
            test_set_id=None,  # No test set ID means get stats for all tests
            current_user_organization_id=current_user.organization_id,
            top=top,
            months=months,
        )


@router.get("/{test_set_identifier}", response_model=TestSetDetailSchema)
@check_resource_permission(TestSet, ResourceAction.READ)
async def read_test_set(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    return resolve_test_set_or_raise(test_set_identifier, db, organization_id)


@router.delete("/{test_set_id}", response_model=schemas.TestSet)
@check_resource_permission(TestSet, ResourceAction.DELETE)
async def delete_test_set(
    test_set_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_test_set = crud.delete_test_set(
        db, test_set_id=test_set_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found")
    return db_test_set


@router.put("/{test_set_id}", response_model=schemas.TestSet)
@check_resource_permission(TestSet, ResourceAction.UPDATE)
@handle_database_exceptions(
    entity_name="test set", custom_unique_message="Test set with this name already exists"
)
async def update_test_set(
    test_set_id: uuid.UUID,
    test_set: schemas.TestSetUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update test_set with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_test_set = crud.update_test_set(
        db,
        test_set_id=test_set_id,
        test_set=test_set,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found")

    try:
        update_test_set_attributes(db=db, test_set_id=str(test_set_id))
    except Exception as e:
        logger.warning(f"Failed to regenerate test set attributes for {test_set_id}: {e}")

    return db_test_set


@router.get("/{test_set_identifier}/download", response_class=StreamingResponse)
def download_test_set_prompts(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        # Resolve test set
        organization_id, user_id = tenant_context  # SECURITY: Get tenant context
        db_test_set = resolve_test_set_or_raise(test_set_identifier, db, organization_id)

        # Get prompts with organization filtering (SECURITY CRITICAL)
        prompts = get_prompts_for_test_set(db, db_test_set.id, organization_id)

        # Check if prompts list is empty before trying to create CSV
        if not prompts:
            raise HTTPException(
                status_code=404, detail=f"No prompts found in test set: {test_set_identifier}"
            )

        csv_data = prompts_to_csv(prompts)

        response = StreamingResponse(iter([csv_data]), media_type="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=test_set_{test_set_identifier}.csv"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download test set prompts for {test_set_identifier}: {str(e)}",
        )


@router.get("/{test_set_identifier}/prompts", response_model=list[schemas.PromptView])
def get_test_set_prompts(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context  # SECURITY: Get tenant context
    db_test_set = resolve_test_set_or_raise(test_set_identifier, db, organization_id)
    return get_prompts_for_test_set(db, db_test_set.id, organization_id)


@router.get("/{test_set_identifier}/tests", response_model=list[TestDetailSchema])
async def get_test_set_tests(
    test_set_identifier: str,
    response: Response,
    skip: int = 0,
    limit: int = 10,
    order_by: str = "created_at",
    order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all tests associated with a test set."""
    db_test_set = resolve_test_set_or_raise(
        test_set_identifier, db, str(current_user.organization_id)
    )
    items, count = crud.get_test_set_tests(
        db=db,
        test_set_id=db_test_set.id,
        skip=skip,
        limit=limit,
        sort_by=order_by,
        sort_order=order,
        filter=filter,
    )

    response.headers["X-Total-Count"] = str(count)
    return items  # FastAPI handles serialization based on response_model


@router.post("/{test_set_identifier}/execute/{endpoint_id}")
async def execute_test_set(
    test_set_identifier: str,
    endpoint_id: uuid.UUID,
    test_configuration_attributes: schemas.TestSetExecutionRequest = None,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Submit a test set for execution against an endpoint."""
    try:
        # Extract test configuration attributes from request body, default to Parallel mode
        attributes = None
        if test_configuration_attributes and test_configuration_attributes.execution_options:
            attributes = test_configuration_attributes.execution_options

        organization_id, user_id = tenant_context
        result = execute_test_set_on_endpoint(
            db=db,
            test_set_identifier=test_set_identifier,
            endpoint_id=endpoint_id,
            current_user=current_user,
            test_configuration_attributes=attributes,
            organization_id=organization_id,
            user_id=user_id,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in test set execution: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to submit test set execution: {str(e)}"
        )


@router.get("/{test_set_identifier}/stats", response_model=schemas.EntityStats)
def generate_test_set_test_stats(
    test_set_identifier: str,
    top: Optional[int] = None,
    months: Optional[int] = 6,
    mode: StatsMode = StatsMode.ENTITY,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get statistics about tests in a specific test set

    Args:
        test_set_identifier: The identifier of the test set
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical stats (default: 6)
        mode: Stats mode to use - either 'entity' (default) or 'related_entity'
        db: Database session
        current_user: Current user
    """
    db_test_set = resolve_test_set_or_raise(
        test_set_identifier, db, str(current_user.organization_id)
    )

    if mode == StatsMode.ENTITY:
        return get_test_set_stats(
            db=db, current_user_organization_id=current_user.organization_id, top=top, months=months
        )
    else:
        return get_test_set_test_stats(
            db=db,
            test_set_id=str(db_test_set.id),
            current_user_organization_id=current_user.organization_id,
            top=top,
            months=months,
        )


@router.get("/{test_set_identifier}/prompts/download")
def download_test_set_prompts_csv(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        # Resolve test set
        organization_id, user_id = tenant_context  # SECURITY: Get tenant context
        db_test_set = resolve_test_set_or_raise(test_set_identifier, db, organization_id)

        # Get prompts with organization filtering (SECURITY CRITICAL)
        prompts = get_prompts_for_test_set(db, db_test_set.id, organization_id)

        try:
            csv_data = prompts_to_csv(prompts)
        except ValueError:
            raise HTTPException(
                status_code=404, detail=f"No prompts found in test set: {test_set_identifier}"
            )

        # Return CSV file
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; "
                f'filename="test_set_{test_set_identifier}_prompts.csv"'
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download test set prompts: {str(e)}"
        )


@router.post("/{test_set_id}/associate", response_model=schemas.TestSetBulkAssociateResponse)
async def associate_tests_with_test_set(
    test_set_id: uuid.UUID,
    request: schemas.TestSetBulkAssociateRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Associate multiple existing tests with a test set in a single operation.
    """
    result = create_test_set_associations(
        db=db,
        test_set_id=str(test_set_id),
        test_ids=[str(test_id) for test_id in request.test_ids],
        organization_id=str(current_user.organization_id),
        user_id=str(current_user.id),
    )

    if not result["success"]:
        error_detail = {"message": result["message"], "metadata": result["metadata"]}
        raise HTTPException(status_code=400, detail=error_detail)

    return result


@router.post("/{test_set_id}/disassociate", response_model=schemas.TestSetBulkDisassociateResponse)
async def disassociate_tests_from_test_set(
    test_set_id: uuid.UUID,
    request: schemas.TestSetBulkDisassociateRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Remove associations between tests and a test set in a single operation.

    The input format should be:
    {
        "test_ids": ["uuid1", "uuid2", "uuid3"]
    }

    Notes:
    - All tests must exist in the database
    - The test set must exist in the database
    - Test associations will be removed in a single operation
    - If a test is not associated, it will be ignored
    """
    # Use the service method to handle the disassociation
    result = remove_test_set_associations(
        db=db,
        test_set_id=str(test_set_id),
        test_ids=[str(test_id) for test_id in request.test_ids],
        organization_id=str(current_user.organization_id),
        user_id=str(current_user.id),
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return schemas.TestSetBulkDisassociateResponse(
        success=result["success"],
        total_tests=result["total_tests"],
        removed_associations=result["removed_associations"],
        message=result["message"],
    )


@router.get("/{test_set_identifier}/metrics", response_model=list[schemas.Metric])
def get_test_set_metrics(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get metrics associated with a test set.

    When a test set has associated metrics, those metrics override the default
    behavior-level metrics during test execution.

    If no metrics are associated, the test set will use the metrics defined
    on each test's behavior during execution.

    Args:
        test_set_identifier: The test set identifier (UUID, nano_id, or slug)
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of metrics associated with the test set (empty list if none)
    """
    db_test_set = resolve_test_set_or_raise(
        test_set_identifier, db, str(current_user.organization_id)
    )
    return db_test_set.metrics or []


@router.post("/{test_set_identifier}/metrics/{metric_id}", response_model=list[schemas.Metric])
def add_metric_to_test_set(
    test_set_identifier: str,
    metric_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Add a metric to a test set.

    When a test set has associated metrics, those metrics override the default
    behavior-level metrics during test execution.

    Args:
        test_set_identifier: The test set identifier (UUID, nano_id, or slug)
        metric_id: The metric ID to add
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated list of metrics associated with the test set
    """
    db_test_set = resolve_test_set_or_raise(
        test_set_identifier, db, str(current_user.organization_id)
    )

    try:
        added = crud.add_metric_to_test_set(
            db=db,
            test_set_id=db_test_set.id,
            metric_id=metric_id,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
        )
        if not added:
            raise HTTPException(
                status_code=400, detail="Metric is already associated with this test set"
            )
        db.commit()
        db.refresh(db_test_set)
        return db_test_set.metrics or []
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{test_set_identifier}/metrics/{metric_id}", response_model=list[schemas.Metric])
def remove_metric_from_test_set(
    test_set_identifier: str,
    metric_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Remove a metric from a test set.

    Args:
        test_set_identifier: The test set identifier (UUID, nano_id, or slug)
        metric_id: The metric ID to remove
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated list of metrics associated with the test set
    """
    db_test_set = resolve_test_set_or_raise(
        test_set_identifier, db, str(current_user.organization_id)
    )

    try:
        removed = crud.remove_metric_from_test_set(
            db=db,
            test_set_id=db_test_set.id,
            metric_id=metric_id,
            organization_id=current_user.organization_id,
        )
        if not removed:
            raise HTTPException(
                status_code=400, detail="Metric is not associated with this test set"
            )
        db.commit()
        db.refresh(db_test_set)
        return db_test_set.metrics or []
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
