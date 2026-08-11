"""CRUD operations for API tokens.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

Token rows are exempt from the ambient scope auto-filter, so organization scoping here is
explicit: ``get_user_tokens``, ``count_user_tokens``, ``revoke_user_tokens`` and
``get_token_by_value`` all take ``organization_id`` and apply the filter by hand. Passing
``None`` means no organization filter at all -- callers that serve a request must pass it.

``get_token_by_value`` sits on the auth hot path (``auth/token_validation.py`` runs it for
every API-token request). It looks tokens up by their SHA-256 ``token_hash`` column, which
is indexed and deterministic, instead of decrypting every row; the decrypted value is then
compared as a guard against hash collisions.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item,
    get_items,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder

logger = logging.getLogger(__name__)


def get_token(
    db: Session, token_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Token]:
    """Get token."""
    return get_item(db, models.Token, token_id, organization_id, user_id)


def get_tokens(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Token]:
    return get_items(db, models.Token, skip, limit, sort_by, sort_order, filter)


def get_user_tokens(
    db: Session,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    valid_only: bool = False,
    organization_id: str = None,
    project_id: str = None,
) -> List[models.Token]:
    """Get all active bearer tokens for a user with pagination and sorting

    Args:
        db: Database session
        user_id: User ID to get tokens for
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string
        valid_only: If True, only returns valid (non-expired) tokens
        organization_id: Organization ID for filtering
        project_id: Project ID for filtering (Token is exempt from auto-filter)

    Returns:
        List of token objects
    """
    query_builder = (
        QueryBuilder(db, models.Token)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(models.Token.user_id == user_id, models.Token.token_type == "bearer")
        )
    )

    if project_id is not None:
        query_builder = query_builder.with_custom_filter(
            lambda q: q.filter(models.Token.project_id == project_id)
        )

    # Add validity check if requested
    if valid_only:
        now = datetime.now(timezone.utc)
        query_builder = query_builder.with_custom_filter(
            lambda q: q.filter(
                # Token is either never-expiring (expires_at is None) or not yet expired
                (models.Token.expires_at.is_(None)) | (models.Token.expires_at > now)
            )
        )

    return (
        query_builder.with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def count_user_tokens(
    db: Session,
    user_id: uuid.UUID,
    filter: str | None = None,
    organization_id: str = None,
    project_id: str = None,
) -> int:
    """Count all active bearer tokens for a user

    This function applies the same filters as get_user_tokens to ensure
    the count matches the actual number of tokens the user can see.

    Args:
        db: Database session
        user_id: User ID to count tokens for
        filter: OData filter string
        organization_id: Organization ID for filtering
        project_id: Project ID for filtering (Token is exempt from auto-filter)

    Returns:
        Count of token objects
    """
    query_builder = (
        QueryBuilder(db, models.Token)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(models.Token.user_id == user_id, models.Token.token_type == "bearer")
        )
    )

    if project_id is not None:
        query_builder = query_builder.with_custom_filter(
            lambda q: q.filter(models.Token.project_id == project_id)
        )

    return query_builder.with_odata_filter(filter).count()


def create_token(
    db: Session, token: schemas.TokenCreate, organization_id: str = None, user_id: str = None
) -> models.Token:
    """Create token."""
    return create_item(db, models.Token, token, organization_id, user_id)


def update_token(
    db: Session,
    token_id: uuid.UUID,
    token: schemas.TokenUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Token]:
    """Update token."""
    return update_item(db, models.Token, token_id, token, organization_id, user_id)


def revoke_token(
    db: Session, token_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Token]:
    """Delete token."""
    return delete_item(db, models.Token, token_id, organization_id, user_id)


def revoke_user_tokens(db: Session, user_id: uuid.UUID, organization_id: str = None) -> int:
    """Revoke all tokens for a user with organization filtering (SECURITY CRITICAL)"""
    query = db.query(models.Token).filter(models.Token.user_id == user_id)

    # Apply organization filtering (SECURITY CRITICAL)
    if organization_id:
        from uuid import UUID

        query = query.filter(models.Token.organization_id == UUID(organization_id))

    result = query.delete()
    # Transaction commit is handled by the session context manager
    return result


def get_token_by_value(db: Session, token_value: str, organization_id: str = None):
    """Retrieve a token by its value with organization filtering (SECURITY CRITICAL)

    Uses SHA-256 hash for efficient O(1) indexed lookup instead of decrypting all tokens.
    The token hash is deterministic, allowing direct SQL queries, while the token itself
    remains encrypted for security.
    """
    from rhesis.backend.app.utils.encryption import hash_token

    # Compute hash of incoming token for lookup
    token_hash_value = hash_token(token_value)

    # Build query using hash index
    query = db.query(models.Token).filter(models.Token.token_hash == token_hash_value)

    # Apply organization filtering (SECURITY CRITICAL)
    if organization_id:
        from uuid import UUID

        query = query.filter(models.Token.organization_id == UUID(organization_id))

    # Get token by hash (O(1) with index)
    token = query.first()

    # Optional: Verify the decrypted token matches (defense in depth)
    # This protects against the unlikely case of hash collisions
    if token and token.token != token_value:
        # Hash collision detected - this should be extremely rare

        logger.warning(f"Token hash collision detected for token_id={token.id}")
        return None

    return token
