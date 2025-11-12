import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
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
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Tool
ToolDetailSchema = create_detailed_schema(schemas.Tool, models.Tool)

router = APIRouter(
    prefix="/tools",
    tags=["tools"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Tool)
@handle_database_exceptions(
    entity_name="tool", custom_unique_message="A tool for this provider already exists in your organization"
)
def create_tool(
    tool: schemas.ToolCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create a new tool integration.

    The auth_token will be encrypted in the database.
    Use {{auth_token}} placeholder in tool_metadata for token substitution.
    """
    organization_id, user_id = tenant_context
    return crud.create_tool(db=db, tool=tool, organization_id=organization_id, user_id=user_id)


@router.get("/", response_model=List[ToolDetailSchema])
@with_count_header(model=models.Tool)
def read_tools(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get all tools for the current organization.

    Note: auth_token is excluded from the response for security.
    """
    organization_id, user_id = tenant_context
    tools = crud.get_tools(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    return tools


@router.get("/{tool_id}", response_model=ToolDetailSchema)
def read_tool(
    tool_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get a specific tool by ID.

    Note: auth_token is excluded from the response for security.
    """
    organization_id, user_id = tenant_context
    tool = crud.get_tool(db=db, tool_id=tool_id, organization_id=organization_id, user_id=user_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.patch("/{tool_id}", response_model=schemas.Tool)
@handle_database_exceptions(
    entity_name="tool", custom_unique_message="A tool for this provider already exists in your organization"
)
def update_tool(
    tool_id: uuid.UUID,
    tool: schemas.ToolUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update a tool.

    Only provide auth_token if you want to update it (it will be re-encrypted).
    """
    organization_id, user_id = tenant_context
    db_tool = crud.update_tool(
        db=db, tool_id=tool_id, tool=tool, organization_id=organization_id, user_id=user_id
    )
    if db_tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return db_tool


@router.delete("/{tool_id}", status_code=204)
def delete_tool(
    tool_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete a tool (soft delete).
    """
    organization_id, user_id = tenant_context
    db_tool = crud.delete_tool(
        db=db, tool_id=tool_id, organization_id=organization_id, user_id=user_id
    )
    if db_tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return Response(status_code=204)
