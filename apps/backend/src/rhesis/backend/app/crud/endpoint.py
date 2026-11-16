"""CRUD operations for endpoints."""

import uuid
from typing import Dict, List, Optional
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    bulk_delete_by_ids,
    create_item,
    delete_item,
    get_item_detail,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import include

_ENDPOINT_RELATED_FIELDS = (
    include(models.Endpoint.status),
    include(models.Endpoint.user),
    include(models.Endpoint.project),
)


def get_endpoint(
    db: Session,
    endpoint_id: uuid.UUID,
    organization_id: str,
    user_id: str,
    project_id: str | None = None,
) -> Optional[models.Endpoint]:
    """Get endpoint with relationships eagerly loaded."""
    return get_item_detail(
        db,
        models.Endpoint,
        endpoint_id,
        organization_id,
        user_id,
        project_id=project_id,
        related_fields=_ENDPOINT_RELATED_FIELDS,
    )


def get_endpoints(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.Endpoint]:
    return get_items_detail(
        db,
        models.Endpoint,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_ENDPOINT_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def _set_metadata_timeout(
    db_endpoint: models.Endpoint,
    timeout_seconds: Optional[int],
) -> None:
    """Set or clear timeout_seconds in endpoint_metadata."""
    meta = dict(db_endpoint.endpoint_metadata or {})
    if timeout_seconds is not None:
        meta["timeout_seconds"] = timeout_seconds
    else:
        meta.pop("timeout_seconds", None)
    db_endpoint.endpoint_metadata = meta


def create_endpoint(
    db: Session, endpoint: schemas.EndpointCreate, organization_id: str, user_id: str
) -> models.Endpoint:
    """Create endpoint."""
    timeout_seconds = endpoint.timeout_seconds if hasattr(endpoint, "timeout_seconds") else None
    db_endpoint = create_item(db, models.Endpoint, endpoint, organization_id, user_id)
    if timeout_seconds is not None:
        _set_metadata_timeout(db_endpoint, timeout_seconds)
        db.flush()
        db.refresh(db_endpoint)
    return db_endpoint


# Changing any of these makes a cached OAuth token stale.
_TOKEN_INPUT_FIELDS = frozenset(
    {
        "auth_type",
        "client_id",
        "client_secret",
        "token_url",
        "token_endpoint_auth_method",
        "scopes",
        "audience",
        "extra_payload",
    }
)


# A stored secret is only ever sent to the host it was entered for. Moving the endpoint
# elsewhere without supplying a new one clears it, or the backend would hand it to
# whichever server the endpoint now names.
_SECRET_FOLLOWS_HOST = {"url": "auth_token", "token_url": "client_secret"}


def _host(url: Optional[str]) -> Optional[str]:
    if not url or not url.strip():
        return None
    url = url.strip()
    # "api.example.com/chat" has no scheme, so urlsplit would put the host in the path.
    if "://" not in url and not url.startswith("//"):
        url = f"https://{url}"
    parts = urlsplit(url)
    return f"{(parts.scheme or 'https').lower()}://{(parts.netloc or '').lower()}"


def _drop_secrets_for_new_hosts(db: Session, endpoint_id: uuid.UUID, endpoint_data: dict) -> None:
    moved = [f for f in _SECRET_FOLLOWS_HOST if f in endpoint_data]
    if not moved:
        return
    current = db.query(models.Endpoint).filter(models.Endpoint.id == endpoint_id).first()
    if current is None:
        return
    for url_field in moved:
        secret_field = _SECRET_FOLLOWS_HOST[url_field]
        if secret_field in endpoint_data:
            continue
        if _host(endpoint_data[url_field]) != _host(getattr(current, url_field)):
            endpoint_data[secret_field] = None


def update_endpoint(
    db: Session,
    endpoint_id: uuid.UUID,
    endpoint: schemas.EndpointUpdate,
    organization_id: str,
    user_id: str,
) -> Optional[models.Endpoint]:
    """Update endpoint."""
    fields_set = getattr(endpoint, "model_fields_set", set())
    timeout_was_set = "timeout_seconds" in fields_set
    timeout_seconds = getattr(endpoint, "timeout_seconds", None)

    # Strip timeout_seconds before update_item: the ORM exposes it as a
    # read-only @property, so setattr would raise AttributeError.
    if hasattr(endpoint, "model_dump"):
        endpoint_data = endpoint.model_dump(exclude={"timeout_seconds"}, exclude_unset=True)
    else:
        endpoint_data = {k: v for k, v in endpoint.items() if k != "timeout_seconds"}

    _drop_secrets_for_new_hosts(db, endpoint_id, endpoint_data)
    if _TOKEN_INPUT_FIELDS & endpoint_data.keys():
        endpoint_data["last_token"] = None
        endpoint_data["last_token_expires_at"] = None

    db_endpoint = update_item(
        db, models.Endpoint, endpoint_id, endpoint_data, organization_id, user_id
    )
    if db_endpoint is not None and timeout_was_set:
        _set_metadata_timeout(db_endpoint, timeout_seconds)
        db.flush()
        db.refresh(db_endpoint)
    return db_endpoint


def delete_endpoint(
    db: Session, endpoint_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Endpoint]:
    return delete_item(
        db, models.Endpoint, endpoint_id, organization_id=organization_id, user_id=user_id
    )


def bulk_delete_endpoints(
    db: Session,
    endpoint_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """Soft delete multiple endpoints in one transaction.

    No owner-only rule on endpoint delete, so this is a direct wrapper around
    the generic bulk helper.
    """
    return bulk_delete_by_ids(
        db,
        models.Endpoint,
        endpoint_ids,
        organization_id=organization_id,
        user_id=user_id,
    )


def user_endpoint_exists(db: Session, organization_id: str) -> bool:
    """True when a live endpoint that isn't seeded example data is visible in the
    session's current scope."""
    query = db.query(models.Endpoint.id).filter(
        models.Endpoint.organization_id == organization_id,
        models.Endpoint.is_example.is_(False),
        models.Endpoint.deleted_at.is_(None),
    )
    return bool(db.query(query.exists()).scalar())
