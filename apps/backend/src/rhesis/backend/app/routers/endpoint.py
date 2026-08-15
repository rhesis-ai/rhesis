import logging
import uuid
from typing import Any, Dict

from fastapi import Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.quota_gates import require_quota
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.crud import endpoint as endpoint_crud
from rhesis.backend.app.database import no_project_scope_hint
from rhesis.backend.app.dependencies import (
    get_endpoint_service,
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.error_handlers import UpstreamHTTPException, internal_error
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.endpoint import (
    AutoConfigureRequest,
    AutoConfigureResult,
    EndpointMappingTestRequest,
)
from rhesis.backend.app.schemas.services import ExploreEndpointRequest, ExploreEndpointResponse
from rhesis.backend.app.services.endpoint import EndpointService
from rhesis.backend.app.services.endpoint.auto_configure import AutoConfigureService
from rhesis.backend.app.services.invokers.common.errors import EndpointInvocationError
from rhesis.backend.app.services.usage_notifications import notify_stock_crossing
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.execution_validation import validate_generation_model
from rhesis.backend.app.utils.odata import apply_select
from rhesis.backend.jobs import launch_job
from rhesis.backend.jobs.endpoint.explore import run_exploration_task

logger = logging.getLogger(__name__)


router = RhesisRouter(
    prefix="/endpoints",
    tags=["endpoints"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource="endpoint",
)


def _endpoint_not_found_detail(db: Session) -> str:
    """404 detail for a missing endpoint.

    ``endpoint.project_id`` is NOT NULL, so an endpoint is never visible without
    a project in scope -- the hint says so rather than implying a bad id.
    """
    return f"Endpoint not found{no_project_scope_hint(db)}"


@router.post("/", response_model=schemas.Endpoint)
@handle_database_exceptions(
    entity_name="endpoint", custom_unique_message="Endpoint with this name already exists"
)
def create_endpoint(
    endpoint: schemas.EndpointCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _quota_gate: Organization = Depends(require_quota(QuotaResource.ENDPOINTS)),
):
    """Create a new endpoint.

    If no status_id is provided, the endpoint is automatically assigned
    the "Active" status.
    """
    organization_id, user_id = tenant_context

    # Auto-assign Active status when none is provided
    if not endpoint.status_id:
        active_status = get_or_create_status(
            db=db,
            name="Active",
            entity_type="General",
            organization_id=organization_id,
            user_id=user_id,
        )
        if active_status:
            endpoint.status_id = active_status.id

    new_endpoint = crud.create_endpoint(
        db=db,
        endpoint=endpoint,
        organization_id=organization_id,
        user_id=user_id,
    )

    notify_stock_crossing(db, _quota_gate, QuotaResource.ENDPOINTS)

    return new_endpoint


@router.get("/", response_model=list[schemas.EndpointDetail])
@with_count_header(model=models.Endpoint)
def read_endpoints(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    select: str | None = Query(
        None,
        alias="$select",
        description="Comma-separated list of fields to return (e.g. name,id,url)",
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all endpoints with their related objects"""
    organization_id, user_id = tenant_context
    results = crud.get_endpoints(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    if select:
        serialized = jsonable_encoder(results)
        return JSONResponse(content=apply_select(serialized, select))
    return results


@router.post("/test")
async def test_endpoint(
    test_config: schemas.EndpointTestRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    endpoint_service: EndpointService = Depends(get_endpoint_service),
):
    """
    Test an endpoint configuration without saving it to the database.

    This endpoint allows testing endpoint connectivity, authentication, and response
    handling before creating a persistent endpoint record.

    Currently only supports REST endpoints with BEARER_TOKEN authentication.

    Args:
        test_config: Endpoint test configuration including connection_type, url, method,
                    request_headers, request_mapping, response_mapping, auth_type,
                    auth_token, and input_data
        db: Database session
        tenant_context: Tenant context for organization and user IDs
        endpoint_service: The endpoint service instance

    Returns:
        The response from the endpoint, either mapped or raw depending on endpoint configuration
    """
    # No try/except: the service already logs what it handles at the level it
    # belongs, and re-logging a 400 "Only REST endpoints are supported" as an
    # ERROR here said nothing the response didn't.
    connection_type_str = (
        test_config.connection_type.value
        if hasattr(test_config.connection_type, "value")
        else str(test_config.connection_type)
    )
    logger.info(
        f"API test request for endpoint: {test_config.url} "
        f"({connection_type_str}, {test_config.method})"
    )

    organization_id, user_id = tenant_context
    result = await endpoint_service.test_endpoint(
        db,
        test_config,
        organization_id=str(organization_id),
        user_id=str(user_id),
    )
    logger.info(f"API test successful for endpoint: {test_config.url}")
    return result


@router.post("/auto-configure", response_model=AutoConfigureResult)
async def auto_configure_endpoint(
    request: AutoConfigureRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Auto-configure an endpoint using AI-powered mapping generation.

    Paste any reference material about an endpoint (curl command, code,
    API docs) and the AI will generate request/response mappings.

    Args:
        request: Auto-configure request with input text and options
        db: Database session
        current_user: Authenticated user

    Returns:
        AutoConfigureResult with generated mappings and diagnostics
    """
    try:
        service = AutoConfigureService(db, current_user)
        result = await service.auto_configure(request)
        return result
    except ValueError as e:
        logger.error(f"Auto-configure ValueError: {e}")
        raise HTTPException(
            status_code=422,
            detail=str(e),
        ) from e


@router.get("/schema")
def get_endpoint_schema(endpoint_service: EndpointService = Depends(get_endpoint_service)):
    """
    Get the endpoint schema definition.

    Args:
        endpoint_service: The endpoint service instance

    Returns:
        Dict containing the input and output schema definitions
    """
    return endpoint_service.get_schema()


@router.delete("/bulk", response_model=schemas.EndpointBulkDeleteResponse)
def bulk_delete_endpoints(
    request: schemas.EndpointBulkDeleteRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete multiple endpoints at once.

    Registered before /{endpoint_id} below -- FastAPI matches routes in
    registration order, so a literal /bulk path must come first or a
    /{endpoint_id}-shaped route would swallow it (treating "bulk" as an id).
    """
    organization_id, user_id = tenant_context
    return endpoint_crud.bulk_delete_endpoints(
        db=db,
        endpoint_ids=request.endpoint_ids,
        organization_id=organization_id,
        user_id=user_id,
    )


# --- Routes with path parameters must come AFTER static routes ---


@router.post("/{endpoint_id}/test")
async def test_endpoint_mapping(
    endpoint_id: uuid.UUID,
    test_request: EndpointMappingTestRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    endpoint_service: EndpointService = Depends(get_endpoint_service),
):
    """Test draft mappings against a stored endpoint using its stored credentials.

    Fetches the endpoint from the database (including its auth token) and invokes it
    with the provided request/response mapping overrides and input data. This lets the
    frontend test unsaved mapping edits without the auth token ever reaching the browser.
    """
    organization_id, user_id = tenant_context
    endpoint = crud.get_endpoint(
        db, endpoint_id=endpoint_id, organization_id=organization_id, user_id=user_id
    )
    if not endpoint:
        raise HTTPException(status_code=404, detail=_endpoint_not_found_detail(db))

    response_format = test_request.response_format.value if test_request.response_format else None

    return await endpoint_service.test_endpoint_mapping(
        db=db,
        endpoint=endpoint,
        request_mapping=test_request.request_mapping,
        response_mapping=test_request.response_mapping,
        input_data=test_request.input_data,
        organization_id=str(organization_id),
        user_id=str(user_id),
        response_format=response_format,
    )


@router.get("/{endpoint_id}", response_model=schemas.EndpointDetail)
def read_endpoint(
    endpoint_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_endpoint = crud.get_endpoint(
        db, endpoint_id=endpoint_id, organization_id=organization_id, user_id=user_id
    )
    if db_endpoint is None:
        raise HTTPException(status_code=404, detail=_endpoint_not_found_detail(db))
    return db_endpoint


@router.delete("/{endpoint_id}", response_model=schemas.Endpoint)
def delete_endpoint(
    endpoint_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_endpoint = crud.delete_endpoint(
        db, endpoint_id=endpoint_id, organization_id=organization_id, user_id=user_id
    )
    if db_endpoint is None:
        raise HTTPException(status_code=404, detail=_endpoint_not_found_detail(db))
    return db_endpoint


@router.put("/{endpoint_id}", response_model=schemas.Endpoint)
def update_endpoint(
    endpoint_id: uuid.UUID,
    endpoint: schemas.EndpointUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_endpoint = crud.update_endpoint(
        db,
        endpoint_id=endpoint_id,
        endpoint=endpoint,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_endpoint is None:
        raise HTTPException(status_code=404, detail=_endpoint_not_found_detail(db))
    return db_endpoint


@router.post("/{endpoint_id}/invoke", **capability(Permission.Endpoint.UPDATE))
async def invoke_endpoint(
    endpoint_id: uuid.UUID,
    input_data: Dict[str, Any],
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    endpoint_service: EndpointService = Depends(get_endpoint_service),
):
    """
    Invoke an endpoint with the given input data.

    Args:
        endpoint_id: The UUID of the endpoint to invoke
        input_data: Dictionary containing input data for the endpoint
        db: Database session
        endpoint_service: The endpoint service instance

    Returns:
        The response from the endpoint, either mapped or raw depending on endpoint configuration
    """
    try:
        logger.info(f"API invoke request for endpoint {endpoint_id} with input: {input_data}")

        # Validate that input_data contains required fields
        if not isinstance(input_data, dict):
            raise HTTPException(status_code=400, detail="Input data must be a JSON object")

        # If input_data doesn't have 'input' field, provide helpful error
        if "input" not in input_data:
            logger.warning(
                f"Input data missing 'input' field. Received keys: {list(input_data.keys())}"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required field 'input'",
                    "received_fields": list(input_data.keys()),
                    "expected_format": {
                        "input": "Your query text here (required)",
                        "conversation_id": "optional-conversation-id",
                        "custom_field": "any additional fields are passed through",
                    },
                },
            )

        organization_id, user_id = tenant_context
        result = await endpoint_service.invoke_endpoint(
            db, str(endpoint_id), input_data, organization_id=organization_id, user_id=str(user_id)
        )
        logger.info(f"API invoke successful for endpoint {endpoint_id}")
        return result
    except EndpointInvocationError as e:
        # Not logged here: `internal_error` logs our failures with a stack, and
        # the global handler logs an UpstreamHTTPException once as a warning.
        status_code = e.status_code or 500
        # EndpointService wraps *our* failures in this same type as
        # error_type="internal_error" (services/endpoint/service.py), so the
        # discriminator is what separates the user's endpoint from our bug.
        if e.error_type == "internal_error":
            raise internal_error(
                e, context=f"invoking endpoint {endpoint_id}", status_code=status_code
            ) from e
        raise UpstreamHTTPException(status_code=status_code, detail=str(e)) from e


@router.post(
    "/{endpoint_id}/explore",
    response_model=ExploreEndpointResponse,
    dependencies=[Depends(validate_generation_model)],
)
def explore_endpoint_route(
    endpoint_id: uuid.UUID,
    request: ExploreEndpointRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Launch an async Penelope exploration of an endpoint.

    Returns a ``task_id`` that can be polled via ``GET /jobs/{task_id}``
    until status is ``SUCCESS``.  The ``result`` field then contains the
    exploration findings.
    """
    organization_id, user_id = tenant_context

    db_endpoint = crud.get_endpoint(
        db, endpoint_id=endpoint_id, organization_id=organization_id, user_id=user_id
    )
    if db_endpoint is None:
        raise HTTPException(status_code=404, detail=_endpoint_not_found_detail(db))

    task_result = launch_job(
        run_exploration_task,
        current_user=current_user,
        db=db,
        endpoint_id=str(endpoint_id),
        strategy=request.strategy,
        goal=request.goal,
        instructions=request.instructions,
        scenario=request.scenario,
        restrictions=request.restrictions,
        previous_findings=request.previous_findings,
    )

    strategy_label = request.strategy or "custom goal"
    return ExploreEndpointResponse(
        task_id=str(task_result.id),
        message=(
            f"Endpoint exploration started using {strategy_label}. "
            "Poll GET /jobs/{{task_id}} until status is SUCCESS."
        ),
    )
