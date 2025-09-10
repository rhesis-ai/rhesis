import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_tenant_context
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.tag import EntityType
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Tag)
def create_tag(
    tag: schemas.TagCreate,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create tag with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    try:
        return crud.create_tag(
            db=db,
            tag=tag,
            organization_id=organization_id,
            user_id=user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations (like foreign key constraints)
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            raise HTTPException(status_code=400, detail="Invalid reference in tag data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Tag with this name already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=list[schemas.Tag])
@with_count_header(model=models.Tag)
def read_tags(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all tags with their related objects"""
    return crud.get_tags(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{tag_id}")
def read_tag(
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get tag with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_tag = crud.get_tag(db, tag_id=tag_id)
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return db_tag


@router.delete("/{tag_id}")
def delete_tag(
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete tag with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_tag = crud.delete_tag(db, tag_id=tag_id)
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return db_tag


@router.put("/{tag_id}", response_model=schemas.Tag)
def update_tag(
    tag_id: uuid.UUID,
    tag: schemas.TagUpdate,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update tag with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_tag = crud.update_tag(
        db, 
        tag_id=tag_id, 
        tag=tag,
        organization_id=organization_id,
        user_id=user_id
    )
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return db_tag


@router.post("/{entity_type}/{entity_id}", response_model=schemas.Tag)
def assign_tag_to_entity(
    entity_type: EntityType,
    entity_id: uuid.UUID,
    tag: schemas.TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Assign a tag to a specific entity"""
    # Set the user_id and organization_id from the current user
    if not tag.user_id:
        tag.user_id = current_user.id
    if not tag.organization_id:
        tag.organization_id = current_user.organization_id

    try:
        return crud.assign_tag(db=db, tag=tag, entity_id=entity_id, entity_type=entity_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{entity_type}/{entity_id}/{tag_id}")
def remove_tag_from_entity(
    entity_type: EntityType,
    entity_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Remove a tag from a specific entity"""
    try:
        success = crud.remove_tag(
            db=db, tag_id=tag_id, entity_id=entity_id, entity_type=entity_type
        )
        if not success:
            raise HTTPException(status_code=404, detail="Tag assignment not found")
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
