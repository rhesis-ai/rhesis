import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Comment
CommentDetailSchema = create_detailed_schema(schemas.Comment, models.Comment)

router = APIRouter(
    prefix="/comments",
    tags=["comments"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Comment)
def create_comment(
    comment: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create a new comment"""
    # Create a dict with the comment data and add user_id
    comment_data = comment.dict()
    comment_data["user_id"] = current_user.id

    return crud.create_comment(db=db, comment=comment_data)


@router.get("/", response_model=List[CommentDetailSchema])
def read_comments(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all comments with filtering and pagination"""
    comments = crud.get_comments(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
    )
    return comments


@router.get("/{comment_id}", response_model=CommentDetailSchema)
def read_comment(
    comment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific comment by ID"""
    comment = crud.get_comment(db=db, comment_id=comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment


@router.put("/{comment_id}", response_model=schemas.Comment)
def update_comment(
    comment_id: uuid.UUID,
    comment: schemas.CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update a comment"""
    # Check if comment exists
    db_comment = crud.get_comment(db=db, comment_id=comment_id)
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Check if user owns the comment
    if db_comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this comment")

    return crud.update_comment(db=db, comment_id=comment_id, comment=comment)


@router.delete("/{comment_id}")
def delete_comment(
    comment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a comment"""
    # Check if comment exists
    db_comment = crud.get_comment(db=db, comment_id=comment_id)
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Check if user owns the comment
    if db_comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    crud.delete_comment(db=db, comment_id=comment_id)
    return {"message": "Comment deleted successfully"}


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[CommentDetailSchema])
def read_comments_by_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all comments for a specific entity (test, test_set, test_run)"""
    # Validate entity type
    valid_entity_types = ["test", "test_set", "test_run"]
    if entity_type not in valid_entity_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_type. Must be one of: {', '.join(valid_entity_types)}",
        )

    comments = crud.get_comments_by_entity(
        db=db,
        entity_id=entity_id,
        entity_type=entity_type,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return comments
