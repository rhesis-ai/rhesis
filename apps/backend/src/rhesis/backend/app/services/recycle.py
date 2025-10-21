"""
Recycle bin service for managing soft-deleted records with cascade awareness.

This service handles:
- Generic item restoration
- Model-specific cascade restoration (e.g., test_run -> test_results)
- Bulk operations with proper transaction management
"""

from datetime import datetime
from typing import Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import models
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
    Restore a soft-deleted item and handle model-specific cascade restoration.
    
    This function:
    1. Restores the primary item
    2. Checks if the model requires cascade restoration
    3. Restores any related child entities that were soft-deleted
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        item_id: ID of the item to restore
        organization_id: Optional organization ID for tenant filtering
    
    Returns:
        Restored item or None if not found
    """
    # First, restore the primary item
    restored_item = restore_item(db, model, item_id, organization_id)
    
    if not restored_item:
        return None
    
    # Handle model-specific cascade restoration
    if model == models.TestRun:
        _restore_test_run_cascade(db, item_id, organization_id)
        logger.info(f"Restored test_run {item_id} with cascade to test_results")
    
    # Add more model-specific cascades here as needed
    # elif model == models.AnotherModel:
    #     _restore_another_model_cascade(db, item_id, organization_id)
    
    return restored_item


def _restore_test_run_cascade(
    db: Session,
    test_run_id: UUID,
    organization_id: Optional[str] = None,
) -> int:
    """
    Restore all soft-deleted test results associated with a test run.
    
    Uses a bulk UPDATE for efficiency, similar to cascade deletion.
    
    Args:
        db: Database session
        test_run_id: ID of the test run
        organization_id: Optional organization ID for security filtering
    
    Returns:
        Number of test results restored
    """
    try:
        # Build query for soft-deleted test results belonging to this test run
        query = db.query(models.TestResult).filter(
            models.TestResult.test_run_id == test_run_id,
            models.TestResult.deleted_at.isnot(None)  # Only restore deleted ones
        )
        
        # Apply organization filter for security
        if organization_id:
            query = query.filter(models.TestResult.organization_id == organization_id)
        
        # Bulk UPDATE to restore all matching test results
        # synchronize_session=False is safe since we're not using these objects after
        count = query.update(
            {"deleted_at": None},
            synchronize_session=False
        )
        
        # Commit the restoration
        db.commit()
        
        logger.info(f"Restored {count} test_results for test_run {test_run_id}")
        return count
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error restoring test_results for test_run {test_run_id}: {e}")
        raise


def bulk_restore_with_cascade(
    db: Session,
    model: Type[T],
    item_ids: list[UUID],
    organization_id: Optional[str] = None,
) -> dict:
    """
    Restore multiple items with cascade awareness.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        item_ids: List of item IDs to restore
        organization_id: Optional organization ID for tenant filtering
    
    Returns:
        Dictionary with restoration results
    """
    results = {
        "restored": [],
        "failed": [],
        "not_found": []
    }
    
    for item_id in item_ids:
        try:
            restored_item = restore_item_with_cascade(
                db, model, item_id, organization_id
            )
            if restored_item:
                results["restored"].append(str(item_id))
            else:
                results["not_found"].append(str(item_id))
        except Exception as e:
            logger.error(f"Error restoring {model.__name__} {item_id}: {e}")
            results["failed"].append({
                "id": str(item_id),
                "error": str(e)
            })
    
    return results

