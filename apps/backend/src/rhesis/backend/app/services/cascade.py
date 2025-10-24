"""
Generic Cascade Service for Soft Delete and Restore Operations

This service provides automatic cascading of soft delete and restore operations
based on the configuration defined in config/cascade_config.py.

Key Features:
- Configuration-driven: No code changes needed for new cascades
- Efficient: Uses bulk UPDATE queries (no object fetching)
- Transactional: Operations are atomic within the calling transaction
- Organization-aware: Respects tenant isolation

Usage:
    # Automatically cascade based on configuration
    cascade_soft_delete(db, models.TestRun, test_run_id, org_id)
    cascade_restore(db, models.TestRun, test_run_id, org_id)
"""

from datetime import datetime
from typing import Optional, Type
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.config.cascade_config import get_cascade_relationships
from rhesis.backend.logging import logger


def cascade_soft_delete(
    db: Session,
    parent_model: Type,
    parent_id: UUID,
    organization_id: Optional[str] = None,
) -> int:
    """
    Cascade soft delete to all configured child relationships.

    Automatically finds and soft deletes all child records based on the
    CASCADE_RELATIONSHIPS configuration. Uses efficient bulk UPDATE queries.

    Args:
        db: Database session
        parent_model: The parent model class (e.g., models.TestRun)
        parent_id: The ID of the parent record being deleted
        organization_id: Optional organization ID for tenant filtering

    Returns:
        Total number of child records soft deleted across all relationships

    Note:
        This function does NOT commit - the caller is responsible for transaction management.
    """
    total_deleted = 0
    relationships = get_cascade_relationships(parent_model)

    for rel in relationships:
        if not rel.cascade_delete:
            continue

        try:
            # Build query for child records
            query = db.query(rel.child_model).filter(
                getattr(rel.child_model, rel.foreign_key) == parent_id
            )

            # Apply organization filter if the child model supports it
            if organization_id and hasattr(rel.child_model, "organization_id"):
                query = query.filter(rel.child_model.organization_id == organization_id)

            # Bulk soft delete using UPDATE
            # synchronize_session=False is safe since we're not using these objects after
            count = query.update({"deleted_at": datetime.utcnow()}, synchronize_session=False)

            total_deleted += count

            if count > 0:
                logger.info(
                    f"Cascade soft delete: {count} {rel.child_model.__name__} "
                    f"records for {parent_model.__name__} {parent_id}"
                )

        except Exception as e:
            logger.error(f"Error cascading soft delete to {rel.child_model.__name__}: {e}")
            raise

    return total_deleted


def cascade_restore(
    db: Session,
    parent_model: Type,
    parent_id: UUID,
    organization_id: Optional[str] = None,
) -> int:
    """
    Cascade restore to all configured child relationships.

    Automatically finds and restores all soft-deleted child records based on the
    CASCADE_RELATIONSHIPS configuration. Uses efficient bulk UPDATE queries.

    Args:
        db: Database session
        parent_model: The parent model class (e.g., models.TestRun)
        parent_id: The ID of the parent record being restored
        organization_id: Optional organization ID for tenant filtering

    Returns:
        Total number of child records restored across all relationships

    Note:
        This function does NOT commit - the caller is responsible for transaction management.
    """
    total_restored = 0
    relationships = get_cascade_relationships(parent_model)

    for rel in relationships:
        if not rel.cascade_restore:
            continue

        try:
            # Build query for soft-deleted child records
            query = db.query(rel.child_model).filter(
                getattr(rel.child_model, rel.foreign_key) == parent_id,
                rel.child_model.deleted_at.isnot(None),  # Only restore deleted ones
            )

            # Apply organization filter if the child model supports it
            if organization_id and hasattr(rel.child_model, "organization_id"):
                query = query.filter(rel.child_model.organization_id == organization_id)

            # Bulk restore using UPDATE
            # synchronize_session=False is safe since we're not using these objects after
            count = query.update({"deleted_at": None}, synchronize_session=False)

            total_restored += count

            if count > 0:
                logger.info(
                    f"Cascade restore: {count} {rel.child_model.__name__} "
                    f"records for {parent_model.__name__} {parent_id}"
                )

        except Exception as e:
            logger.error(f"Error cascading restore to {rel.child_model.__name__}: {e}")
            raise

    return total_restored
