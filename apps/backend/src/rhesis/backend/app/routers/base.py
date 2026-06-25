from typing import Optional, Type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.schemas import Base
from rhesis.backend.app.utils.odata import apply_select
from rhesis.backend.app.utils.schema_factory import create_detailed_schema


class RhesisRouter(APIRouter):
    """APIRouter subclass that stamps a resource name onto every route it owns.

    Usage::

        router = RhesisRouter(prefix="/behaviors", tags=["behaviors"], resource="behavior")

    The ``resource`` name is stored in ``route.openapi_extra["x-rhesis-resource"]``
    on every route added to this router.  The capability deriver in
    :mod:`rhesis.backend.app.auth.capabilities` reads it to derive
    ``"behavior:read"``, ``"behavior:create"``, etc. without any hardcoded
    tag-to-resource mapping.

    Non-CRUD routes whose action cannot be inferred from the HTTP verb should
    carry an explicit ``@capability("resource:action")`` decorator instead::

        @router.post("/generate", **capability("test_set:generate"))
        async def generate(...): ...
    """

    def __init__(self, *args, resource: Optional[str] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rhesis_resource = resource

    def add_api_route(self, path: str, endpoint, **kwargs) -> None:  # type: ignore[override]
        if self._rhesis_resource:
            extra: dict = dict(kwargs.pop("openapi_extra", None) or {})
            # setdefault: an explicit @capability() marker already in the dict wins.
            extra.setdefault("x-rhesis-resource", self._rhesis_resource)
            kwargs["openapi_extra"] = extra
        super().add_api_route(path, endpoint, **kwargs)


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

    @router.get("/", response_model=list[detailed_schema])
    def read_items(
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
        select: str | None = Query(
            None,
            alias="$select",
            description="Comma-separated list of fields to return",
        ),
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
        if select:
            serialized = jsonable_encoder(items)
            return JSONResponse(content=apply_select(serialized, select))
        return items
