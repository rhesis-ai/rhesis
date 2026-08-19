"""CRUD operations for models -- the LLM/embedding provider configurations users register.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

``update_model`` and ``delete_model`` enforce the ``is_protected`` rules for system models,
the pre-seeded rows an organization gets on onboarding. A protected model rejects any
change to its core configuration -- name, model_name, provider_type_id, key, endpoint,
is_protected, icon -- and rejects deletion outright, while tags, status, owner and assignee
stay editable so users can still organize it. Both raise ``ValueError`` with "protected" in
the message; the router turns that into a 403.

``get_model`` intentionally doesn't follow this repo's usual soft-delete contract -- see
its own docstring.

The block that moved here also held ``test_model_connection``, a stub that never did
anything but return ``True`` -- the real check was never written. It had no callers (the
``/models/{id}/test`` endpoint uses ``ModelConnectionService`` instead), so it was dropped
rather than carried over.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

# Relationships serialized by schemas.ModelDetail -- provider_type, status.
# owner/assignee: unused, excluded. Public (no leading underscore) since
# routers/model.py's own get_item_detail call for the single-item GET reuses it.
MODEL_DETAIL_RELATED_FIELDS = (
    include(models.Model.provider_type),
    include(models.Model.status),
)


def get_model(
    db: Session, model_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Model]:
    """Get a specific model by ID with its related objects and organization filtering.

    Doesn't call ``get_item_detail`` directly: callers here need a soft-deleted model
    to return ``None``, not raise ``ItemDeletedException``, so they can fall back.
    """
    return (
        QueryBuilder(db, models.Model)
        .with_related(include(models.Model.provider_type))
        .with_organization_filter(organization_id)
        .filter_by_id(model_id)
    )


def get_models(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Model]:
    """Get all models with their related objects"""
    return get_items_detail(
        db,
        models.Model,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=MODEL_DETAIL_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def _reject_rows_without_own_credentials(db: Session, model: schemas.ModelCreate) -> None:
    """Refuse a row that has neither an API key nor an endpoint of its own.

    Such a row falls back to reading its key from the process environment, so
    it would run on this deployment's credentials rather than the tenant's.
    Caught here so the tenant sees it while saving rather than when a test run
    fails later; `_require_own_credentials` is the runtime backstop that also
    covers rows edited into this shape or created before this check existed.
    """
    from rhesis.backend.app.utils.user_model_utils import has_own_credentials

    if model.provider_type_id is None:
        return
    provider_type = (
        db.query(models.TypeLookup).filter(models.TypeLookup.id == model.provider_type_id).first()
    )
    if provider_type is None:
        return
    if has_own_credentials(provider_type.type_value, model.key, model.endpoint):
        return
    raise ValueError(
        f"Model '{model.name}' needs either an API key or an endpoint. Without one it would "
        f"run on the server's own provider credentials."
    )


def create_model(
    db: Session, model: schemas.ModelCreate, organization_id: str = None, user_id: str = None
) -> models.Model:
    """Create a new model."""
    _reject_rows_without_own_credentials(db, model)
    return create_item(db, models.Model, model, organization_id, user_id)


def update_model(
    db: Session,
    model_id: uuid.UUID,
    model: schemas.ModelUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Model]:
    """Update a model."""
    # First check if the model is protected
    existing_model = get_model(db, model_id, organization_id)
    if existing_model and getattr(existing_model, "is_protected", False):
        # For protected models, only allow updating certain fields
        # (tags, comments, status, owner, assignee)
        # Block updates to core model configuration properties
        protected_fields = {
            "name",
            "model_name",
            "provider_type_id",
            "key",
            "endpoint",
            "is_protected",
            "icon",
        }

        # Convert model to dict and check if any protected fields are being updated
        update_data = (
            model.model_dump(exclude_unset=True)
            if hasattr(model, "model_dump")
            else model.dict(exclude_unset=True)
        )

        # Check if user is trying to change any protected fields to a different value
        attempted_protected_updates = []
        for field in protected_fields:
            if field in update_data:
                existing_value = getattr(existing_model, field)
                new_value = update_data[field]
                # Only flag as error if the value is actually changing
                if existing_value != new_value:
                    attempted_protected_updates.append(field)

        if attempted_protected_updates:
            fields_str = ", ".join(attempted_protected_updates)
            raise ValueError(
                f"Cannot update protected fields ({fields_str}) on system model. "
                "Only tags, status, owner, and assignee can be modified."
            )

    return update_item(db, models.Model, model_id, model, organization_id, user_id)


def delete_model(
    db: Session, model_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Model]:
    """Delete a model (protected models cannot be deleted)"""
    # First check if the model is protected
    model = get_model(db, model_id, organization_id)
    if model and getattr(model, "is_protected", False):
        raise ValueError("Cannot delete protected system model")

    return delete_item(db, models.Model, model_id, organization_id=organization_id, user_id=user_id)
