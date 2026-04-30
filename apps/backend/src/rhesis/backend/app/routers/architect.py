"""REST API for Architect session management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/architect/sessions",
    tags=["architect"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.ArchitectSession)
def create_session(
    session: schemas.ArchitectSessionCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    return crud.create_architect_session(
        db=db,
        session=session,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/", response_model=list[schemas.ArchitectSession])
@with_count_header(model=models.ArchitectSession)
def list_sessions(
    response: Response,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    return crud.get_architect_sessions(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{session_id}", response_model=schemas.ArchitectSessionDetail)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_session = crud.get_architect_session_detail(
        db,
        session_id=session_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session


@router.put("/{session_id}", response_model=schemas.ArchitectSession)
def update_session(
    session_id: uuid.UUID,
    session: schemas.ArchitectSessionUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_session = crud.update_architect_session(
        db=db,
        session_id=session_id,
        session=session,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session


@router.delete("/{session_id}", response_model=schemas.ArchitectSession)
def delete_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_session = crud.delete_architect_session(
        db=db,
        session_id=session_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session


@router.get(
    "/{session_id}/messages",
    response_model=list[schemas.ArchitectMessage],
)
def get_messages(
    session_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    # Verify session exists and belongs to user
    db_session = crud.get_architect_session(
        db,
        session_id=session_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return crud.get_architect_messages(
        db=db,
        session_id=session_id,
        skip=skip,
        limit=limit,
        organization_id=organization_id,
        user_id=user_id,
    )
