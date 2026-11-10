"""
Recycle bin service for managing soft-deleted records.

This service provides convenience wrappers for restore operations.
Cascade restoration is handled automatically by restore_item() based on
configuration in config/cascade_config.py.

This service handles:
- Generic item restoration with automatic cascading
- Bulk operations with proper error handling
"""

import logging
import re
from functools import lru_cache
from typing import Any, Dict, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from rhesis.backend.app.utils.crud_utils import restore_item
from rhesis.backend.app.utils.encryption import EncryptedString

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Backstop for secret columns that are neither encrypted nor declared in the
# model's audit policy (e.g. refresh_token.token_hash on an unaudited model).
_SECRET_NAME_PATTERN = re.compile(r"password|secret|credential|api_key|token_hash")


@lru_cache(maxsize=None)
def secret_column_keys(model: type) -> frozenset[str]:
    """Attribute keys of *model* that must never leave the API in recycle-bin responses.

    A column is secret when it is an ``EncryptedString``, is listed in the model's
    ``__audit__.secret``, or its name matches ``_SECRET_NAME_PATTERN``.
    """
    declared = set(getattr(getattr(model, "__audit__", None), "secret", ()))
    return frozenset(
        prop.key
        for prop in inspect(model).column_attrs
        for column in prop.columns[:1]
        if isinstance(column.type, EncryptedString)
        or column.name in declared
        or _SECRET_NAME_PATTERN.search(column.name)
    )


def serialize_recycled_item(item: Any) -> Dict[str, Any]:
    """Column values of a recycle-bin row, minus secret columns and relationships."""
    model = type(item)
    hidden = secret_column_keys(model)
    return {
        prop.key: getattr(item, prop.key)
        for prop in inspect(model).column_attrs
        if prop.key not in hidden
    }


def restore_item_with_cascade(
    db: Session,
    model: Type[T],
    item_id: UUID,
    organization_id: Optional[str] = None,
) -> Optional[T]:
    """
    Restore a soft-deleted item.

    Cascade restoration happens automatically based on configuration
    in config/cascade_config.py. No model-specific logic needed.

    Args:
        db: Database session
        model: SQLAlchemy model class
        item_id: ID of the item to restore
        organization_id: Optional organization ID for tenant filtering

    Returns:
        Restored item or None if not found
    """
    # restore_item() now automatically handles cascades based on config
    return restore_item(db, model, item_id, organization_id)


def bulk_restore_with_cascade(
    db: Session,
    model: Type[T],
    item_ids: list[UUID],
    organization_id: Optional[str] = None,
) -> dict:
    """
    Restore multiple items with automatic cascade.

    Each item is restored with automatic cascade based on configuration.

    Args:
        db: Database session
        model: SQLAlchemy model class
        item_ids: List of item IDs to restore
        organization_id: Optional organization ID for tenant filtering

    Returns:
        Dictionary with restoration results
    """
    results = {"restored": [], "failed": [], "not_found": []}

    for item_id in item_ids:
        try:
            restored_item = restore_item_with_cascade(db, model, item_id, organization_id)
            if restored_item:
                results["restored"].append(str(item_id))
            else:
                results["not_found"].append(str(item_id))
        except Exception as e:
            logger.error(f"Error restoring {model.__name__} {item_id}: {e}")
            results["failed"].append({"id": str(item_id), "error": str(e)})

    return results
