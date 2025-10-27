"""
Recycle bin service for managing soft-deleted records.

This service provides convenience wrappers for restore operations.
Cascade restoration is handled automatically by restore_item() based on
configuration in config/cascade_config.py.

This service handles:
- Generic item restoration with automatic cascading
- Bulk operations with proper error handling
"""

from typing import Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.utils.crud_utils import restore_item
from rhesis.backend.logging import logger

T = TypeVar("T")


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
