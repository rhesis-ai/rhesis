"""CRUD operations for embeddings.

An ``Embedding`` row stores its vector in a dimension-specific column
(``embedding_768``, ``embedding_1536``, ...) because pgvector needs a fixed width per
column. The ``ck_embedding_exactly_one_embedding`` constraint requires exactly one of them
to be set, so ``create_embedding`` reads the dimension out of ``embedding_config`` and
writes the vector into the matching column instead of passing it straight through.

Re-embedding is a dedup-then-supersede pair rather than an update. ``get_embedding_by_hash``
looks for a row matching the same entity, config hash and text hash, so unchanged text is
not embedded twice; ``mark_embeddings_stale`` bulk-flips the previous active rows to stale
and returns how many it touched, keeping the old vectors around instead of deleting them.
"""

import uuid
from typing import List, Optional
from uuid import UUID

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


def get_embedding(
    db: Session,
    embedding_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Embedding]:
    """Get a single embedding by ID."""
    return get_item(db, models.Embedding, embedding_id, organization_id, user_id)


def get_embeddings(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.Embedding]:
    """Get multiple embeddings."""
    return get_items(
        db,
        models.Embedding,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def get_active_embeddings_for_entities(
    db: Session,
    entity_ids: List[UUID],
    entity_type: str,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.Embedding]:
    from rhesis.backend.app.models.enums import EmbeddingStatus
    from rhesis.backend.app.models.status import Status

    return (
        QueryBuilder(db, models.Embedding)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(
                models.Embedding.entity_id.in_(entity_ids),
                models.Embedding.entity_type == entity_type,
                models.Embedding.status.has(Status.name == EmbeddingStatus.ACTIVE.value),
            )
        )
        .all()
    )


def create_embedding(
    db: Session,
    embedding: schemas.EmbeddingCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.Embedding:
    """Create embedding."""
    embedding_data = embedding.model_dump(exclude={"embedding"})

    # The database constraint ck_embedding_exactly_one_embedding requires
    # exactly one dimension column to be set. Set it before insert.
    if embedding.embedding is not None and "dimension" in embedding.embedding_config:
        dim = embedding.embedding_config["dimension"]
        dim_field = f"embedding_{dim}"
        embedding_data[dim_field] = embedding.embedding

    return create_item(db, models.Embedding, embedding_data, organization_id, user_id)


def update_embedding(
    db: Session,
    embedding_id: uuid.UUID,
    embedding: schemas.EmbeddingUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Embedding]:
    """Update embedding."""
    return update_item(db, models.Embedding, embedding_id, embedding, organization_id, user_id)


def delete_embedding(
    db: Session, embedding_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Embedding]:
    """Delete embedding."""
    return delete_item(db, models.Embedding, embedding_id, organization_id, user_id)


def get_embedding_by_hash(
    db: Session,
    entity_id: str,
    entity_type: str,
    organization_id: str,
    config_hash: str,
    text_hash: str,
    status_id: uuid.UUID,
) -> Optional[models.Embedding]:
    """Find an exact matching embedding (deduplication)."""
    return (
        db.query(models.Embedding)
        .filter(
            models.Embedding.entity_id == entity_id,
            models.Embedding.entity_type == entity_type,
            models.Embedding.organization_id == organization_id,
            models.Embedding.config_hash == config_hash,
            models.Embedding.text_hash == text_hash,
            models.Embedding.status_id == status_id,
        )
        .first()
    )


def mark_embeddings_stale(
    db: Session,
    entity_id: str,
    entity_type: str,
    organization_id: str,
    active_status_id: uuid.UUID,
    stale_status_id: uuid.UUID,
) -> int:
    """Bulk update old active embeddings to stale."""
    return (
        db.query(models.Embedding)
        .filter(
            models.Embedding.entity_id == entity_id,
            models.Embedding.entity_type == entity_type,
            models.Embedding.organization_id == organization_id,
            models.Embedding.status_id == active_status_id,
        )
        .update({"status_id": stale_status_id})
    )
