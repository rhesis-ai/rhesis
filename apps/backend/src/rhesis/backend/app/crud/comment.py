"""CRUD operations for comments and their emoji reactions.

Two behaviours here are worth knowing about. ``delete_comment`` first strips the
``comment_id`` key out of ``Task.task_metadata`` for every task that points at the comment,
so deleting a comment does not leave orphaned references behind; that cleanup is committed
separately and a failure is logged rather than blocking the delete.

The emoji helpers write through a raw ``UPDATE comment SET emojis`` instead of assigning to
the ORM attribute. ``Comment.emojis`` is a JSON column, so an in-place mutation of the dict
is not seen by SQLAlchemy's change tracking -- ``add_emoji_reaction`` therefore rebuilds the
dict before serialising it, and both helpers push the result down as JSON text.
"""

import json
import logging
import uuid
from typing import List, Optional, Union

from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

logger = logging.getLogger(__name__)

# Relationships serialized by schemas.CommentDetail -- user only.
_COMMENT_RELATED_FIELDS = (include(models.Comment.user),)


def get_comment(
    db: Session,
    comment_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Comment]:
    """Get comment with relationships eagerly loaded."""
    return get_item_detail(
        db,
        models.Comment,
        comment_id,
        organization_id,
        user_id,
        related_fields=_COMMENT_RELATED_FIELDS,
    )


def get_comments(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.Comment]:
    """Get all comments with filtering and pagination"""
    return get_items_detail(
        db,
        models.Comment,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_COMMENT_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def get_comments_by_entity(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    organization_id: str,
    user_id: str | None = None,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> List[models.Comment]:
    """Get all comments for a specific entity (test, test_set, test_run)"""
    return (
        QueryBuilder(db, models.Comment)
        .with_related(include(models.Comment.user))
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(
                models.Comment.entity_id == entity_id, models.Comment.entity_type == entity_type
            )
        )
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def create_comment(
    db: Session,
    comment: Union[schemas.CommentCreate, dict],
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.Comment:
    """Create comment."""
    # If it's a dict, convert it to CommentCreate schema first
    if isinstance(comment, dict):
        comment = schemas.CommentCreate(**comment)

    # Convert enum to string if it's still an enum object
    if hasattr(comment, "entity_type") and hasattr(comment.entity_type, "value"):
        comment.entity_type = comment.entity_type.value

    return create_item(db, models.Comment, comment, organization_id, user_id)


def update_comment(
    db: Session,
    comment_id: uuid.UUID,
    comment: schemas.CommentUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Comment]:
    """Update a comment with optimized tenant context"""
    return update_item(db, models.Comment, comment_id, comment, organization_id, user_id)


def delete_comment(
    db: Session, comment_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Comment]:
    """Delete a comment with optimized tenant context and clear task references"""
    from sqlalchemy import cast, func
    from sqlalchemy.dialects.postgresql import JSONB

    # First, clear the comment_id from all tasks that reference this comment
    # This prevents orphaned references in task_metadata
    try:
        # Clear comment_id from task_metadata using SQLAlchemy JSONB operators
        # Cast JSON to JSONB to use the '-' operator for key removal
        db.query(models.Task).filter(
            models.Task.task_metadata["comment_id"].astext == str(comment_id),
            models.Task.organization_id == organization_id,
        ).update(
            {
                models.Task.task_metadata: cast(models.Task.task_metadata, JSONB).op("-")(
                    "comment_id"
                ),
                models.Task.updated_at: func.now(),
            },
            synchronize_session=False,
        )

        # Commit the task metadata updates before deleting the comment
        db.commit()
    except Exception as e:
        # Log the error but continue with comment deletion
        # This ensures the comment can still be deleted even if task cleanup fails
        logger.error(f"Error clearing task references for comment {comment_id}: {e}")
        db.rollback()

    # Now proceed with normal comment deletion
    return delete_item(db, models.Comment, comment_id, organization_id, user_id)


def add_emoji_reaction(
    db: Session,
    comment_id: uuid.UUID,
    emoji: str,
    user_id: uuid.UUID,
    user_name: str,
    organization_id: str | None = None,
    user_id_param: str | None = None,
) -> Optional[models.Comment]:
    """Add an emoji reaction to a comment"""
    comment = get_comment(db, comment_id, organization_id, user_id_param)
    if not comment:
        return None

    # Initialize emojis if None
    if comment.emojis is None:
        comment.emojis = {}

    # Initialize emoji list if it doesn't exist
    if emoji not in comment.emojis:
        comment.emojis[emoji] = []

    # Check if user already reacted with this emoji
    existing_reaction = next(
        (reaction for reaction in comment.emojis[emoji] if reaction["user_id"] == str(user_id)),
        None,
    )

    if existing_reaction:
        return comment  # User already reacted, no change needed

    # Add new reaction
    new_reaction = {"user_id": str(user_id), "user_name": user_name}

    # Create a completely new emojis dictionary instead of modifying in-place
    current_emojis = dict(comment.emojis) if comment.emojis else {}
    if emoji not in current_emojis:
        current_emojis[emoji] = []
    current_emojis[emoji].append(new_reaction)

    # Convert dictionary to JSON string for PostgreSQL
    emojis_json = json.dumps(current_emojis)

    update_sql = text("UPDATE comment SET emojis = :emojis WHERE id = :comment_id")
    db.execute(update_sql, {"emojis": emojis_json, "comment_id": comment_id})

    # Transaction commit is handled by the session context manager
    db.refresh(comment)

    return comment


def remove_emoji_reaction(
    db: Session,
    comment_id: uuid.UUID,
    emoji: str,
    user_id: uuid.UUID,
    organization_id: str | None = None,
    user_id_param: str | None = None,
) -> Optional[models.Comment]:
    """Remove an emoji reaction from a comment"""
    comment = get_comment(db, comment_id, organization_id, user_id_param)
    if not comment:
        return None

    if comment.emojis is None or emoji not in comment.emojis:
        return comment  # No reactions to remove

    # Remove user's reaction
    comment.emojis[emoji] = [
        reaction for reaction in comment.emojis[emoji] if reaction["user_id"] != str(user_id)
    ]

    # Remove emoji key if no reactions left
    if not comment.emojis[emoji]:
        del comment.emojis[emoji]

    # Convert dictionary to JSON string for PostgreSQL
    emojis_json = json.dumps(comment.emojis)

    update_sql = text("UPDATE comment SET emojis = :emojis WHERE id = :comment_id")
    db.execute(update_sql, {"emojis": emojis_json, "comment_id": comment_id})

    # Transaction commit is handled by the session context manager
    db.refresh(comment)

    return comment
