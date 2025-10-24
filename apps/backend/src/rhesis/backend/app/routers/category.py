import uuid

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
@handle_database_exceptions(
    entity_name="category",
    custom_field_messages={"parent_id": "Invalid parent category reference"},
    custom_unique_message="Category with this name already exists",
)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(
        get_tenant_db_session
    ),  # ← ONLY CHANGE: get_tenant_db_session instead of get_db_session
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create category with optimized approach supporting both RLS and explicit parameters.

    Performance improvements:
    - Automatically sets PostgreSQL session variables for RLS policies
    - Maintains explicit parameter passing for maximum compatibility
    - Single database connection with optimized session variable caching
    - Drop-in replacement requiring minimal code changes
    """
    organization_id, user_id = tenant_context
    return crud.create_category(
        db=db, category=category, organization_id=organization_id, user_id=user_id
    )


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
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all categories with their related objects"""
    organization_id, user_id = tenant_context
    filter = combine_entity_type_filter(filter, entity_type)

    return crud.get_categories(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{category_id}")
def read_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get category with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_category = crud.get_category(
        db, category_id=category_id, organization_id=organization_id, user_id=user_id
    )
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category


@router.put("/{category_id}", response_model=CategoryDetailSchema)
@handle_database_exceptions(
    entity_name="category",
    custom_field_messages={"parent_id": "Invalid parent category reference"},
    custom_unique_message="Category with this name already exists",
)
def update_category(
    category_id: uuid.UUID,
    category: schemas.CategoryUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update category with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_category = crud.update_category(
        db,
        category_id=category_id,
        category=category,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category


@router.delete("/{category_id}")
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete category with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_category = crud.delete_category(
        db, category_id=category_id, organization_id=organization_id, user_id=user_id
    )
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category
