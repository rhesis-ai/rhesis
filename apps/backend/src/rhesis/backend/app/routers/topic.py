import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
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
def create_topic(
    topic: schemas.TopicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    return crud.create_topic(db=db, topic=topic)


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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all topics with their related objects"""
    filter = combine_entity_type_filter(filter, entity_type)

    return crud.get_topics(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{topic_id}", response_model=TopicDetailSchema)
def read_topic(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_topic = crud.get_topic(db, topic_id=topic_id)
    if db_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return db_topic


@router.delete("/{topic_id}", response_model=schemas.Topic)
def delete_topic(
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_topic = crud.delete_topic(db, topic_id=topic_id)
    if db_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return db_topic


@router.put("/{topic_id}", response_model=schemas.Topic)
def update_topic(
    topic_id: uuid.UUID,
    topic: schemas.TopicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_topic = crud.update_topic(db, topic_id=topic_id, topic=topic)
    if db_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return db_topic
