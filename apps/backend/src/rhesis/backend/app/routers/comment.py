import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import EntityType
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

"""
# Comment API Documentation

## Emoji Reactions Structure

Emoji reactions are stored as JSON in the `emojis` field of each comment. 
The structure is: {emoji_character: [list_of_user_reactions]}

### Example Comment Response:
```json
{
  "id": "uuid",
  "content": "Great work on this test!",
  "emojis": {
    "🚀": [
      {"user_id": "user-uuid-1", "user_name": "John Doe"},
      {"user_id": "user-uuid-2", "user_name": "Jane Smith"}
    ],
    "👍": [
      {"user_id": "user-uuid-3", "user_name": "Bob Wilson"}
    ]
  },
  "entity_id": "test-uuid",
  "entity_type": "Test",
  "user_id": "author-uuid",
  "organization_id": "org-uuid",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

### Key Points:
- **Emoji Character**: The emoji itself (🚀, 👍, ❤️) is the dictionary key
- **User Reactions**: Each emoji maps to a list of users who reacted
- **User Data**: Each reaction includes `user_id` and `user_name`
- **No Duplicates**: A user can only react once per emoji per comment

### Supported Entity Types:
- Test, TestSet, TestRun, TestResult, Metric, Model, Prompt, Behavior, Category
"""


@router.post("/", response_model=schemas.Comment)
def create_comment(
    comment: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create a new comment"""
    # Create a dict with the comment data and add user_id and organization_id
    comment_data = comment.model_dump()  # Use model_dump() for Pydantic v2
    comment_data["user_id"] = current_user.id
    comment_data["organization_id"] = current_user.organization_id

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
    """Get all comments for a specific entity (Test, TestSet, TestRun, TestResult, Metric, Model, Prompt, Behavior, Category)"""
    # Validate entity type
    try:
        EntityType(entity_type)
    except ValueError:
        valid_entity_types = [e.value for e in EntityType]
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


@router.post("/{comment_id}/emoji/{emoji}")
def add_emoji_reaction(
    comment_id: uuid.UUID,
    emoji: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    ## Emoji Reactions Structure

    Emoji reactions are stored as JSON in the `emojis` field of each comment.
    The structure is: {emoji_character: [list_of_user_reactions]}

    ### Example Comment Response:
    ```json
    {
      "id": "uuid",
      "content": "Great work on this test!",
      "emojis": {
        "🚀": [
          {"user_id": "user-uuid-1", "user_name": "John Doe"},
          {"user_id": "user-uuid-2", "user_name": "Jane Smith"}
        ],
        "👍": [
          {"user_id": "user-uuid-3", "user_name": "Bob Wilson"}
        ]
      },
      "entity_id": "test-uuid",
      "entity_type": "Test",
      "user_id": "author-uuid",
      "organization_id": "org-uuid",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z"
    }
    ```

    ### Key Points:
    - **Emoji Character**: The emoji itself (🚀, 👍, ❤️) is the dictionary key
    - **User Reactions**: Each emoji maps to a list of users who reacted
    - **User Data**: Each reaction includes `user_id` and `user_name`
    - **No Duplicates**: A user can only react once per emoji per comment
    """
    # Check if comment exists
    db_comment = crud.get_comment(db=db, comment_id=comment_id)
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Add emoji reaction
    updated_comment = crud.add_emoji_reaction(
        db=db,
        comment_id=comment_id,
        emoji=emoji,
        user_id=current_user.id,
        user_name=current_user.given_name or current_user.email,
    )

    if updated_comment is None:
        raise HTTPException(status_code=400, detail="Failed to add emoji reaction")

    return updated_comment


@router.delete("/{comment_id}/emoji/{emoji}")
def remove_emoji_reaction(
    comment_id: uuid.UUID,
    emoji: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Remove an emoji reaction from a comment"""
    # Check if comment exists
    db_comment = crud.get_comment(db=db, comment_id=comment_id)
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Remove emoji reaction
    updated_comment = crud.remove_emoji_reaction(
        db=db, comment_id=comment_id, emoji=emoji, user_id=current_user.id
    )

    if updated_comment is None:
        raise HTTPException(status_code=400, detail="Failed to remove emoji reaction")

    return updated_comment
