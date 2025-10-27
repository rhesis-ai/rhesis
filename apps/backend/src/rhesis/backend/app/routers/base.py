from typing import List, Type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.schemas import Base
from rhesis.backend.app.utils.schema_factory import create_detailed_schema


def get_router(model: Type, base_schema: Type[Base], prefix: str):
    router = APIRouter(prefix=prefix)

    # Create detailed schema dynamically
    detailed_schema = create_detailed_schema(base_schema, model)

    @router.get("/{item_id}", response_model=detailed_schema)
    def read_item(
        item_id: UUID,
        db: Session = Depends(get_tenant_db_session),
        tenant_context=Depends(get_tenant_context),
        current_user: schemas.User = Depends(require_current_user_or_token),
    ):
        organization_id, user_id = tenant_context
        db_item = crud.get_item_detail(db, model, item_id, organization_id, user_id)
        if db_item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return db_item

    @router.get("/", response_model=List[detailed_schema])
    def read_items(
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
        db: Session = Depends(get_tenant_db_session),
        tenant_context=Depends(get_tenant_context),
        current_user: schemas.User = Depends(require_current_user_or_token),
    ):
        organization_id, user_id = tenant_context
        items = crud.get_items_detail(
            db,
            model,
            skip,
            limit,
            sort_by,
            sort_order,
            filter,
            organization_id=organization_id,
            user_id=user_id,
        )
        return items
