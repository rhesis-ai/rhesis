import functools
import logging
import uuid
from typing import List, NamedTuple, Optional

import anyio
import httpx
from fastapi import Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.crud import tool as tool_crud
from rhesis.backend.app.crud import type_lookup as type_lookup_crud
from rhesis.backend.app.dependencies import (
    OffLoopSession,
    get_off_loop_tenant_session,
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
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.services.tool.mcp import (
    handle_mcp_exception,
    mcp_extract,
    mcp_health_check,
)
from rhesis.backend.app.services.tool.providers import (
    FieldStore,
    ProviderFieldError,
    ProviderManifest,
    all_manifests,
    get_manifest,
    prepare_credentials,
    validate_store,
)
from rhesis.backend.app.services.tool.rest import (
    create_jira_ticket_from_task,
    get_rest_client,
    run_rest_health_check,
)
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


def _manifest_or_400(provider: str) -> ProviderManifest:
    """Manifest for *provider*, or a 400 naming it.

    A tool row can name a provider this build does not know (a downgrade, or a
    type_lookup row from a newer release). Failing with 400 rather than
    KeyError keeps that a user-visible configuration error.
    """
    manifest = get_manifest(provider)
    if manifest is None:
        raise HTTPException(status_code=400, detail=f"Unknown tool provider '{provider}'")
    return manifest


def _validate_fields(
    manifest: ProviderManifest,
    credentials: dict | None,
    tool_metadata: dict | None,
    *,
    check_credentials: bool = True,
    check_metadata: bool = True,
) -> None:
    """Check a provider's declared fields, translating failures to 400.

    Which stores are checked depends on the call site: an update that carries
    no ``credentials`` key must not be told a credential is missing.
    """
    try:
        if check_credentials:
            validate_store(manifest, FieldStore.CREDENTIALS, credentials)
        if check_metadata:
            validate_store(manifest, FieldStore.METADATA, tool_metadata)
    except ProviderFieldError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _prepare_and_validate_credentials(
    manifest: ProviderManifest,
    credentials: dict | None,
    *,
    existing_credentials_json: str | None = None,
) -> dict:
    """Merge with stored values where declared, normalize, then validate."""
    try:
        prepared = prepare_credentials(
            manifest,
            credentials,
            existing_credentials_json=existing_credentials_json,
        )
        validate_store(manifest, FieldStore.CREDENTIALS, prepared)
    except ProviderFieldError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return prepared


def _validate_mcp_test_connection_request(
    provider: str,
    credentials: dict[str, str] | None,
    tool_metadata: dict | None,
) -> None:
    """Validate unsaved credentials and metadata before an MCP health check."""
    manifest = get_manifest(provider)
    if manifest is None:
        return

    if credentials is not None:
        _validate_fields(manifest, credentials, tool_metadata)
        return

    # A request may carry tool_id plus a metadata override and no credentials.
    # Metadata is the scope the agent is confined to, so it still has to hold
    # up: a caller sending an empty override would otherwise drop the saved
    # scope and run the health check against everything the token can reach.
    if tool_metadata is not None:
        _validate_fields(manifest, None, tool_metadata, check_credentials=False)


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

    manifest = _manifest_or_400(provider_type.type_value)
    prepared = _prepare_and_validate_credentials(manifest, tool.credentials)
    _validate_fields(manifest, prepared, tool.tool_metadata, check_credentials=False)


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

    See ``GET /tools/providers`` for the supported providers and the fields each one needs.
    """
    organization_id, user_id = tenant_context

    provider_type = type_lookup_crud.get_type_lookup(
        db, tool.tool_provider_type_id, organization_id, user_id
    )
    if provider_type:
        manifest = _manifest_or_400(provider_type.type_value)
        prepared = _prepare_and_validate_credentials(manifest, tool.credentials)
        _validate_fields(manifest, prepared, tool.tool_metadata, check_credentials=False)
        tool = tool.model_copy(update={"credentials": prepared})

    return tool_crud.create_tool(db=db, tool=tool, organization_id=organization_id, user_id=user_id)


@router.get("/providers")
def read_tool_providers() -> List[dict]:
    """Every supported provider, with the fields and auth methods it needs.

    Single source of truth for the frontend's provider grid and connection
    form. Before this existed the same facts were duplicated as constants in
    ``config/tool-providers.tsx`` and as per-provider branches in
    ``ToolConnectionDrawer.tsx``, and drifted from the backend whenever a
    provider changed.

    Declared ahead of ``/{tool_id}`` so the path is not parsed as a tool UUID.
    """
    return [manifest.serialize() for manifest in all_manifests()]


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
    manifest = _manifest_or_400(provider_type.type_value)
    _validate_fields(manifest, None, tool_metadata, check_credentials=False)


def _validate_and_merge_credentials_on_update(
    tool: "schemas.ToolUpdate",
    existing_tool: "models.Tool",
    provider_type: "models.TypeLookup",
) -> "schemas.ToolUpdate":
    """Validate and merge credentials on a tool update.

    Fields the manifest marks ``preserve_on_update`` fall back to the stored
    value, so a PATCH carrying only a new token keeps the instance URL, the org
    name, or the other half of a two-part credential.

    Returns the (possibly updated) tool schema so callers can capture merged
    credentials without mutating the original object.
    """
    manifest = _manifest_or_400(provider_type.type_value)
    prepared = _prepare_and_validate_credentials(
        manifest,
        tool.credentials,
        existing_credentials_json=existing_tool.credentials,
    )
    return tool.model_copy(update={"credentials": prepared})


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
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
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
        provider = await anyio.to_thread.run_sync(
            functools.partial(
                resolve_provider, db, organization_id, tool_id=str(tool_id), user_id=user_id
            )
        )
        identifier = request.url or request.id
        transport = route(provider, ToolAction.EXTRACT)
        if transport is Transport.REST:
            rest_client = await anyio.to_thread.run_sync(
                functools.partial(
                    get_rest_client,
                    db=db,
                    tool_id=str(tool_id),
                    organization_id=organization_id,
                    user_id=user_id,
                )
            )
            docs = await rest_client.fetch_all(
                identifier, include_children=request.include_children
            )
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


class _ConnectionTarget(NamedTuple):
    """What a connection test needs, resolved off the event loop."""

    provider: str
    tool_id: Optional[str]
    provider_type_id: Optional[uuid.UUID]
    credentials: Optional[dict]
    tool_metadata: Optional[dict]


def _apply_saved_tool_override(
    db: Session,
    request: TestToolConnectionRequest,
    organization_id: str,
    user_id: Optional[str],
) -> tuple[Optional[uuid.UUID], dict, Optional[dict]]:
    """Fill a partial credential override from the saved tool.

    Returns ``(provider_type_id, credentials, tool_metadata)``.
    """
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
    manifest = _manifest_or_400(provider)
    try:
        credentials = prepare_credentials(
            manifest,
            request.credentials,
            existing_credentials_json=existing_tool.credentials,
        )
    except ProviderFieldError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    metadata = request.tool_metadata
    if metadata is None:
        metadata = existing_tool.tool_metadata
    return existing_tool.tool_provider_type_id, credentials, metadata


def _resolve_connection_target(
    db: Session,
    request: TestToolConnectionRequest,
    organization_id: str,
    user_id: Optional[str],
) -> _ConnectionTarget:
    """Resolve the provider and effective credentials. Runs in a worker thread."""
    effective_tool_id = request.tool_id
    effective_provider_type_id = request.provider_type_id
    effective_credentials = request.credentials
    effective_metadata = request.tool_metadata

    if request.tool_id and request.credentials is not None:
        (
            effective_provider_type_id,
            effective_credentials,
            effective_metadata,
        ) = _apply_saved_tool_override(db, request, organization_id, user_id)
        effective_tool_id = None

    provider = resolve_provider(
        db,
        organization_id,
        tool_id=effective_tool_id,
        provider_type_id=effective_provider_type_id,
        user_id=user_id,
    )
    return _ConnectionTarget(
        provider=provider,
        tool_id=effective_tool_id,
        provider_type_id=effective_provider_type_id,
        credentials=effective_credentials,
        tool_metadata=effective_metadata,
    )


@router.post("/test-connection", response_model=TestToolConnectionResponse)
async def test_tool_connection(
    request: TestToolConnectionRequest,
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
    tenant_context=Depends(get_tenant_context),
    project_id: Optional[str] = Depends(get_project_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Test a tool's credentials via a lightweight connection check."""
    try:
        organization_id, user_id = tenant_context
        target = await anyio.to_thread.run_sync(
            _resolve_connection_target, db, request, organization_id, user_id
        )
        transport = route(target.provider, ToolAction.TEST_CONNECTION)
        if transport is Transport.REST:
            return await run_rest_health_check(
                db=db,
                organization_id=organization_id,
                tool_id=target.tool_id,
                provider_type_id=target.provider_type_id,
                credentials=target.credentials,
                user_id=user_id,
                tool_metadata=target.tool_metadata,
            )
        elif transport is Transport.MCP:
            credentials = target.credentials
            manifest = get_manifest(target.provider)
            if manifest is not None and credentials is not None:
                credentials = prepare_credentials(manifest, credentials)
            _validate_mcp_test_connection_request(
                target.provider, credentials, target.tool_metadata
            )
            return await mcp_health_check(
                organization_id=organization_id,
                user_id=user_id,
                tool_id=target.tool_id,
                provider_type_id=target.provider_type_id,
                credentials=credentials,
                tool_metadata=target.tool_metadata,
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
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
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
        provider = await anyio.to_thread.run_sync(
            functools.partial(
                resolve_provider, db, organization_id, tool_id=request.tool_id, user_id=user_id
            )
        )
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
