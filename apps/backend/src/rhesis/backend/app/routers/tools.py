import logging
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
from rhesis.backend.app.schemas.services import (
    ExtractToolRequest,
    ExtractToolResponse,
    TestToolConnectionRequest,
    TestToolConnectionResponse,
)
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.services.tool.mcp import handle_mcp_exception
from rhesis.backend.app.services.tool.rest import get_rest_client, run_rest_health_check
from rhesis.backend.app.services.tool.rest.config import validate_base_url
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

logger = logging.getLogger(__name__)

# Create the detailed schema for Tool
ToolDetailSchema = create_detailed_schema(schemas.Tool, models.Tool)

router = APIRouter(
    prefix="/tools",
    tags=["tools"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Tool)
def create_tool(
    tool: schemas.ToolCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create a new tool.

    A tool allows the system to connect to an external service or API. Examples of tools are:

    - MCPs
    - APIs

    Supported providers: notion, github, jira, confluence.
    """
    organization_id, user_id = tenant_context

    # Validate provider-specific requirements
    provider_type = crud.get_type_lookup(db, tool.tool_provider_type_id, organization_id, user_id)
    if provider_type:
        if provider_type.type_value == "jira":
            if not tool.tool_metadata or "space_key" not in tool.tool_metadata:
                raise HTTPException(status_code=400, detail="Jira integrations require 'space_key'")
            if (
                not isinstance(tool.tool_metadata["space_key"], str)
                or not tool.tool_metadata["space_key"].strip()
            ):
                raise HTTPException(status_code=400, detail="Jira 'space_key' must be non-empty")

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

    Note: credentials is excluded from the response for security.
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

    Note: credentials is excluded from the response for security.
    """
    organization_id, user_id = tenant_context
    tool = crud.get_tool(db=db, tool_id=tool_id, organization_id=organization_id, user_id=user_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.patch("/{tool_id}", response_model=schemas.Tool)
def update_tool(
    tool_id: uuid.UUID,
    tool: schemas.ToolUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update a tool.

    Only provide credentials if you want to update them (they will be re-encrypted).

    """
    organization_id, user_id = tenant_context

    if tool.tool_metadata is not None or tool.credentials is not None:
        existing_tool = crud.get_tool(
            db=db, tool_id=tool_id, organization_id=organization_id, user_id=user_id
        )
        if not existing_tool:
            raise HTTPException(status_code=404, detail="Tool not found")

        provider_type = crud.get_type_lookup(
            db, existing_tool.tool_provider_type_id, organization_id, user_id
        )
        if provider_type:
            if provider_type.type_value == "jira":
                if tool.tool_metadata is not None:
                    if "space_key" not in tool.tool_metadata:
                        raise HTTPException(
                            status_code=400, detail="Jira integrations require 'space_key'"
                        )
                    if (
                        not isinstance(tool.tool_metadata["space_key"], str)
                        or not tool.tool_metadata["space_key"].strip()
                    ):
                        raise HTTPException(
                            status_code=400, detail="Jira 'space_key' must be non-empty"
                        )
                if tool.credentials is not None and "JIRA_URL" in tool.credentials:
                    try:
                        validate_base_url(tool.credentials["JIRA_URL"], "JIRA_URL")
                    except ValueError as e:
                        raise HTTPException(status_code=400, detail=str(e))
            elif provider_type.type_value == "confluence":
                if tool.credentials is not None and "CONFLUENCE_URL" in tool.credentials:
                    try:
                        validate_base_url(tool.credentials["CONFLUENCE_URL"], "CONFLUENCE_URL")
                    except ValueError as e:
                        raise HTTPException(status_code=400, detail=str(e))

    db_tool = crud.update_tool(
        db=db, tool_id=tool_id, tool=tool, organization_id=organization_id, user_id=user_id
    )
    if db_tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return db_tool


@router.post("/{tool_id}/extract", response_model=ExtractToolResponse)
async def extract_tool_item(
    tool_id: uuid.UUID,
    request: ExtractToolRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Extract content from a tool item as markdown.

    Supports Notion and GitHub tools via direct REST API calls.
    Set include_children=True to recursively fetch child pages / subdirectory files.
    Either ``id`` or ``url`` (or both) must be provided in the request body.
    """
    try:
        organization_id, user_id = tenant_context
        client = get_rest_client(
            db=db,
            tool_id=str(tool_id),
            organization_id=organization_id,
            user_id=user_id,
        )
        if not hasattr(client, "fetch_all"):
            raise HTTPException(
                status_code=400,
                detail="Extract is not supported for this tool provider.",
            )
        identifier = request.url or request.id
        docs = await client.fetch_all(identifier, include_children=request.include_children)
        return ExtractToolResponse(
            sources=[
                {"id": d.id, "title": d.title, "content": d.content, "url": d.url} for d in docs
            ]
        )
    except HTTPException:
        raise
    except (ToolConfigurationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Tool extract error: {e}", exc_info=True)
        raise handle_mcp_exception(e, "extract")


@router.post("/test-connection", response_model=TestToolConnectionResponse)
async def test_tool_connection(
    request: TestToolConnectionRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Test a tool's credentials via a lightweight REST health check."""
    try:
        organization_id, user_id = tenant_context
        result = await run_rest_health_check(
            db=db,
            organization_id=organization_id,
            tool_id=request.tool_id,
            provider_type_id=request.provider_type_id,
            credentials=request.credentials,
            user_id=user_id,
        )
        return result
    except (ToolConfigurationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Tool health check error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
