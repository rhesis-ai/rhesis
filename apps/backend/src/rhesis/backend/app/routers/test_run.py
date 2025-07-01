from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema
from rhesis.backend.app.services.test_run import get_test_results_for_test_run, test_run_results_to_csv

# Create the detailed schema for TestRun
TestRunDetailSchema = create_detailed_schema(
    schemas.TestRun, 
    models.TestRun,
    include_nested_relationships={
        "test_configuration": {
            "endpoint": ["project"],
            "test_set": []
        }
    }
)

router = APIRouter(
    prefix="/test_runs",
    tags=["test_runs"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.TestRun)
def create_test_run(
    test_run: schemas.TestRunCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Create a new test run"""
    # Set the user_id to the current user if not provided
    if not test_run.user_id:
        test_run.user_id = current_user.id

    # Set the organization_id if not provided
    if not test_run.organization_id:
        test_run.organization_id = current_user.organization_id

    return crud.create_test_run(db=db, test_run=test_run)


@router.get("/", response_model=List[TestRunDetailSchema])
@with_count_header(model=models.TestRun)
def read_test_runs(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get all test runs with their related objects"""
    test_runs = crud.get_test_runs(
        db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )
    return test_runs


@router.get("/{test_run_id}", response_model=TestRunDetailSchema)
def read_test_run(
    test_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get a specific test run by ID with its related objects"""
    db_test_run = crud.get_test_run(db, test_run_id=test_run_id)
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    return db_test_run


@router.get("/{test_run_id}/behaviors", response_model=List[schemas.Behavior])
def get_test_run_behaviors(
    test_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get behaviors that have test results for this test run"""
    behaviors = crud.get_test_run_behaviors(db, test_run_id=test_run_id)
    return behaviors


@router.put("/{test_run_id}", response_model=schemas.TestRun)
def update_test_run(
    test_run_id: UUID,
    test_run: schemas.TestRunUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Update a test run"""
    db_test_run = crud.get_test_run(db, test_run_id=test_run_id)
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Check if the user has permission to update this test run
    if db_test_run.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this test run")

    return crud.update_test_run(db=db, test_run_id=test_run_id, test_run=test_run)


@router.delete("/{test_run_id}", response_model=schemas.TestRun)
def delete_test_run(
    test_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Delete a test run"""
    db_test_run = crud.get_test_run(db, test_run_id=test_run_id)
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Check if the user has permission to delete this test run
    if db_test_run.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete this test run")

    return crud.delete_test_run(db=db, test_run_id=test_run_id)


@router.get("/{test_run_id}/download", response_class=StreamingResponse)
def download_test_run_results(
    test_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Download test run results as CSV"""
    try:
        # Check if test run exists and user has access
        db_test_run = crud.get_test_run(db, test_run_id=test_run_id)
        if db_test_run is None:
            raise HTTPException(status_code=404, detail="Test run not found")

        # Check if the user has permission to access this test run
        if db_test_run.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized to access this test run")

        # Get test results data
        test_results_data = get_test_results_for_test_run(db, test_run_id)

        # Convert to CSV
        csv_data = test_run_results_to_csv(test_results_data)

        # Create response
        response = StreamingResponse(iter([csv_data]), media_type="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=test_run_{test_run_id}_results.csv"
        )
        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download test run results for {test_run_id}: {str(e)}",
        )