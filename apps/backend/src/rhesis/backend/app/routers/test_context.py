from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/test-contexts", tags=["test contexts"], responses={404: {"description": "Not found"}}
)


@router.post("/", response_model=schemas.TestContext)
@handle_database_exceptions(
    entity_name="test context", custom_unique_message="test context with this name already exists"
)
def create_test_context(
    test_context: schemas.TestContextCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create test context with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    # Verify that the test exists
    test = crud.get_test(
        db, test_id=test_context.test_id, organization_id=organization_id, user_id=user_id
    )
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    return crud.create_test_context(
        db=db, test_context=test_context, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=List[schemas.TestContext])
@with_count_header(model=models.TestContext)
def read_test_contexts(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    test_id: Optional[UUID] = None,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test contexts or filter by test_id"""
    organization_id, user_id = tenant_context
    if test_id:
        test_contexts = crud.get_test_contexts_by_test(
            db, test_id=test_id, organization_id=organization_id, user_id=user_id
        )
    else:
        test_contexts = crud.get_test_contexts(
            db, skip=skip, limit=limit, organization_id=organization_id, user_id=user_id
        )
    return test_contexts


@router.get("/{test_context_id}", response_model=schemas.TestContext)
def read_test_context(
    test_context_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test context by ID"""
    db_test_context = crud.get_test_context(
        db, test_context_id=test_context_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_context is None:
        raise HTTPException(status_code=404, detail="Test context not found")
    return db_test_context


@router.put("/{test_context_id}", response_model=schemas.TestContext)
def update_test_context(
    test_context_id: UUID,
    test_context: schemas.TestContextUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update test_context with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_test_context = crud.get_test_context(
        db, test_context_id=test_context_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_context is None:
        raise HTTPException(status_code=404, detail="Test context not found")

    # If test_id is being updated, verify that the test exists
    if test_context.test_id and test_context.test_id != db_test_context.test_id:
        test = crud.get_test(
            db, test_id=test_context.test_id, organization_id=organization_id, user_id=user_id
        )
        if test is None:
            raise HTTPException(status_code=404, detail="Test not found")

    return crud.update_test_context(
        db=db,
        test_context_id=test_context_id,
        test_context=test_context,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.delete("/{test_context_id}", response_model=schemas.TestContext)
def delete_test_context(
    test_context_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test context"""
    db_test_context = crud.get_test_context(
        db, test_context_id=test_context_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_context is None:
        raise HTTPException(status_code=404, detail="Test context not found")

    return crud.delete_test_context(
        db=db, test_context_id=test_context_id, organization_id=organization_id, user_id=user_id
    )
