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
from rhesis.backend.app.schemas.model import TestModelConnectionRequest, TestModelConnectionResponse
from rhesis.backend.app.services.model_connection import ModelConnectionService
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Model
ModelDetailSchema = create_detailed_schema(schemas.Model, models.Model)

router = APIRouter(
    prefix="/models",
    tags=["models"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Model)
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
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Test a model connection before saving it.

    This endpoint validates that:
    1. The provider is supported by the SDK
    2. The API key is valid
    3. The model can be initialized successfully
    4. A simple generation call works (for full validation)

    Args:
        request: Contains provider, model_name, api_key, and optional endpoint

    Returns:
        TestModelConnectionResponse: Success status and message
    """
    result = ModelConnectionService.test_connection(
        provider=request.provider,
        model_name=request.model_name,
        api_key=request.api_key,
        endpoint=request.endpoint,
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


@router.put("/{model_id}", response_model=schemas.Model)
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


@router.delete("/{model_id}", response_model=schemas.Model)
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
    """Test the connection to the model's endpoint"""
    organization_id, user_id = tenant_context
    db_model = crud.get_model(db, model_id=model_id, organization_id=organization_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        # Here you would implement the actual connection test logic
        # This could include making a test request to the model's endpoint
        # For now, we'll just return a success message
        return {"status": "success", "message": "Connection test successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
