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
from rhesis.backend.app.schemas.model import (
    ModelRead,
    TestModelConnectionRequest,
    TestModelConnectionResponse,
)
from rhesis.backend.app.services.model_connection import ModelConnectionService
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema
from rhesis.sdk.models.factory import get_available_embedding_models, get_available_llm_models

# Create the detailed schema for Model (uses ModelRead to exclude API key from responses)
ModelDetailSchema = create_detailed_schema(ModelRead, models.Model)

router = APIRouter(
    prefix="/models",
    tags=["models"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=ModelRead)
@handle_database_exceptions(
    entity_name="model", custom_unique_message="Model with this name already exists"
)
def create_model(
    model: schemas.ModelCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create model with super optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_model(db=db, model=model, organization_id=organization_id, user_id=user_id)


@router.post("/test-connection", response_model=TestModelConnectionResponse)
async def test_model_connection_endpoint(
    request: TestModelConnectionRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Test a model connection before saving it.

    When model_id is provided (edit mode), uses the stored API key and endpoint
    from that model so the user can test without re-entering credentials.

    This endpoint validates that:
    1. The provider is supported by the SDK
    2. The API key is valid
    3. The model can be initialized successfully
    4. A test call works (generation for LLMs, embedding for embedding models)

    Args:
        request: Contains provider, model_name, api_key (or model_id), optional endpoint, and model_type

    Returns:
        TestModelConnectionResponse: Success status and message
    """
    api_key = request.api_key
    endpoint = request.endpoint

    # When model_id is set, the API key is taken from the backend-stored model credentials.
    if request.model_id:
        organization_id, user_id = tenant_context
        db_model = crud.get_model(
            db, model_id=request.model_id, organization_id=organization_id, user_id=user_id
        )
        if db_model is None:
            raise HTTPException(status_code=404, detail="Model not found")
        api_key = db_model.key or ""
        if endpoint is None or (isinstance(endpoint, str) and not endpoint.strip()):
            endpoint = db_model.endpoint

    result = ModelConnectionService.test_connection(
        provider=request.provider,
        model_name=request.model_name,
        api_key=api_key,
        endpoint=endpoint,
        model_type=request.model_type,
    )

    return TestModelConnectionResponse(
        success=result.success,
        message=result.message,
        provider=result.provider,
        model_name=result.model_name,
    )


@router.get("/", response_model=List[ModelDetailSchema])
@with_count_header(model=models.Model)
def read_models(
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
    """Get all models with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_models(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{model_id}", response_model=ModelDetailSchema)
def read_model(
    model_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific model by ID"""
    organization_id, user_id = tenant_context
    # Use get_item_detail which properly handles soft-deleted items (raises ItemDeletedException)
    from rhesis.backend.app.utils.crud_utils import get_item_detail

    db_model = get_item_detail(db, models.Model, model_id, organization_id, user_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return db_model


@router.put("/{model_id}", response_model=ModelRead)
def update_model(
    model_id: uuid.UUID,
    model: schemas.ModelUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update model with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    try:
        db_model = crud.update_model(
            db, model_id=model_id, model=model, organization_id=organization_id, user_id=user_id
        )
        if db_model is None:
            raise HTTPException(status_code=404, detail="Model not found")
        return db_model
    except ValueError as e:
        if "protected" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{model_id}", response_model=ModelRead)
def delete_model(
    model_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a model (protected system models cannot be deleted)"""
    organization_id, user_id = tenant_context
    try:
        db_model = crud.delete_model(
            db, model_id=model_id, organization_id=organization_id, user_id=user_id
        )
        if db_model is None:
            raise HTTPException(status_code=404, detail="Model not found")
        return db_model
    except ValueError as e:
        if "protected" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{model_id}/test", response_model=dict)
async def test_model_connection(
    model_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Test a model's connection by making an actual test call.

    Uses ModelConnectionService which validates the model configuration
    and makes a test call to verify it works properly (generation for LLMs,
    embedding for embedding models).
    """
    from rhesis.backend.app.services.model_connection import ModelConnectionService
    from rhesis.backend.logging import logger

    logger.info(f"[MODEL_TEST] Testing connection for model_id={model_id}")

    organization_id, user_id = tenant_context
    db_model = crud.get_model(db, model_id=model_id, organization_id=organization_id)
    if db_model is None:
        logger.warning(f"[MODEL_TEST] Model not found: model_id={model_id}")
        raise HTTPException(status_code=404, detail="Model not found")

    provider = db_model.provider_type.type_value if db_model.provider_type else None
    model_name = db_model.model_name
    api_key = db_model.key
    model_type = db_model.model_type or "llm"

    logger.info(
        f"[MODEL_TEST] Testing model: name={db_model.name}, "
        f"provider={provider}, model_name={model_name}, type={model_type}"
    )

    try:
        # Use ModelConnectionService which makes an actual test call
        result = ModelConnectionService.test_connection(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            model_type=model_type,
        )

        status = "success" if result.success else "error"
        logger.info(f"[MODEL_TEST] Test result: status={status}, message={result.message}")

        return {
            "status": status,
            "message": result.message,
        }

    except Exception as e:
        # Catch any unexpected errors
        error_msg = str(e) if str(e) else "Failed to test model connection"
        logger.error(f"[MODEL_TEST] Exception: {error_msg}", exc_info=True)
        return {
            "status": "error",
            "message": error_msg,
        }


@router.get("/provider/{provider_name}", response_model=List[str])
def get_provider_models(
    provider_name: str,
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get the list of available LLM models for a specific provider.
    """
    try:
        models_list = get_available_llm_models(provider_name)
        return models_list
    except ValueError as e:
        # ValueError is raised for unsupported providers or providers that don't support listing
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Other exceptions (network errors, API errors, etc.)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve models for provider '{provider_name}': {str(e)}",
        )


@router.get("/provider/{provider_name}/embeddings", response_model=List[str])
def get_provider_embedding_models(
    provider_name: str,
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get the list of available embedding models for a specific provider.
    """
    try:
        models_list = get_available_embedding_models(provider_name)
        return models_list
    except ValueError as e:
        # ValueError is raised for unsupported providers or providers that don't support embeddings
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Other exceptions (network errors, API errors, etc.)
        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to retrieve embedding models for provider '{provider_name}': {str(e)}"
            ),
        )
