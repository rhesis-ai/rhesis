import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
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
- Test, TestSet, TestRun, TestResult, Metric, Model, Prompt, Behavior, Category, Source
"""


@router.post("/", response_model=schemas.Comment)
@handle_database_exceptions(entity_name="comment", custom_unique_message="Comment already exists")
def create_comment(
    comment: schemas.CommentCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create comment with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_comment(
        db=db, comment=comment, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=List[CommentDetailSchema])
def read_comments(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get all comments with filtering and pagination - optimized approach.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    comments = crud.get_comments(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    return comments


@router.get("/{comment_id}")
def read_comment(
    comment_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get comment with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    """Get a specific comment by ID"""
    comment = crud.get_comment(
        db=db, comment_id=comment_id, organization_id=organization_id, user_id=user_id
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment


@router.put("/{comment_id}", response_model=schemas.Comment)
def update_comment(
    comment_id: uuid.UUID,
    comment: schemas.CommentUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update comment with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    """Update a comment"""
    # Check if comment exists
    db_comment = crud.get_comment(
        db=db, comment_id=comment_id, organization_id=organization_id, user_id=user_id
    )
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Check if user owns the comment
    if db_comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this comment")

    return crud.update_comment(
        db=db,
        comment_id=comment_id,
        comment=comment,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.delete("/{comment_id}", response_model=schemas.Comment)
def delete_comment(
    comment_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete comment with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    """Delete a comment"""
    # Check if comment exists
    db_comment = crud.get_comment(
        db=db, comment_id=comment_id, organization_id=organization_id, user_id=user_id
    )
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Check if user owns the comment
    if db_comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    return crud.delete_comment(
        db=db, comment_id=comment_id, organization_id=organization_id, user_id=user_id
    )


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[CommentDetailSchema])
def read_comments_by_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get all comments for a specific entity - optimized approach.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - Direct tenant context injection

    Supported entities: Test, TestSet, TestRun, TestResult, PromptTemplate,
    Metric, Model, Prompt, Behavior, Category, Source
    """
    organization_id, user_id = tenant_context
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
        organization_id=organization_id,
        user_id=user_id,
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
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
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
    organization_id, user_id = tenant_context
    # Check if comment exists
    db_comment = crud.get_comment(
        db=db, comment_id=comment_id, organization_id=organization_id, user_id=user_id
    )
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Add emoji reaction
    updated_comment = crud.add_emoji_reaction(
        db=db,
        comment_id=comment_id,
        emoji=emoji,
        user_id=current_user.id,
        user_name=current_user.given_name or current_user.email,
        organization_id=organization_id,
        user_id_param=user_id,
    )

    if updated_comment is None:
        raise HTTPException(status_code=400, detail="Failed to add emoji reaction")

    return updated_comment


@router.delete("/{comment_id}/emoji/{emoji}")
def remove_emoji_reaction(
    comment_id: uuid.UUID,
    emoji: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Remove an emoji reaction from a comment - optimized approach.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    # Check if comment exists
    db_comment = crud.get_comment(
        db=db, comment_id=comment_id, organization_id=organization_id, user_id=user_id
    )
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Remove emoji reaction
    updated_comment = crud.remove_emoji_reaction(
        db=db,
        comment_id=comment_id,
        emoji=emoji,
        user_id=current_user.id,
        organization_id=organization_id,
        user_id_param=user_id,
    )

    if updated_comment is None:
        raise HTTPException(status_code=400, detail="Failed to remove emoji reaction")

    return updated_comment
