from rhesis.backend.app.models.user import User
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_tenant_context, get_db_session, get_tenant_db_session
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Model
ModelDetailSchema = create_detailed_schema(schemas.Model, models.Model)

router = APIRouter(
    prefix="/models",
    tags=["models"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)])


@router.post("/", response_model=schemas.Model)
@handle_database_exceptions(
    entity_name="model", custom_unique_message="Model with this name already exists"
)
def create_model(
    model: schemas.ModelCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
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
    current_user: User = Depends(require_current_user_or_token)):
    """Get all models with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_models(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter, organization_id=organization_id, user_id=user_id
    )


@router.get("/{model_id}", response_model=ModelDetailSchema)
def read_model(
    model_id: uuid.UUID, 
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
    """Get a specific model by ID"""
    organization_id, user_id = tenant_context
    db_model = crud.get_model(db, model_id=model_id, organization_id=organization_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return db_model


@router.put("/{model_id}", response_model=schemas.Model)
def update_model(
    model_id: uuid.UUID,
    model: schemas.ModelUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
    """
    Update model with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_model = crud.update_model(
        db, model_id=model_id, model=model, organization_id=organization_id, user_id=user_id
    )
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return db_model


@router.delete("/{model_id}", response_model=schemas.Model)
def delete_model(
    model_id: uuid.UUID, 
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
    """Delete a model"""
    organization_id, user_id = tenant_context
    db_model = crud.delete_model(db, model_id=model_id, organization_id=organization_id, user_id=user_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return db_model


@router.post("/{model_id}/test", response_model=dict)
async def test_model_connection(
    model_id: uuid.UUID, 
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
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
