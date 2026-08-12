"""CRUD operations for file attachments.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

A ``File`` is always an attachment to something else — it carries a generic
``(entity_id, entity_type)`` pair rather than a real foreign key, so every read here
filters on both. ``entity_type`` is stored as a plain string; ``create_file`` unwraps a
passed ``EntityType`` enum member to its ``.value`` first, because callers hand it either
form and a bare enum would be written as ``EntityType.TEST`` instead of ``"Test"``.

``link_file_to_entity`` is the one function that bypasses ``QueryBuilder`` and the shared
crud helpers. Span storage creates a ``File`` before the ``Trace`` it belongs to exists,
then re-points it once the trace is written, so this is a targeted metadata update that
commits on its own — it moves no bytes and touches no storage.

``get_entity_files_total_size`` and ``get_entity_files_max_position`` are raw aggregates
(quota check and next-position lookup for the upload endpoint), so they filter
``deleted_at`` and ``organization_id`` by hand instead of going through ``QueryBuilder``.
"""

import uuid
from typing import List, Optional, Union

from sqlalchemy import func
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder


def create_file(
    db: Session,
    file_data: Union[schemas.FileCreate, dict],
    organization_id: str = None,
    user_id: str = None,
) -> models.File:
    """Create a file record."""
    if isinstance(file_data, dict):
        file_data = schemas.FileCreate(**file_data)

    if hasattr(file_data, "entity_type") and hasattr(file_data.entity_type, "value"):
        file_data.entity_type = file_data.entity_type.value

    return create_item(db, models.File, file_data, organization_id, user_id)


def get_file(
    db: Session,
    file_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.File]:
    """Get file metadata (content is deferred, not loaded)."""
    return get_item(db, models.File, file_id, organization_id, user_id)


def link_file_to_entity(
    db: Session,
    file_id: uuid.UUID,
    entity_id: uuid.UUID,
    entity_type: str,
) -> Optional[models.File]:
    """Update a File row to link it to a new entity (e.g. a Trace after span storage).

    Pure metadata update — no bytes, no storage writes.
    Returns the updated File, or None if not found.
    """
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if not db_file:
        return None
    db_file.entity_id = entity_id
    db_file.entity_type = entity_type
    db.commit()
    db.refresh(db_file)
    return db_file


def get_files_for_entity(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    organization_id: str = None,
    user_id: str = None,
    skip: int = 0,
    limit: int = 100,
) -> List[models.File]:
    """Get all files for a specific entity (content deferred)."""
    return (
        QueryBuilder(db, models.File)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(
                models.File.entity_id == entity_id,
                models.File.entity_type == entity_type,
            )
        )
        .with_pagination(skip, limit)
        .with_sorting("position", "asc")
        .all()
    )


def get_entity_files_total_size(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    organization_id: str = None,
) -> int:
    """Get total size in bytes of all files for an entity."""
    query = db.query(func.coalesce(func.sum(models.File.size_bytes), 0)).filter(
        models.File.entity_id == entity_id,
        models.File.entity_type == entity_type,
        models.File.deleted_at.is_(None),
    )
    if organization_id:
        query = query.filter(models.File.organization_id == organization_id)
    return query.scalar()


def get_entity_files_max_position(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    organization_id: str = None,
) -> int:
    """Get the maximum position of files for an entity, or -1 if none exist."""
    query = db.query(func.coalesce(func.max(models.File.position), -1)).filter(
        models.File.entity_id == entity_id,
        models.File.entity_type == entity_type,
        models.File.deleted_at.is_(None),
    )
    if organization_id:
        query = query.filter(models.File.organization_id == organization_id)
    return query.scalar()


def delete_file(
    db: Session,
    file_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.File]:
    """Soft-delete a file."""
    return delete_item(db, models.File, file_id, organization_id, user_id)
