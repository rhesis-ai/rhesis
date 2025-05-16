from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/test-contexts",
    tags=["test contexts"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.TestContext)
def create_test_context(
    test_context: schemas.TestContextCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Create a new test context"""
    # Verify that the test exists
    test = crud.get_test(db, test_id=test_context.test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    return crud.create_test_context(db=db, test_context=test_context)


@router.get("/", response_model=List[schemas.TestContext])
@with_count_header(model=models.TestContext)
def read_test_contexts(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    test_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get all test contexts or filter by test_id"""
    if test_id:
        test_contexts = crud.get_test_contexts_by_test(db, test_id=test_id)
    else:
        test_contexts = crud.get_test_contexts(db, skip=skip, limit=limit)
    return test_contexts


@router.get("/{test_context_id}", response_model=schemas.TestContext)
def read_test_context(
    test_context_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get a specific test context by ID"""
    db_test_context = crud.get_test_context(db, test_context_id=test_context_id)
    if db_test_context is None:
        raise HTTPException(status_code=404, detail="Test context not found")
    return db_test_context


@router.put("/{test_context_id}", response_model=schemas.TestContext)
def update_test_context(
    test_context_id: UUID,
    test_context: schemas.TestContextUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Update a test context"""
    db_test_context = crud.get_test_context(db, test_context_id=test_context_id)
    if db_test_context is None:
        raise HTTPException(status_code=404, detail="Test context not found")

    # If test_id is being updated, verify that the test exists
    if test_context.test_id and test_context.test_id != db_test_context.test_id:
        test = crud.get_test(db, test_id=test_context.test_id)
        if test is None:
            raise HTTPException(status_code=404, detail="Test not found")

    return crud.update_test_context(
        db=db, test_context_id=test_context_id, test_context=test_context
    )


@router.delete("/{test_context_id}", response_model=schemas.TestContext)
def delete_test_context(
    test_context_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Delete a test context"""
    db_test_context = crud.get_test_context(db, test_context_id=test_context_id)
    if db_test_context is None:
        raise HTTPException(status_code=404, detail="Test context not found")

    return crud.delete_test_context(db=db, test_context_id=test_context_id)
