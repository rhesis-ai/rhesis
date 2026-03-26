from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.schemas.adaptive_testing import (
    AdaptiveSettingsEndpoint,
    AdaptiveSettingsMetric,
    AdaptiveSettingsResponse,
)

from .tests import _is_adaptive_test_set


def _get_default_endpoint_id_from_attributes(
    test_set: models.TestSet,
) -> Optional[UUID]:
    attrs = test_set.attributes or {}
    adaptive_settings = attrs.get("adaptive_settings") or {}
    raw_id = adaptive_settings.get("default_endpoint_id")
    if not raw_id:
        return None
    try:
        return UUID(str(raw_id))
    except (ValueError, TypeError):
        return None


def resolve_endpoint_id(
    test_set: models.TestSet,
    request_endpoint_id: Optional[UUID],
) -> str:
    if request_endpoint_id is not None:
        return str(request_endpoint_id)

    endpoint_id = _get_default_endpoint_id_from_attributes(test_set)
    if endpoint_id is None:
        raise ValueError("No endpoint specified and no default endpoint configured in settings")

    return str(endpoint_id)


def resolve_metric_names(
    test_set: models.TestSet,
    db: Session,
    organization_id: str,
    request_metric_names: Optional[List[str]],
) -> List[str]:
    # Kept for API symmetry with endpoint resolver usage from routers.
    _ = db, organization_id
    if request_metric_names:
        return request_metric_names

    metric_names = [metric.name for metric in (test_set.metrics or []) if metric.name]
    if not metric_names:
        raise ValueError("No metrics specified and no metrics configured in settings")

    return metric_names


def get_adaptive_settings(
    db: Session,
    test_set: models.TestSet,
    organization_id: str,
    user_id: str,
) -> AdaptiveSettingsResponse:
    if not _is_adaptive_test_set(test_set):
        raise ValueError("Test set is not configured for adaptive testing")

    endpoint_ref = None
    endpoint_id = _get_default_endpoint_id_from_attributes(test_set)
    if endpoint_id is not None:
        endpoint = crud.get_endpoint(
            db=db,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if endpoint is not None:
            endpoint_ref = AdaptiveSettingsEndpoint(id=endpoint.id, name=endpoint.name)

    metrics = [
        AdaptiveSettingsMetric(id=metric.id, name=metric.name)
        for metric in (test_set.metrics or [])
    ]

    return AdaptiveSettingsResponse(default_endpoint=endpoint_ref, metrics=metrics)


def update_adaptive_settings(
    db: Session,
    test_set: models.TestSet,
    organization_id: str,
    user_id: str,
    default_endpoint_id: Optional[UUID] = None,
    metric_ids: Optional[list[UUID]] = None,
) -> AdaptiveSettingsResponse:
    if not _is_adaptive_test_set(test_set):
        raise ValueError("Test set is not configured for adaptive testing")

    if default_endpoint_id is not None:
        endpoint = crud.get_endpoint(
            db=db,
            endpoint_id=default_endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if endpoint is None:
            raise ValueError(f"Endpoint not found: {default_endpoint_id}")

        attrs = dict(test_set.attributes or {})
        adaptive_settings = dict(attrs.get("adaptive_settings") or {})
        adaptive_settings["default_endpoint_id"] = str(default_endpoint_id)
        attrs["adaptive_settings"] = adaptive_settings
        test_set.attributes = attrs
        db.add(test_set)

    if metric_ids is not None:
        # Replace metrics atomically by removing existing and adding requested.
        existing_metric_ids = [metric.id for metric in (test_set.metrics or [])]
        desired_metric_ids = list(dict.fromkeys(metric_ids))

        for metric_id in existing_metric_ids:
            if metric_id not in desired_metric_ids:
                crud.remove_metric_from_test_set(
                    db=db,
                    test_set_id=test_set.id,
                    metric_id=metric_id,
                    organization_id=test_set.organization_id,
                )

        for metric_id in desired_metric_ids:
            if metric_id not in existing_metric_ids:
                added = crud.add_metric_to_test_set(
                    db=db,
                    test_set_id=test_set.id,
                    metric_id=metric_id,
                    user_id=test_set.user_id,
                    organization_id=test_set.organization_id,
                )
                if not added:
                    continue

    db.flush()
    db.refresh(test_set)
    return get_adaptive_settings(
        db=db,
        test_set=test_set,
        organization_id=organization_id,
        user_id=user_id,
    )
