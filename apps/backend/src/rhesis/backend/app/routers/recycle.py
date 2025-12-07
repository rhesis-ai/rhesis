"""
Recycle bin management endpoints for soft-deleted records.

These endpoints allow superusers to:
- View soft-deleted records in the recycle bin
- Restore soft-deleted records from the recycle bin
- Permanently delete records (empty recycle bin)
"""

from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.services import recycle as recycle_service
from rhesis.backend.app.utils.crud_utils import (
    get_deleted_items,
    hard_delete_item,
)
from rhesis.backend.logging import logger

router = APIRouter(prefix="/recycle", tags=["recycle"])


def require_superuser(current_user: models.User):
    """Check if the current user is a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can access this endpoint")


def get_all_models() -> Dict[str, type]:
    """
    Automatically discover all SQLAlchemy models that inherit from Base.

    Returns:
        Dictionary mapping lowercase model names to model classes
    """
    model_map = {}

    # Get all subclasses of Base (all models)
    for mapper in Base.registry.mappers:
        model_class = mapper.class_
        # Use the table name as the key (already lowercase)
        table_name = model_class.__tablename__
        model_map[table_name] = model_class

    return model_map


def get_model_by_name(model_name: str) -> type:
    """
    Get a model class by its name.

    Args:
        model_name: Name of the model (table name)

    Returns:
        Model class

    Raises:
        HTTPException: If model not found
    """
    model_map = get_all_models()
    model = model_map.get(model_name.lower())

    if not model:
        available_models = sorted(model_map.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: {model_name}. Available models: {', '.join(available_models)}",
        )

    return model


@router.get("/models")
def list_available_models(
    current_user: models.User = Depends(require_current_user_or_token),
    db: Session = Depends(get_tenant_db_session),
):
    """
    List all available models that can be managed.

    Returns:
        List of model names and their details
    """
    model_map = get_all_models()

    model_info = []
    for table_name, model_class in sorted(model_map.items()):
        # Get model metadata
        mapper = inspect(model_class)

        model_info.append(
            {
                "name": table_name,
                "class_name": model_class.__name__,
                "has_organization_id": hasattr(model_class, "organization_id"),
                "has_user_id": hasattr(model_class, "user_id"),
                "columns": [col.name for col in mapper.columns],
            }
        )

    return {"count": len(model_info), "models": model_info}


@router.get("/{model_name}")
def get_recycled_records(
    model_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_tenant_db_session),
    current_user: models.User = Depends(require_current_user_or_token),
    tenant_context=Depends(get_tenant_context),
):
    """
    Get soft-deleted records in the recycle bin for a specific model.

    Users can view deleted records from their organization.

    Args:
        model_name: Name of the model (e.g., 'user', 'test', 'project')
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of soft-deleted records
    """
    model = get_model_by_name(model_name)
    organization_id, user_id = tenant_context

    # Check if model supports organization filtering
    org_id = None
    if hasattr(model, "organization_id"):
        org_id = organization_id

    deleted_items = get_deleted_items(db, model, skip=skip, limit=limit, organization_id=org_id)

    return {
        "model": model_name,
        "count": len(deleted_items),
        "items": deleted_items,
        "has_more": len(deleted_items) == limit,
    }


@router.post("/{model_name}/{item_id}/restore")
def restore_from_recycle_bin(
    model_name: str,
    item_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: models.User = Depends(require_current_user_or_token),
    tenant_context=Depends(get_tenant_context),
):
    """
    Restore a soft-deleted record from the recycle bin.

    This endpoint uses cascade-aware restoration. For example, restoring a
    test_run will automatically restore all its associated test_results.

    Users can restore deleted records from their organization.

    Args:
        model_name: Name of the model
        item_id: ID of the record to restore

    Returns:
        Restored record with cascade information
    """
    model = get_model_by_name(model_name)
    organization_id, user_id = tenant_context

    org_id = None
    if hasattr(model, "organization_id"):
        org_id = organization_id

    # Use cascade-aware restoration from service layer
    restored_item = recycle_service.restore_item_with_cascade(
        db, model, item_id, organization_id=org_id
    )

    if not restored_item:
        raise HTTPException(
            status_code=404, detail=f"{model_name} not found in recycle bin or already active"
        )

    logger.info(f"Restored {model_name} {item_id} from recycle bin by user {current_user.email}")

    return {
        "message": f"{model_name} restored successfully from recycle bin",
        "item": restored_item,
    }


@router.delete("/empty/{model_name}")
def empty_recycle_bin_for_model(
    model_name: str,
    confirm: bool = Query(False, description="Must be true to confirm"),
    db: Session = Depends(get_tenant_db_session),
    current_user: models.User = Depends(require_current_user_or_token),
    tenant_context=Depends(get_tenant_context),
):
    """
    Empty the recycle bin for a specific model - permanently delete ALL soft-deleted records.

    WARNING: This action cannot be undone! All soft-deleted records will be
    permanently removed from the database.

    Args:
        model_name: Name of the model
        confirm: Must be true to confirm permanent deletion

    Returns:
        Count of permanently deleted records
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Must set confirm=true to empty recycle bin")

    model = get_model_by_name(model_name)
    organization_id, user_id = tenant_context

    org_id = None
    if hasattr(model, "organization_id"):
        org_id = organization_id

    # Get all deleted items using QueryBuilder directly to bypass pagination limits
    from rhesis.backend.app.utils.model_utils import QueryBuilder

    deleted_items = (
        QueryBuilder(db, model)
        .only_deleted()
        .with_organization_filter(org_id)
        .with_visibility_filter()
        .all()
    )

    deleted_count = 0
    failed_count = 0

    for item in deleted_items:
        try:
            if hard_delete_item(db, model, item.id, organization_id=org_id):
                deleted_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Error permanently deleting {model_name} {item.id}: {e}")
            failed_count += 1

    logger.warning(
        f"EMPTY RECYCLE BIN: {model_name} - {deleted_count} permanently deleted, "
        f"{failed_count} failed by user {current_user.email}"
    )

    return {
        "message": f"Recycle bin emptied for {model_name}",
        "permanently_deleted": deleted_count,
        "failed": failed_count,
        "warning": "This action cannot be undone",
    }


@router.delete("/{model_name}/{item_id}")
def permanently_delete_record(
    model_name: str,
    item_id: UUID,
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    db: Session = Depends(get_tenant_db_session),
    current_user: models.User = Depends(require_current_user_or_token),
    tenant_context=Depends(get_tenant_context),
):
    """
    Permanently delete a record from the recycle bin (admin only).

    WARNING: This action cannot be undone! The record will be permanently
    removed from the database.

    Args:
        model_name: Name of the model
        item_id: ID of the record to delete
        confirm: Must be true to confirm permanent deletion

    Returns:
        Success message
    """
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must set confirm=true to permanently delete records"
        )

    model = get_model_by_name(model_name)
    organization_id, user_id = tenant_context

    org_id = None
    if hasattr(model, "organization_id"):
        org_id = organization_id

    success = hard_delete_item(db, model, item_id, organization_id=org_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"{model_name} not found in recycle bin")

    logger.warning(
        f"PERMANENT DELETE: {model_name} {item_id} from recycle bin by user {current_user.email}"
    )

    return {
        "message": f"{model_name} permanently deleted from recycle bin",
        "item_id": str(item_id),
        "warning": "This action cannot be undone",
    }


@router.get("/stats/counts")
def get_recycle_bin_counts(
    db: Session = Depends(get_tenant_db_session),
    current_user: models.User = Depends(require_current_user_or_token),
    tenant_context=Depends(get_tenant_context),
):
    """
    Get counts of soft-deleted records in the recycle bin for all models.

    Users can see counts for deleted records in their organization.
    This can take a while for large databases as it queries every table.

    Returns:
        Dictionary with counts per model
    """
    model_map = get_all_models()
    counts = {}
    organization_id, user_id = tenant_context

    for table_name, model in sorted(model_map.items()):
        try:
            # Check if model supports organization filtering
            org_id = None
            if hasattr(model, "organization_id"):
                org_id = organization_id

            # Count deleted items using QueryBuilder directly to avoid pagination limits
            from rhesis.backend.app.utils.model_utils import QueryBuilder

            count = (
                QueryBuilder(db, model)
                .only_deleted()
                .with_organization_filter(org_id)
                .with_visibility_filter()
                .count()
            )

            # Only include models that have deleted records
            if count > 0:
                counts[table_name] = {"count": count, "class_name": model.__name__}
        except Exception as e:
            logger.error(f"Error counting recycled items for {table_name}: {e}")
            counts[table_name] = {"count": "error", "error": str(e)}

    return {
        "total_models_with_deleted": len(
            [c for c in counts.values() if isinstance(c.get("count"), int) and c["count"] > 0]
        ),
        "counts": counts,
    }


@router.post("/bulk-restore/{model_name}")
def bulk_restore_from_recycle_bin(
    model_name: str,
    item_ids: List[UUID],
    db: Session = Depends(get_tenant_db_session),
    current_user: models.User = Depends(require_current_user_or_token),
    tenant_context=Depends(get_tenant_context),
):
    """
    Restore multiple soft-deleted records from the recycle bin at once.

    Uses cascade-aware restoration - each item and its related entities are restored.

    Users can restore deleted records from their organization.

    Args:
        model_name: Name of the model
        item_ids: List of IDs to restore

    Returns:
        Summary of restoration results
    """

    if not item_ids:
        raise HTTPException(status_code=400, detail="No item IDs provided")

    if len(item_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 items can be restored at once")

    model = get_model_by_name(model_name)
    organization_id, user_id = tenant_context

    org_id = None
    if hasattr(model, "organization_id"):
        org_id = organization_id

    # Use cascade-aware bulk restoration from service layer
    results = recycle_service.bulk_restore_with_cascade(db, model, item_ids, organization_id=org_id)

    logger.info(
        f"Bulk restore {model_name} from recycle bin: {len(results['restored'])} restored, "
        f"{len(results['failed'])} failed, {len(results['not_found'])} not found "
        f"by user {current_user.email}"
    )

    return {
        "message": f"Bulk restore completed for {model_name}",
        "summary": {
            "total_requested": len(item_ids),
            "restored": len(results["restored"]),
            "failed": len(results["failed"]),
            "not_found": len(results["not_found"]),
        },
        "results": results,
    }
