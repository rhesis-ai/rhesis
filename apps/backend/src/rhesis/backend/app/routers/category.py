import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.odata import combine_entity_type_filter
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Test
CategoryDetailSchema = create_detailed_schema(schemas.Category, models.Category)

router = APIRouter(
    prefix="/categories",
    tags=["categories"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Category)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        return crud.create_category(db=db, category=category)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations (like foreign key constraints)
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            if "parent_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid parent category reference")
            if "status_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid status reference")
            if "entity_type_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid entity type reference")
            raise HTTPException(status_code=400, detail="Invalid reference in category data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Category with this name already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=list[CategoryDetailSchema])
@with_count_header(model=models.Category)
def read_categories(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    entity_type: str | None = Query(None, description="Filter categories by entity type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all categories with their related objects"""
    filter = combine_entity_type_filter(filter, entity_type)

    return crud.get_categories(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{category_id}", response_model=CategoryDetailSchema)
def read_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_category = crud.get_category(db, category_id=category_id)
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category


@router.put("/{category_id}", response_model=schemas.Category)
def update_category(
    category_id: uuid.UUID,
    category: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        db_category = crud.update_category(db, category_id=category_id, category=category)
        if db_category is None:
            raise HTTPException(status_code=404, detail="Category not found")
        return db_category
    except HTTPException:
        # Re-raise HTTPExceptions (like our 404)
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations (like foreign key constraints)
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            if "parent_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid parent category reference")
            if "status_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid status reference")
            if "entity_type_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid entity type reference")
            raise HTTPException(status_code=400, detail="Invalid reference in category data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Category with this name already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{category_id}", response_model=schemas.Category)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_category = crud.delete_category(db, category_id=category_id)
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category
