"""SDK metric synchronization logic."""

import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
from rhesis.backend.app.utils.query_utils import QueryBuilder
from rhesis.backend.app.utils.status import get_or_create_status
from rhesis.sdk.connector.registry import DEFAULT_METRIC_PARAMS

logger = logging.getLogger(__name__)

SDK_BACKEND_TYPE_NAME = "BackendType"
SDK_BACKEND_TYPE_VALUE = "sdk"


def sync_sdk_metrics(
    db: Session,
    metrics_data: List[Dict[str, Any]],
    organization_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Sync SDK metrics - create/update/mark inactive as needed.

    Creates one Metric row per metric registered by the SDK.

    Args:
        db: Database session
        metrics_data: List of metric metadata from SDK
        organization_id: Organization ID
        user_id: User ID

    Returns:
        Dict with sync statistics
    """
    logger.info(f"=== SYNC SDK METRICS === count={len(metrics_data)}")

    backend_type = get_or_create_type_lookup(
        db=db,
        type_name=SDK_BACKEND_TYPE_NAME,
        type_value=SDK_BACKEND_TYPE_VALUE,
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )

    existing_by_name = _get_existing_sdk_metrics(db, organization_id, backend_type.id)

    registered_names: set[str] = set()
    stats: Dict[str, Any] = {
        "created": 0,
        "updated": 0,
        "marked_inactive": 0,
        "errors": [],
    }

    for metric_data in metrics_data:
        metric_name = metric_data.get("name")
        if not metric_name:
            logger.warning(f"Skipping metric without name: {metric_data}")
            continue

        registered_names.add(metric_name)
        metadata = metric_data.get("metadata", {})

        try:
            if metric_name in existing_by_name:
                _update_existing_metric(
                    existing_by_name[metric_name],
                    metric_data,
                    metadata,
                )
                stats["updated"] += 1
            else:
                _create_new_metric(
                    db,
                    metric_name,
                    metric_data,
                    metadata,
                    organization_id,
                    user_id,
                    backend_type,
                )
                stats["created"] += 1

        except Exception as e:
            logger.error(
                f"Error syncing metric {metric_name}: {e}",
                exc_info=True,
            )
            stats["errors"].append({"metric": metric_name, "error": str(e)})

    _mark_inactive_metrics(
        db,
        existing_by_name,
        registered_names,
        organization_id,
        user_id,
        stats,
    )

    db.flush()
    logger.info(f"SDK metric sync complete: {stats}")
    return stats


def _empty_stats(error_msg: str) -> Dict[str, Any]:
    return {
        "created": 0,
        "updated": 0,
        "marked_inactive": 0,
        "errors": [error_msg],
    }


def _get_existing_sdk_metrics(
    db: Session,
    organization_id: str,
    backend_type_id,
) -> Dict[str, models.Metric]:
    """Get existing SDK metrics for this org keyed by name."""
    query_builder = QueryBuilder(db, models.Metric).with_organization_filter(organization_id)
    query_builder.query = query_builder.query.filter(
        models.Metric.backend_type_id == backend_type_id,
    )
    existing = query_builder.all()

    result = {}
    for m in existing:
        sdk_conn = _get_sdk_connection(m)
        if sdk_conn:
            result[m.name] = m

    logger.info(f"Found {len(result)} existing SDK metrics: {list(result.keys())}")
    return result


def _get_sdk_connection(metric: models.Metric) -> Dict[str, Any] | None:
    """Extract sdk_connection from metric's evaluation_examples JSON."""
    if not metric.evaluation_examples:
        return None
    try:
        import json

        data = json.loads(metric.evaluation_examples)
        return data.get("sdk_connection")
    except (json.JSONDecodeError, TypeError):
        return None


def _set_sdk_connection(
    metric: models.Metric,
    metric_name: str,
    accepted_params: List[str],
) -> None:
    """Store sdk_connection in metric's evaluation_examples as JSON."""
    import json

    data = {}
    if metric.evaluation_examples:
        try:
            data = json.loads(metric.evaluation_examples)
        except (json.JSONDecodeError, TypeError):
            data = {}

    data["sdk_connection"] = {
        "metric_name": metric_name,
        "accepted_params": accepted_params,
        "last_registered": datetime.utcnow().isoformat(),
    }
    metric.evaluation_examples = json.dumps(data)


def _update_existing_metric(
    metric: models.Metric,
    metric_data: Dict[str, Any],
    metadata: Dict[str, Any],
) -> None:
    """Update an existing SDK metric row."""
    description = metadata.get("description", "")
    if description:
        metric.description = description

    score_type = metadata.get("score_type", "numeric")
    metric.score_type = score_type

    accepted_params = metric_data.get("parameters", list(DEFAULT_METRIC_PARAMS))
    metric.ground_truth_required = "expected_output" in accepted_params
    metric.context_required = "context" in accepted_params

    _set_sdk_connection(metric, metric.name, accepted_params)

    logger.info(f"Updated SDK metric: {metric.name}")


def _create_new_metric(
    db: Session,
    metric_name: str,
    metric_data: Dict[str, Any],
    metadata: Dict[str, Any],
    organization_id: str,
    user_id: str,
    backend_type,
) -> models.Metric:
    """Create a new Metric row for an SDK metric."""
    description = metadata.get("description") or f"SDK metric: {metric_name}"
    score_type = metadata.get("score_type", "numeric")
    accepted_params = metric_data.get("parameters", list(DEFAULT_METRIC_PARAMS))

    active_status = get_or_create_status(db, "Active", "General", organization_id, user_id)

    metric_type = get_or_create_type_lookup(
        db=db,
        type_name="MetricType",
        type_value="custom-code",
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )

    from uuid import UUID

    metric = models.Metric(
        name=metric_name,
        description=description,
        evaluation_prompt=f"SDK metric executed on client side: {metric_name}",
        score_type=score_type,
        class_name=metric_name,
        backend_type_id=backend_type.id,
        metric_type_id=metric_type.id if metric_type else None,
        status_id=active_status.id if active_status else None,
        ground_truth_required="expected_output" in accepted_params,
        context_required="context" in accepted_params,
        metric_scope=["Single-Turn"],
        organization_id=UUID(organization_id),
        user_id=UUID(user_id),
    )

    _set_sdk_connection(metric, metric_name, accepted_params)

    db.add(metric)
    db.flush()

    logger.info(f"Created SDK metric: {metric_name} (id={metric.id})")
    return metric


def _mark_inactive_metrics(
    db: Session,
    existing_by_name: Dict[str, models.Metric],
    registered_names: set[str],
    organization_id: str,
    user_id: str,
    stats: Dict[str, Any],
) -> None:
    """Mark metrics that are no longer registered as inactive."""
    for name, metric in existing_by_name.items():
        if name not in registered_names:
            try:
                inactive_status = get_or_create_status(
                    db, "Inactive", "General", organization_id, user_id
                )
                if inactive_status:
                    metric.status_id = inactive_status.id
                    stats["marked_inactive"] += 1
                    logger.info(f"Marked SDK metric '{name}' inactive")
            except Exception as e:
                logger.error(
                    f"Error marking metric '{name}' inactive: {e}",
                    exc_info=True,
                )
                stats["errors"].append({"metric": name, "error": str(e)})
