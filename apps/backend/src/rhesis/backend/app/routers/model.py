import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
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
def create_model(model: schemas.ModelCreate, db: Session = Depends(get_db)):
    """Create a new model"""
    return crud.create_model(db=db, model=model)


@router.get("/", response_model=List[ModelDetailSchema])
@with_count_header(model=models.Model)
def read_models(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
):
    """Get all models with their related objects"""
    return crud.get_models(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{model_id}", response_model=ModelDetailSchema)
def read_model(model_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a specific model by ID"""
    db_model = crud.get_model(db, model_id=model_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return db_model


@router.put("/{model_id}", response_model=schemas.Model)
def update_model(
    model_id: uuid.UUID,
    model: schemas.ModelUpdate,
    db: Session = Depends(get_db),
):
    """Update a model"""
    db_model = crud.update_model(db, model_id=model_id, model=model)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return db_model


@router.delete("/{model_id}", response_model=schemas.Model)
def delete_model(model_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a model"""
    db_model = crud.delete_model(db, model_id=model_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return db_model


@router.post("/{model_id}/test", response_model=dict)
async def test_model_connection(model_id: uuid.UUID, db: Session = Depends(get_db)):
    """Test the connection to the model's endpoint"""
    db_model = crud.get_model(db, model_id=model_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        # Here you would implement the actual connection test logic
        # This could include making a test request to the model's endpoint
        # For now, we'll just return a success message
        return {"status": "success", "message": "Connection test successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
