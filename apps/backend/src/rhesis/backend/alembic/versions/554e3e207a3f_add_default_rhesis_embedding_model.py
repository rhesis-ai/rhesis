"""add_default_rhesis_embedding_model

This migration adds the default Rhesis embedding model to all existing organizations.
For new organizations, the embedding model is created during onboarding via load_initial_data.

Revision ID: 554e3e207a3f
Revises: ae4f01064490
Create Date: 2026-02-16 00:00:00

"""

import uuid
from typing import Optional, Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

# Import models and utilities
from rhesis.backend.app import models
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.models.enums import ModelType
from rhesis.backend.app.utils.crud_utils import (
    get_or_create_entity,
    get_or_create_status,
    get_or_create_type_lookup,
)

# revision identifiers, used by Alembic.
revision: str = "554e3e207a3f"
down_revision: Union[str, None] = "ae4f01064490"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _update_user_embedding_settings(
    session: Session,
    organization_id: str,
    condition_fn,
    new_model_id: Optional[str],
) -> int:
    """
    Helper function to update user embedding model settings.

    Args:
        session: SQLAlchemy session
        organization_id: Organization ID to filter users
        condition_fn: Function that takes current_model_id and returns True if update needed
        new_model_id: The new model_id to set (or None to clear)

    Returns:
        Number of users updated
    """
    users_in_org = (
        session.query(models.User).filter(models.User.organization_id == organization_id).all()
    )

    users_updated = 0
    for user in users_in_org:
        updates = {}

        # Check embedding model settings
        embedding_setting = getattr(user.settings.models, "embedding", None)
        if embedding_setting:
            current_model_id = (
                str(embedding_setting.model_id) if embedding_setting.model_id else None
            )

            if condition_fn(current_model_id):
                updates["models"] = {"embedding": {"model_id": new_model_id}}

        # Apply updates using UserSettingsManager if needed
        if updates:
            # Settings are auto-persisted when using user.settings
            user.settings.update(updates)
            session.flush()
            users_updated += 1

    return users_updated


def upgrade() -> None:
    """
    Add the default Rhesis embedding model to all existing organizations.

    Uses existing utility functions to create models with proper error handling
    and consistency with the load_initial_data function.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # For Rhesis embedding model, always use "default" as model_name
        # (regardless of what DEFAULT_EMBEDDING_MODEL env var is set to)
        embedding_model_name = "default"

        # Get all organizations (including those that haven't completed onboarding)
        organizations = session.query(models.Organization).all()

        print(
            f"\n📦 Creating default Rhesis embedding model for {len(organizations)} "
            f"organization(s)..."
        )
        created_count = 0
        skipped_count = 0

        for org in organizations:
            organization_id = str(org.id)
            # Use owner_id or fall back to user_id
            user_id = str(org.owner_id or org.user_id)

            if not user_id:
                print(f"  ⚠ Skipping org {organization_id}: No owner or user")
                skipped_count += 1
                continue

            # Check if a protected Rhesis embedding model already exists
            existing_model = (
                session.query(models.Model)
                .join(models.TypeLookup, models.Model.provider_type_id == models.TypeLookup.id)
                .filter(
                    models.Model.organization_id == org.id,
                    models.TypeLookup.type_value == "rhesis",
                    models.Model.is_protected,
                    models.Model.model_type == ModelType.EMBEDDING.value,
                )
                .first()
            )

            if existing_model:
                print(f"  ⏭ Skipping org {organization_id}: Rhesis embedding model already exists")
                skipped_count += 1
                continue

            try:
                # Get or create the rhesis provider type
                rhesis_provider_type = get_or_create_type_lookup(
                    db=session,
                    type_name="ProviderType",
                    type_value="rhesis",
                    description="Rhesis",
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )

                # Get or create the Available status for Model entity type
                available_status = get_or_create_status(
                    db=session,
                    name="Available",
                    entity_type=EntityType.MODEL,
                    description="Model is ready and can be used",
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )

                # Create the default Rhesis embedding model
                default_embedding_model_data = {
                    "name": "Rhesis Default Embedding",
                    "model_name": embedding_model_name,
                    "model_type": ModelType.EMBEDDING.value,
                    "description": "Default Rhesis-hosted embedding model for semantic search.",
                    "icon": "rhesis",
                    "provider_type_id": rhesis_provider_type.id,
                    "status_id": available_status.id,
                    "key": "",
                    "endpoint": None,
                    "is_protected": True,
                    "user_id": uuid.UUID(user_id),
                    "owner_id": uuid.UUID(user_id),
                }

                default_embedding_model = get_or_create_entity(
                    db=session,
                    model=models.Model,
                    entity_data=default_embedding_model_data,
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )

                # Set this model as default embedding model for users in this organization
                # who don't have an embedding model set
                users_updated = _update_user_embedding_settings(
                    session=session,
                    organization_id=org.id,
                    condition_fn=lambda model_id: model_id is None,  # Update if not set
                    new_model_id=str(default_embedding_model.id),
                )

                created_count += 1
                print(
                    f"  ✓ Created Rhesis embedding model for org {organization_id} "
                    f"(set as default for {users_updated} user(s))"
                )

            except Exception as e:
                print(f"  ✗ Error creating embedding model for org {organization_id}: {e}")
                skipped_count += 1
                continue

        # Commit all changes
        session.commit()
        print(f"\n✅ Migration complete: {created_count} created, {skipped_count} skipped\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Migration failed: {e}\n")
        raise
    finally:
        session.close()


def downgrade() -> None:
    """
    Remove the default Rhesis embedding models that were created by this migration.
    Also clean up user settings that reference these models.

    WARNING: This will only remove protected Rhesis embedding models,
    not any user-created Rhesis embedding models.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Find protected Rhesis embedding models to delete
        models_to_delete = (
            session.query(models.Model)
            .join(models.TypeLookup, models.Model.provider_type_id == models.TypeLookup.id)
            .filter(
                models.Model.is_protected,
                models.Model.name == "Rhesis Default Embedding",
                models.TypeLookup.type_value == "rhesis",
                models.Model.model_type == ModelType.EMBEDDING.value,
            )
            .all()
        )

        deleted_count = len(models_to_delete)
        users_updated = 0

        # Clean up user settings that reference these models
        for model in models_to_delete:
            model_id_str = str(model.id)

            # Clear settings for users pointing to this model
            users_updated += _update_user_embedding_settings(
                session=session,
                organization_id=model.organization_id,
                condition_fn=lambda mid, target=model_id_str: mid == target,  # Update if matches
                new_model_id=None,  # Clear the setting
            )

        # Delete each model individually
        for model in models_to_delete:
            session.delete(model)

        session.commit()
        print(
            f"\n🗑 Removed {deleted_count} default Rhesis embedding model(s) and cleared "
            f"settings for {users_updated} user(s)\n"
        )

    except Exception as e:
        session.rollback()
        print(f"\n❌ Downgrade failed: {e}\n")
        raise
    finally:
        session.close()
