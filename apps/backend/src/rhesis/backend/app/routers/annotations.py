"""Annotation endpoints.

Full CRUD on the ``annotation`` table plus an entity-scoped listing. Writes go
through the annotation service, which owns the status override an annotation
puts on its parent.
"""

import uuid
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import schemas
from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import authorize_object, project_id_from_scope
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.crud import annotation as annotation_crud
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.services import annotation as annotation_service
from rhesis.backend.app.services.annotation_context import attach_context
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions

router = RhesisRouter(
    prefix="/annotations",
    tags=["annotations"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource="annotation",
)


def _load_or_404(db: Session, annotation_id: uuid.UUID, organization_id: str, user_id: str):
    annotation = annotation_crud.get_annotation(
        db, annotation_id, organization_id=organization_id, user_id=user_id
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


def _authorize_own(request: Request, db: Session, current_user: User, annotation, permission: str):
    """Narrow a write to the annotation's author.

    The full contract is the project-scoped ``annotation:update`` / ``:delete``
    that the router's ``resource`` stamp makes the authz backstop demand, *plus*
    ownership. Built-in roles grant the base and ``:own`` capabilities together,
    so the practical rule is "a member edits their own annotations"; not even an
    admin edits someone else's, since ``authorize_object`` has no bypass. Same
    contract as comments and tasks.
    """
    principal = resolve_principal_from_request(current_user, request)
    if not authorize_object(
        principal, permission, annotation, project_id=project_id_from_scope(db), db=db
    ):
        raise HTTPException(status_code=403, detail="Not authorized for this annotation")


@router.post("/", response_model=schemas.Annotation)
@handle_database_exceptions(
    entity_name="annotation", custom_unique_message="Annotation already exists"
)
def create_annotation(
    data: schemas.AnnotationCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    return annotation_service.create_annotation(db, data, current_user)


@router.get("/", response_model=List[schemas.AnnotationDetail])
def read_annotations(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    search: Optional[str] = Query(None, description="Search comments or target reference"),
    rating: Optional[str] = Query(None, description="Filter by status name (Pass/Fail)"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved state"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    test_run_id: Optional[uuid.UUID] = Query(None, description="Scope to a test run"),
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    organization_id, _ = tenant_context
    filters = {
        "search": search,
        "rating": rating,
        "resolved": resolved,
        "target_type": target_type,
        "entity_type": entity_type,
        "test_run_id": test_run_id,
        "filter": filter,
    }
    annotations = annotation_crud.get_annotations(
        db,
        organization_id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        **filters,
    )
    response.headers["X-Total-Count"] = str(
        annotation_crud.count_annotations(db, organization_id, **filters)
    )
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return attach_context(db, annotations)


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=List[schemas.AnnotationDetail],
)
def read_annotations_by_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    organization_id, _ = tenant_context
    try:
        EntityType(entity_type)
    except ValueError:
        valid = ", ".join(e.value for e in EntityType)
        raise HTTPException(status_code=400, detail=f"Invalid entity_type. Must be one of: {valid}")

    annotations = annotation_crud.get_annotations_by_entity(
        db,
        entity_id=entity_id,
        entity_type=entity_type,
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return attach_context(db, annotations)


@router.get("/{annotation_id}", response_model=schemas.AnnotationDetail)
def read_annotation(
    annotation_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    organization_id, user_id = tenant_context
    annotation = _load_or_404(db, annotation_id, organization_id, user_id)
    return attach_context(db, [annotation])[0]


@router.put("/{annotation_id}", response_model=schemas.Annotation)
def update_annotation(
    annotation_id: uuid.UUID,
    data: schemas.AnnotationUpdate,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    annotation = _load_or_404(db, annotation_id, organization_id, user_id)
    _authorize_own(request, db, current_user, annotation, Permission.Annotation.UPDATE_OWN)
    return annotation_service.update_annotation(db, annotation_id, data, current_user)


@router.delete("/{annotation_id}", response_model=schemas.Annotation)
def delete_annotation(
    annotation_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    annotation = _load_or_404(db, annotation_id, organization_id, user_id)
    _authorize_own(request, db, current_user, annotation, Permission.Annotation.DELETE_OWN)
    return annotation_service.delete_annotation(db, annotation_id, current_user)
