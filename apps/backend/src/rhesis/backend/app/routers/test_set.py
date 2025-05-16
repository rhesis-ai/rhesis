import uuid
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import require_current_user_or_token
from rhesis.backend.app.auth.decorators import check_resource_permission
from rhesis.backend.app.auth.permissions import ResourceAction
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.prompt import get_prompts_for_test_set, prompts_to_csv
from rhesis.backend.app.services.test import (
    create_test_set_associations,
    remove_test_set_associations,
)
from rhesis.backend.app.services.test_set import (
    bulk_create_test_set,
    get_test_set_stats,
    get_test_set_test_stats,
)
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema
from rhesis.backend.logging import logger

# Create the detailed schema for TestSet and Test
TestSetDetailSchema = create_detailed_schema(schemas.TestSet, models.TestSet)
TestDetailSchema = create_detailed_schema(schemas.Test, models.Test)

router = APIRouter(
    prefix="/test_sets",
    tags=["test_sets"],
    responses={404: {"description": "Not found"}},
)


class StatsMode(str, Enum):
    ENTITY = "entity"
    RELATED_ENTITY = "related_entity"


def resolve_test_set_or_raise(identifier: str, db: Session) -> TestSet:
    """
    Helper function to resolve a test set by identifier and raise 404 if not found.

    Args:
        identifier: The test set identifier (UUID, nano_id, or slug)
        db: The database session

    Returns:
        The resolved TestSet

    Raises:
        HTTPException: 404 error if test set is not found
    """
    db_test_set = crud.resolve_test_set(identifier, db)
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found with provided identifier")
    return db_test_set


@router.post("/bulk", response_model=schemas.TestSetBulkResponse)
async def create_test_set_bulk(
    test_set_data: schemas.TestSetBulkCreate,
    db: Session = Depends(get_db),
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
                "test_configuration": {}  # Optional test configuration
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
        test_set = bulk_create_test_set(
            db=db,
            test_set_data=test_set_data,
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
        )
        return test_set
    except Exception as e:
        logger.error(f"Failed to create test set: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create test set: {str(e)}")


@router.post("/", response_model=schemas.TestSet)
async def create_test_set(
    test_set: schemas.TestSetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    return crud.create_test_set(db=db, test_set=test_set)


@router.get("/", response_model=list[TestSetDetailSchema])
@with_count_header(model=models.TestSet)
async def read_test_sets(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    order_by: str = "created_at",
    order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get test sets with flexible filtering.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        order_by: Field to sort by
        order: Sort order (asc/desc)
        filter: OData filter string (use $filter in the query)
        db: Database session
        current_user: Current user
    """
    return crud.get_test_sets(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=order_by,
        sort_order=order,
        filter=filter,
    )


@router.get("/stats", response_model=schemas.EntityStats)
def generate_test_set_stats(
    top: Optional[int] = None,
    months: Optional[int] = 6,
    mode: StatsMode = StatsMode.ENTITY,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    return resolve_test_set_or_raise(test_set_identifier, db)


@router.delete("/{test_set_id}", response_model=schemas.TestSet)
@check_resource_permission(TestSet, ResourceAction.DELETE)
async def delete_test_set(
    test_set_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_test_set = crud.delete_test_set(db, test_set_id=test_set_id)
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found")
    return db_test_set


@router.put("/{test_set_id}", response_model=schemas.TestSet)
@check_resource_permission(TestSet, ResourceAction.UPDATE)
async def update_test_set(
    test_set_id: uuid.UUID,
    test_set: schemas.TestSetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_test_set = crud.update_test_set(db, test_set_id=test_set_id, test_set=test_set)
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found")
    return db_test_set


@router.get("/{test_set_identifier}/download", response_class=StreamingResponse)
def download_test_set_prompts(
    test_set_identifier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        # Resolve test set
        db_test_set = resolve_test_set_or_raise(test_set_identifier, db)

        # Get prompts
        prompts = get_prompts_for_test_set(db_test_set.id, db)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_test_set = resolve_test_set_or_raise(test_set_identifier, db)
    return get_prompts_for_test_set(db, db_test_set.id)


@router.get("/{test_set_identifier}/tests", response_model=list[TestDetailSchema])
async def get_test_set_tests(
    test_set_identifier: str,
    response: Response,
    skip: int = 0,
    limit: int = 10,
    order_by: str = "created_at",
    order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all tests associated with a test set."""
    db_test_set = resolve_test_set_or_raise(test_set_identifier, db)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Submit a test set for execution against an endpoint."""
    logger.info(
        f"Starting test set execution for identifier: {test_set_identifier} "
        f"and endpoint: {endpoint_id}"
    )

    try:
        # Resolve test set
        logger.debug("Resolving test set")
        db_test_set = resolve_test_set_or_raise(test_set_identifier, db)
        logger.info(f"Successfully resolved test set: {db_test_set.name} (ID: {db_test_set.id})")

        # Create a test configuration for this execution
        logger.debug("Creating test configuration")
        test_config = schemas.TestConfigurationCreate(
            endpoint_id=endpoint_id,
            test_set_id=db_test_set.id,
            user_id=current_user.id if current_user else None,
        )
        db_test_config = crud.create_test_configuration(db=db, test_configuration=test_config)
        logger.info(f"Created test configuration with ID: {db_test_config.id}")

        # Execute the test configuration
        from rhesis.backend.tasks.test_configuration import execute_test_configuration

        logger.debug("Submitting test configuration for execution")
        result = execute_test_configuration.delay(test_configuration_id=str(db_test_config.id))
        logger.info(f"Test configuration execution submitted with task ID: {result.id}")

        response_data = {
            "status": "submitted",
            "message": f"Test set execution started for {db_test_set.name}",
            "test_set_id": str(db_test_set.id),
            "endpoint_id": str(endpoint_id),
            "test_configuration_id": str(db_test_config.id),
            "task_id": result.id,
        }
        logger.debug(f"Returning response: {response_data}")
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit test set execution: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to submit test set execution: {str(e)}"
        )


@router.get("/{test_set_identifier}/stats", response_model=schemas.EntityStats)
def generate_test_set_test_stats(
    test_set_identifier: str,
    top: Optional[int] = None,
    months: Optional[int] = 6,
    mode: StatsMode = StatsMode.ENTITY,
    db: Session = Depends(get_db),
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
    db_test_set = resolve_test_set_or_raise(test_set_identifier, db)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        # Resolve test set
        db_test_set = resolve_test_set_or_raise(test_set_identifier, db)

        # Get prompts
        prompts = get_prompts_for_test_set(db_test_set.id, db)

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
                "Content-Disposition": 
                f'attachment; filename="test_set_{test_set_identifier}_prompts.csv"'
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
