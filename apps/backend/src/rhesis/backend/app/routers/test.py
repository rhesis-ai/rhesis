from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_tenant_context
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.test import bulk_create_tests, get_test_stats
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Test
TestDetailSchema = create_detailed_schema(schemas.Test, models.Test)

router = APIRouter(
    prefix="/tests",
    tags=["tests"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.Test)
@handle_database_exceptions(
    entity_name="test", custom_unique_message="Test with this name already exists"
)
def create_test(
    test: schemas.TestCreate,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all tests with their related objects"""
    tests = crud.get_tests(
        db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )
    return tests


@router.get("/{test_id}", response_model=TestDetailSchema)
def read_test(
    test_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test by ID with its related objects"""
    db_test = crud.get_test(db, test_id=test_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return db_test


@router.put("/{test_id}", response_model=schemas.Test)
def update_test(
    test_id: UUID,
    test: schemas.TestUpdate,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test"""
    db_test = crud.get_test(db, test_id=test_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    # Check if the user has permission to delete this test
    if db_test.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete this test")

    return crud.delete_test(db=db, test_id=test_id)
