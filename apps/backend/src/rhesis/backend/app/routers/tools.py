import logging
import uuid
from typing import List, Optional

import httpx
from fastapi import Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.crud import tool as tool_crud
from rhesis.backend.app.crud import type_lookup as type_lookup_crud
from rhesis.backend.app.dependencies import (
    get_project_context,
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.error_handlers import UpstreamHTTPException
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.services import (
    CreateJiraTicketFromTaskRequest,
    CreateJiraTicketFromTaskResponse,
    ExtractToolRequest,
    ExtractToolResponse,
    TestToolConnectionRequest,
    TestToolConnectionResponse,
)
from rhesis.backend.app.services.tool.actions import (
    ToolAction,
    Transport,
    resolve_provider,
    route,
)
from rhesis.backend.app.services.tool.azure_devops import (
    normalize_azure_devops_org,
    prepare_azure_devops_credentials,
)
from rhesis.backend.app.services.tool.credential_merge import (
    merge_azure_devops_credentials_on_update as _merge_azure_devops_credentials_on_update,
)
from rhesis.backend.app.services.tool.credential_merge import (
    merge_gitlab_credentials_on_update as _merge_gitlab_credentials_on_update,
)
from rhesis.backend.app.services.tool.credential_merge import (
    resolve_mcp_test_connection_credentials,
)
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.services.tool.mcp import (
    handle_mcp_exception,
    mcp_extract,
    mcp_health_check,
)
from rhesis.backend.app.services.tool.rest import (
    create_jira_ticket_from_task,
    get_rest_client,
    run_rest_health_check,
)
from rhesis.backend.app.services.tool.rest.config import validate_base_url
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.sdk.agents.mcp.exceptions import MCPError

logger = logging.getLogger(__name__)

router = RhesisRouter(
    prefix="/tools",
    tags=["tools"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource="tool",
)


def _validate_gitlab_project(tool_metadata: dict | None) -> None:
    if not tool_metadata or "project" not in tool_metadata:
        raise HTTPException(
            status_code=400,
            detail="GitLab integrations require project metadata",
        )
    project = tool_metadata["project"]
    if not isinstance(project, dict) or "namespace" not in project:
        raise HTTPException(
            status_code=400,
            detail="GitLab project must include 'namespace'",
        )
    namespace = project["namespace"]
    if not isinstance(namespace, str) or not namespace.strip() or "/" not in namespace.strip():
        raise HTTPException(
            status_code=400,
            detail="GitLab 'namespace' must be a non-empty group/project path",
        )


def _validate_gitlab_credentials(credentials: dict[str, str] | None) -> None:
    token = (credentials or {}).get("GITLAB_PERSONAL_ACCESS_TOKEN", "")
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=400,
            detail="GitLab integrations require 'GITLAB_PERSONAL_ACCESS_TOKEN'",
        )


def _validate_shortcut_credentials(credentials: dict[str, str] | None) -> None:
    token = (credentials or {}).get("SHORTCUT_API_TOKEN", "")
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=400,
            detail="Shortcut integrations require 'SHORTCUT_API_TOKEN'",
        )


def _validate_asana_workspace_gid(tool_metadata: dict | None) -> None:
    if not tool_metadata or "workspace_gid" not in tool_metadata:
        return
    workspace_gid = tool_metadata["workspace_gid"]
    if not isinstance(workspace_gid, str) or not workspace_gid.strip():
        raise HTTPException(
            status_code=400,
            detail="Asana 'workspace_gid' must be a non-empty string",
        )


def _validate_asana_credentials(credentials: dict[str, str] | None) -> None:
    token = (credentials or {}).get("ASANA_ACCESS_TOKEN", "")
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=400,
            detail="Asana integrations require 'ASANA_ACCESS_TOKEN'",
        )


def _validate_linear_credentials(credentials: dict[str, str] | None) -> None:
    token = (credentials or {}).get("LINEAR_API_TOKEN", "")
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=400,
            detail="Linear integrations require 'LINEAR_API_TOKEN'",
        )


def _validate_trello_credentials(credentials: dict[str, str] | None) -> None:
    token = (credentials or {}).get("TRELLO_TOKEN", "")
    key = (credentials or {}).get("TRELLO_API_KEY", "")

    if not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=400,
            detail="TRELLO integrations require 'TRELLO_TOKEN'",
        )

    if not isinstance(key, str) or not key.strip():
        raise HTTPException(
            status_code=400,
            detail="TRELLO integrations require 'TRELLO_API_KEY'",
        )


def _validate_trello_workspace_gid(tool_metadata: dict | None) -> None:
    if not tool_metadata or "workspace_gid" not in tool_metadata:
        return
    workspace_gid = tool_metadata["workspace_gid"]
    if not isinstance(workspace_gid, str) or not workspace_gid.strip():
        raise HTTPException(
            status_code=400,
            detail="Trello 'workspace_gid' must be a non-empty string",
        )


def _validate_azure_devops_project(tool_metadata: dict | None) -> None:
    if not tool_metadata or "project" not in tool_metadata:
        raise HTTPException(
            status_code=400,
            detail="Azure DevOps integrations require project metadata",
        )
    project = tool_metadata["project"]
    if not isinstance(project, str) or not project.strip():
        raise HTTPException(
            status_code=400,
            detail="Azure DevOps 'project' must be a non-empty string",
        )


def _validate_azure_devops_credentials(credentials: dict[str, str] | None) -> None:
    org = (credentials or {}).get("AZURE_DEVOPS_ORG", "")
    if not isinstance(org, str) or not org.strip():
        raise HTTPException(
            status_code=400,
            detail="Azure DevOps integrations require 'AZURE_DEVOPS_ORG'",
        )
    try:
        normalize_azure_devops_org(org)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    email = (credentials or {}).get("AZURE_DEVOPS_EMAIL", "")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=400,
            detail="Azure DevOps integrations require 'AZURE_DEVOPS_EMAIL'",
        )

    token = (credentials or {}).get("AZURE_DEVOPS_PAT", "")
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=400,
            detail="Azure DevOps integrations require 'AZURE_DEVOPS_PAT'",
        )


def _validate_mcp_test_connection_request(
    provider: str,
    credentials: dict[str, str] | None,
    tool_metadata: dict | None,
) -> None:
    """Validate unsaved credentials/metadata before MCP health check."""
    if credentials is None:
        return

    if provider == "gitlab":
        _validate_gitlab_credentials(credentials)
        _validate_gitlab_project(tool_metadata)
    elif provider == "shortcut":
        _validate_shortcut_credentials(credentials)
    elif provider == "asana":
        _validate_asana_credentials(credentials)
        _validate_asana_workspace_gid(tool_metadata)
    elif provider == "trello":
        _validate_trello_credentials(credentials)
        _validate_trello_workspace_gid(tool_metadata)
    elif provider == "linear":
        _validate_linear_credentials(credentials)
    elif provider == "azure_devops":
        _validate_azure_devops_credentials(credentials)
        _validate_azure_devops_project(tool_metadata)


def _validate_provider_type_switch(
    existing_tool: models.Tool,
    tool: schemas.ToolUpdate,
    provider_type: models.TypeLookup | None,
) -> None:
    if tool.tool_provider_type_id is None:
        return
    if tool.tool_provider_type_id == existing_tool.tool_provider_type_id:
        return

    if tool.credentials is None or tool.tool_metadata is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Changing tool provider type requires both credentials "
                "and tool_metadata in the same request"
            ),
        )

    if not provider_type:
        raise HTTPException(status_code=400, detail="Invalid tool provider type")

    if provider_type.type_value == "jira":
        if "space_key" not in tool.tool_metadata:
            raise HTTPException(status_code=400, detail="Jira integrations require 'space_key'")
        if (
            not isinstance(tool.tool_metadata["space_key"], str)
            or not tool.tool_metadata["space_key"].strip()
        ):
            raise HTTPException(status_code=400, detail="Jira 'space_key' must be non-empty")
    elif provider_type.type_value == "gitlab":
        _validate_gitlab_credentials(tool.credentials)
        _validate_gitlab_project(tool.tool_metadata)
    elif provider_type.type_value == "shortcut":
        _validate_shortcut_credentials(tool.credentials)
    elif provider_type.type_value == "asana":
        _validate_asana_credentials(tool.credentials)
        _validate_asana_workspace_gid(tool.tool_metadata)
    elif provider_type.type_value == "trello":
        _validate_trello_credentials(tool.credentials)
        _validate_trello_workspace_gid(tool.tool_metadata)
    elif provider_type.type_value == "linear":
        _validate_linear_credentials(tool.credentials)
    elif provider_type.type_value == "azure_devops":
        prepared_credentials = prepare_azure_devops_credentials(tool.credentials)
        _validate_azure_devops_credentials(prepared_credentials)
        _validate_azure_devops_project(tool.tool_metadata)


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

    Supported providers include notion, github, jira, confluence, and gitlab.
    """
    organization_id, user_id = tenant_context

    provider_type = type_lookup_crud.get_type_lookup(
        db, tool.tool_provider_type_id, organization_id, user_id
    )
    if provider_type:
        if provider_type.type_value == "jira":
            if not tool.tool_metadata or "space_key" not in tool.tool_metadata:
                raise HTTPException(status_code=400, detail="Jira integrations require 'space_key'")
            if (
                not isinstance(tool.tool_metadata["space_key"], str)
                or not tool.tool_metadata["space_key"].strip()
            ):
                raise HTTPException(status_code=400, detail="Jira 'space_key' must be non-empty")
        elif provider_type.type_value == "gitlab":
            _validate_gitlab_credentials(tool.credentials)
            _validate_gitlab_project(tool.tool_metadata)
        elif provider_type.type_value == "shortcut":
            _validate_shortcut_credentials(tool.credentials)
        elif provider_type.type_value == "asana":
            _validate_asana_credentials(tool.credentials)
            _validate_asana_workspace_gid(tool.tool_metadata)
        elif provider_type.type_value == "trello":
            _validate_trello_credentials(tool.credentials)
            _validate_trello_workspace_gid(tool.tool_metadata)
        elif provider_type.type_value == "linear":
            _validate_linear_credentials(tool.credentials)
        elif provider_type.type_value == "azure_devops":
            prepared_credentials = prepare_azure_devops_credentials(tool.credentials)
            _validate_azure_devops_credentials(prepared_credentials)
            _validate_azure_devops_project(tool.tool_metadata)
            tool = tool.model_copy(update={"credentials": prepared_credentials})

    return tool_crud.create_tool(db=db, tool=tool, organization_id=organization_id, user_id=user_id)


@router.get("/", response_model=List[schemas.ToolDetail])
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
    tools = tool_crud.get_tools(
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


@router.get("/{tool_id}", response_model=schemas.ToolDetail)
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
    tool = tool_crud.get_tool(
        db=db, tool_id=tool_id, organization_id=organization_id, user_id=user_id
    )
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


def _validate_tool_metadata_on_update(
    tool_metadata: dict,
    provider_type: "models.TypeLookup",
) -> None:
    """Validate provider-specific metadata fields on a tool update."""
    if provider_type.type_value == "jira":
        if "space_key" not in tool_metadata:
            raise HTTPException(status_code=400, detail="Jira integrations require 'space_key'")
        if (
            not isinstance(tool_metadata["space_key"], str)
            or not tool_metadata["space_key"].strip()
        ):
            raise HTTPException(status_code=400, detail="Jira 'space_key' must be non-empty")
    elif provider_type.type_value == "gitlab":
        _validate_gitlab_project(tool_metadata)
    elif provider_type.type_value == "asana":
        _validate_asana_workspace_gid(tool_metadata)
    elif provider_type.type_value == "trello":
        _validate_trello_workspace_gid(tool_metadata)
    elif provider_type.type_value == "azure_devops":
        _validate_azure_devops_project(tool_metadata)


def _validate_and_merge_credentials_on_update(
    tool: "schemas.ToolUpdate",
    existing_tool: "models.Tool",
    provider_type: "models.TypeLookup",
) -> "schemas.ToolUpdate":
    """Validate and, where necessary, merge credentials on a tool update.

    Returns the (possibly updated) tool schema so callers can capture merged
    credentials without mutating the original object.
    """
    if provider_type.type_value == "jira" and "JIRA_URL" in tool.credentials:
        try:
            validate_base_url(tool.credentials["JIRA_URL"], "JIRA_URL")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif provider_type.type_value == "confluence" and "CONFLUENCE_URL" in tool.credentials:
        try:
            validate_base_url(tool.credentials["CONFLUENCE_URL"], "CONFLUENCE_URL")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif provider_type.type_value == "gitlab":
        merged_credentials = _merge_gitlab_credentials_on_update(
            existing_tool.credentials,
            tool.credentials,
        )
        _validate_gitlab_credentials(merged_credentials)
        tool = tool.model_copy(update={"credentials": merged_credentials})
    elif provider_type.type_value == "shortcut":
        _validate_shortcut_credentials(tool.credentials)
    elif provider_type.type_value == "asana":
        _validate_asana_credentials(tool.credentials)
    elif provider_type.type_value == "trello":
        _validate_trello_credentials(tool.credentials)
    elif provider_type.type_value == "linear":
        _validate_linear_credentials(tool.credentials)
    elif provider_type.type_value == "azure_devops":
        merged_credentials = prepare_azure_devops_credentials(
            _merge_azure_devops_credentials_on_update(
                existing_tool.credentials,
                tool.credentials,
            )
        )
        _validate_azure_devops_credentials(merged_credentials)
        tool = tool.model_copy(update={"credentials": merged_credentials})
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

    existing_tool = tool_crud.get_tool(
        db=db, tool_id=tool_id, organization_id=organization_id, user_id=user_id
    )
    if not existing_tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    effective_provider_type_id = (
        tool.tool_provider_type_id
        if tool.tool_provider_type_id is not None
        else existing_tool.tool_provider_type_id
    )
    provider_type = type_lookup_crud.get_type_lookup(
        db, effective_provider_type_id, organization_id, user_id
    )

    _validate_provider_type_switch(existing_tool, tool, provider_type)

    if tool.tool_metadata is not None and provider_type:
        _validate_tool_metadata_on_update(tool.tool_metadata, provider_type)

    if tool.credentials is not None and provider_type:
        tool = _validate_and_merge_credentials_on_update(tool, existing_tool, provider_type)

    db_tool = tool_crud.update_tool(
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
    project_id: Optional[str] = Depends(get_project_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Extract content from a tool item as markdown.

    The transport (deterministic REST call vs. MCP agent) is chosen per provider for
    the extract action — invisible to the caller.
    Set include_children=True to recursively fetch child pages / subdirectory files
    (REST providers only).
    Either ``id`` or ``url`` (or both) must be provided in the request body.
    """
    try:
        organization_id, user_id = tenant_context
        provider = resolve_provider(db, organization_id, tool_id=str(tool_id), user_id=user_id)
        identifier = request.url or request.id
        transport = route(provider, ToolAction.EXTRACT)
        if transport is Transport.REST:
            docs = await get_rest_client(
                db=db,
                tool_id=str(tool_id),
                organization_id=organization_id,
                user_id=user_id,
            ).fetch_all(identifier, include_children=request.include_children)
        elif transport is Transport.MCP:
            docs = await mcp_extract(
                tool_id=str(tool_id),
                identifier=identifier,
                organization_id=organization_id,
                user_id=user_id,
                project_id=project_id,
            )
        return ExtractToolResponse(
            sources=[
                {"id": d.id, "title": d.title, "content": d.content, "url": d.url} for d in docs
            ]
        )
    except HTTPException:
        raise
    except (ToolConfigurationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # No log here: handle_mcp_exception logs with the MCP category attached
        # and marks the result, so this failure is recorded exactly once.
        raise handle_mcp_exception(e, "extract") from e


def _ensure_mcp_saved_credential_override(provider: str) -> None:
    """Reject tool_id + partial credentials for REST test-connection paths."""
    if route(provider, ToolAction.TEST_CONNECTION) is not Transport.MCP:
        raise HTTPException(
            status_code=400,
            detail=(
                "Partial credential overrides with tool_id are only supported for MCP providers"
            ),
        )


@router.post("/test-connection", response_model=TestToolConnectionResponse)
async def test_tool_connection(
    request: TestToolConnectionRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    project_id: Optional[str] = Depends(get_project_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Test a tool's credentials via a lightweight connection check."""
    try:
        organization_id, user_id = tenant_context
        effective_tool_id = request.tool_id
        effective_provider_type_id = request.provider_type_id
        effective_credentials = request.credentials
        effective_metadata = request.tool_metadata

        if request.tool_id and request.credentials is not None:
            existing_tool = tool_crud.get_tool(
                db=db,
                tool_id=uuid.UUID(request.tool_id),
                organization_id=organization_id,
                user_id=user_id,
            )
            if not existing_tool:
                raise HTTPException(status_code=404, detail="Tool not found")

            provider = existing_tool.tool_provider_type.type_value
            _ensure_mcp_saved_credential_override(provider)
            effective_credentials = resolve_mcp_test_connection_credentials(
                provider,
                existing_tool.credentials,
                request.credentials,
            )
            if effective_metadata is None:
                effective_metadata = existing_tool.tool_metadata
            effective_provider_type_id = existing_tool.tool_provider_type_id
            effective_tool_id = None

        provider = resolve_provider(
            db,
            organization_id,
            tool_id=effective_tool_id,
            provider_type_id=effective_provider_type_id,
            user_id=user_id,
        )
        transport = route(provider, ToolAction.TEST_CONNECTION)
        if transport is Transport.REST:
            return await run_rest_health_check(
                db=db,
                organization_id=organization_id,
                tool_id=effective_tool_id,
                provider_type_id=effective_provider_type_id,
                credentials=effective_credentials,
                user_id=user_id,
                tool_metadata=effective_metadata,
            )
        elif transport is Transport.MCP:
            if provider == "azure_devops" and effective_credentials is not None:
                effective_credentials = prepare_azure_devops_credentials(effective_credentials)
            _validate_mcp_test_connection_request(
                provider, effective_credentials, effective_metadata
            )
            return await mcp_health_check(
                organization_id=organization_id,
                user_id=user_id,
                tool_id=effective_tool_id,
                provider_type_id=effective_provider_type_id,
                credentials=effective_credentials,
                tool_metadata=effective_metadata,
                project_id=project_id,
            )
    except (ToolConfigurationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.HTTPError as e:
        # Wrong host, unreachable instance, timeout -- the user's own service,
        # and the reason is the entire result of a connection test. Bad
        # credentials never land here: health_check answers those with 200 and
        # is_authenticated="No".
        reason = str(e) or type(e).__name__
        logger.warning("Tool connection test could not reach the provider: %s", reason)
        upstream = UpstreamHTTPException(
            status_code=502, detail=f"Could not reach the provider: {reason}"
        )
        upstream.rhesis_logged = True
        raise upstream from e
    except MCPError as e:
        # MCP providers report the same failures through their own exceptions.
        raise handle_mcp_exception(e, "test connection") from e


@router.post("/jira/create-ticket-from-task", response_model=CreateJiraTicketFromTaskResponse)
async def create_jira_ticket_from_task_endpoint(
    request: CreateJiraTicketFromTaskRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create a Jira issue from a task using the configured Jira REST integration.

    Args:
        request: CreateJiraTicketFromTaskRequest with task_id and tool_id

    Returns:
        CreateJiraTicketFromTaskResponse with issue key, URL, and message
    """
    try:
        organization_id, user_id = tenant_context
        provider = resolve_provider(db, organization_id, tool_id=request.tool_id, user_id=user_id)
        # Validate the provider supports ticket creation (raises if not).
        route(provider, ToolAction.CREATE_TICKET)
        return await create_jira_ticket_from_task(
            task_id=request.task_id,
            tool_id=request.tool_id,
            db=db,
            organization_id=organization_id,
            user_id=user_id,
        )
    except ToolConfigurationError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        logger.warning(f"Invalid request for Jira ticket creation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e


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
    db_tool = tool_crud.delete_tool(
        db=db, tool_id=tool_id, organization_id=organization_id, user_id=user_id
    )
    if db_tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return Response(status_code=204)
