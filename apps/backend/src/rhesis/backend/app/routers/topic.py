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
TopicDetailSchema = create_detailed_schema(schemas.Topic, models.Topic)

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Topic)
@handle_database_exceptions(
    entity_name="topic",
    custom_field_messages={"parent_id": "Invalid parent topic reference"},
    custom_unique_message="Topic with this name already exists",
)
def create_topic(
    topic: schemas.TopicCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create topic with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_topic(db=db, topic=topic, organization_id=organization_id, user_id=user_id)


@router.get("/", response_model=list[TopicDetailSchema])
@with_count_header(model=models.Topic)
def read_topics(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    entity_type: str | None = Query(None, description="Filter topics by entity type"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all topics with their related objects"""
    organization_id, user_id = tenant_context
    filter = combine_entity_type_filter(filter, entity_type)

    return crud.get_topics(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{topic_id}")
def read_topic(
    topic_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get topic with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_topic = crud.get_topic(
        db, topic_id=topic_id, organization_id=organization_id, user_id=user_id
    )
    if db_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return db_topic


@router.delete("/{topic_id}")
def delete_topic(
    topic_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete topic with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_topic = crud.delete_topic(
        db, topic_id=topic_id, organization_id=organization_id, user_id=user_id
    )
    if db_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return db_topic


@router.put("/{topic_id}", response_model=schemas.Topic)
@handle_database_exceptions(
    entity_name="topic",
    custom_field_messages={"parent_id": "Invalid parent topic reference"},
    custom_unique_message="Topic with this name already exists",
)
def update_topic(
    topic_id: uuid.UUID,
    topic: schemas.TopicUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update topic with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_topic = crud.update_topic(
        db, topic_id=topic_id, topic=topic, organization_id=organization_id, user_id=user_id
    )
    if db_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return db_topic
