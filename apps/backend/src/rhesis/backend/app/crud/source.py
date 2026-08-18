"""CRUD operations for sources and their chunks.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

``Source.content`` is a ``deferred()`` column on the model -- the full extracted text of a
document or web page, which no list or detail response returns. ``get_source`` and
``get_sources`` therefore leave it unloaded, and ``get_source_with_content`` exists as a
separate function that adds ``undefer(models.Source.content)`` for the few callers that do
need the text (chunking, test generation, the file-download endpoint). The two getters are
otherwise the same query, except that ``get_source_with_content`` lets the caller pass
``include_deleted`` through to ``_check_and_raise_if_deleted`` while ``get_source`` always
rejects soft-deleted rows.

``create_chunk`` lives here because a ``Chunk`` only exists as a piece of one source. It is
the only chunk helper with a caller (``ChunkingService``); the update/delete/get variants
were never used and were removed rather than carried over in the split.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

_SOURCE_RELATED_FIELDS = (
    include(models.Source.source_type),
    include(models.Source.user),
)


def get_source(
    db: Session,
    source_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Source]:
    """Get source.

    Note: Content field is deferred and will not be loaded unless explicitly requested.
    Use get_source_with_content() to load the content field.
    Relationships (source_type, user) are loaded for display.
    """
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.Source)
        .with_deleted()
        .with_related(*_SOURCE_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .filter_by_id(source_id)
    )
    return _check_and_raise_if_deleted(item, models.Source, source_id, False)


def get_source_with_content(
    db: Session,
    source_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
    include_deleted: bool = False,
) -> Optional[models.Source]:
    """Get source with content field explicitly loaded (a deferred column)."""
    from sqlalchemy.orm import undefer

    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.Source)
        .with_deleted()
        .with_related(*_SOURCE_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_custom_filter(lambda q: q.options(undefer(models.Source.content)))
        .filter_by_id(source_id)
    )
    return _check_and_raise_if_deleted(item, models.Source, source_id, include_deleted)


def get_sources(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Source]:
    """Get sources.

    Note: Content field is deferred and will not be loaded.
    Use get_source_with_content() for individual sources that need content.
    Relationships (source_type, user) are loaded for display.
    """
    return (
        QueryBuilder(db, models.Source)
        .with_related(*_SOURCE_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_source(
    db: Session, source: schemas.SourceCreate, organization_id: str = None, user_id: str = None
) -> models.Source:
    """Create source."""
    return create_item(db, models.Source, source, organization_id, user_id)


def update_source(
    db: Session,
    source_id: uuid.UUID,
    source: schemas.SourceUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Source]:
    """Update source."""
    return update_item(db, models.Source, source_id, source, organization_id, user_id)


def delete_source(
    db: Session, source_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Source]:
    """Delete source."""
    return delete_item(db, models.Source, source_id, organization_id, user_id)


def create_chunk(
    db: Session, chunk: schemas.ChunkCreate, organization_id: str = None, user_id: str = None
) -> models.Chunk:
    """Create chunk."""
    return create_item(db, models.Chunk, chunk, organization_id=organization_id, user_id=user_id)
