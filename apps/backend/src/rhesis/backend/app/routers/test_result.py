from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

TestResultDetailSchema = create_detailed_schema(schemas.TestResult, models.TestResult)

router = APIRouter(
    prefix="/test_results",
    tags=["test_results"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.TestResult)
def create_test_result(
    test_result: schemas.TestResultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create a new test result"""
    # Set the user_id to the current user if not provided
    if not test_result.user_id:
        test_result.user_id = current_user.id
    return crud.create_test_result(db=db, test_result=test_result)


@router.get("/", response_model=List[TestResultDetailSchema])
@with_count_header(model=models.TestResult)
def read_test_results(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test results"""
    test_results = crud.get_test_results(
        db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )
    return test_results


@router.get("/{test_result_id}", response_model=TestResultDetailSchema)
def read_test_result(
    test_result_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test result by ID"""
    db_test_result = crud.get_test_result(db, test_result_id=test_result_id)
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    return db_test_result


@router.put("/{test_result_id}", response_model=schemas.TestResult)
def update_test_result(
    test_result_id: UUID,
    test_result: schemas.TestResultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update a test result"""
    db_test_result = crud.get_test_result(db, test_result_id=test_result_id)
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Check if the user has permission to update this test result
    if db_test_result.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this test result")

    return crud.update_test_result(db=db, test_result_id=test_result_id, test_result=test_result)


@router.delete("/{test_result_id}", response_model=schemas.TestResult)
def delete_test_result(
    test_result_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test result"""
    db_test_result = crud.get_test_result(db, test_result_id=test_result_id)
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Check if the user has permission to delete this test result
    if db_test_result.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this test result")

    return crud.delete_test_result(db=db, test_result_id=test_result_id)
