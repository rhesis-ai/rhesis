"""
Generic cascade for soft delete and restore.

Cascades follow the configuration in config/cascade_config.py, so a new
cascade needs no code here. Each child relationship gets one bulk UPDATE for
the whole batch of parents (no objects are loaded), inside the caller's
transaction, filtered to the caller's organization.

Usage:
    cascade_soft_delete(db, models.TestRun, test_run_id, org_id)
    cascade_restore(db, models.TestRun, test_run_id, org_id)

None of these functions commit; the caller owns the transaction.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Type
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.config.cascade_config import get_cascade_relationships
from rhesis.backend.app.utils.crud_utils import bulk_update

logger = logging.getLogger(__name__)


def _child_criteria(rel, parent_ids: List[UUID], organization_id: Optional[str]) -> List[Any]:
    child = rel.child_model
    criteria = [getattr(child, rel.foreign_key).in_(parent_ids)]
    # Extra filters narrow polymorphic relationships (e.g. entity_type = "Test").
    criteria += [getattr(child, key) == value for key, value in rel.extra_filters.items()]
    if organization_id and hasattr(child, "organization_id"):
        criteria.append(child.organization_id == organization_id)
    return criteria


def cascade_soft_delete_bulk(
    db: Session,
    parent_model: Type,
    parent_ids: List[UUID],
    organization_id: Optional[str] = None,
) -> int:
    """Soft delete the configured children of every parent in ``parent_ids``.

    Returns the number of child rows soft deleted across all relationships.
    """
    if not parent_ids:
        return 0

    total = 0
    for rel in get_cascade_relationships(parent_model):
        if not rel.cascade_delete:
            continue
        now = datetime.now(timezone.utc)
        ids = bulk_update(
            db,
            rel.child_model,
            _child_criteria(rel, parent_ids, organization_id),
            {"deleted_at": now, "updated_at": now},
            synchronize_session=False,
        )
        total += len(ids)
        if ids:
            logger.info(
                f"Cascade soft delete: {len(ids)} {rel.child_model.__name__} "
                f"records for {len(parent_ids)} {parent_model.__name__} row(s)"
            )
    return total


def cascade_soft_delete(
    db: Session,
    parent_model: Type,
    parent_id: UUID,
    organization_id: Optional[str] = None,
) -> int:
    """Soft delete the configured children of one parent."""
    return cascade_soft_delete_bulk(db, parent_model, [parent_id], organization_id)


def cascade_restore(
    db: Session,
    parent_model: Type,
    parent_id: UUID,
    organization_id: Optional[str] = None,
) -> int:
    """Restore the soft-deleted configured children of one parent.

    Returns the number of child rows restored across all relationships.
    """
    total = 0
    for rel in get_cascade_relationships(parent_model):
        if not rel.cascade_restore:
            continue
        criteria = _child_criteria(rel, [parent_id], organization_id)
        criteria.append(rel.child_model.deleted_at.isnot(None))
        ids = bulk_update(
            db,
            rel.child_model,
            criteria,
            {"deleted_at": None, "updated_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        total += len(ids)
        if ids:
            logger.info(
                f"Cascade restore: {len(ids)} {rel.child_model.__name__} "
                f"records for {parent_model.__name__} {parent_id}"
            )
    return total
