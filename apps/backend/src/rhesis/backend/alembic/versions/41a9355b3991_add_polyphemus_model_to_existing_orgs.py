"""add_polyphemus_model_to_existing_orgs

This migration adds the Polyphemus model to all existing organizations.
For new organizations, the model is created during onboarding via load_initial_data.

Revision ID: 41a9355b3991
Revises: 7b998a6fe52d
Create Date: 2026-01-14

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

# Import models and utilities
from rhesis.backend.app import models
from rhesis.backend.app.utils.model_utils import create_default_rhesis_model

# revision identifiers, used by Alembic.
revision: str = "41a9355b3991"
down_revision: Union[str, None] = "7b998a6fe52d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add the Polyphemus model to all existing organizations.

    Uses the utility function to create models with proper error handling
    and consistency with the load_initial_data function.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Get all organizations (including those that haven't completed onboarding)
        organizations = session.query(models.Organization).all()

        print(f"\n📦 Creating Polyphemus model for {len(organizations)} organization(s)...")
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

            # Check if a protected Polyphemus model already exists
            existing_model = (
                session.query(models.Model)
                .join(models.TypeLookup, models.Model.provider_type_id == models.TypeLookup.id)
                .filter(
                    models.Model.organization_id == org.id,
                    models.TypeLookup.type_value == "polyphemus",
                    models.Model.is_protected,
                )
                .first()
            )

            if existing_model:
                print(f"  ⏭ Skipping org {organization_id}: Polyphemus model already exists")
                skipped_count += 1
                continue

            try:
                # Create the Polyphemus model using the utility function
                polyphemus_model = create_default_rhesis_model(
                    db=session,
                    provider_value="polyphemus",
                    model_name="default",
                    name="Rhesis Polyphemus",
                    description=(
                        "Polyphemus adversarial model hosted by Rhesis. No API key required."
                    ),
                    icon="polyphemus",
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )

                created_count += 1
                print(
                    f"  ✓ Created Polyphemus model for org {organization_id} "
                    f"(ID: {polyphemus_model.id})"
                )

            except Exception as e:
                print(f"  ✗ Error creating model for org {organization_id}: {e}")
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
    Remove the Polyphemus models that were created by this migration.

    WARNING: This will only remove protected Polyphemus models, not any user-created Polyphemus
    models.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Find protected Polyphemus models to delete
        models_to_delete = (
            session.query(models.Model)
            .join(models.TypeLookup, models.Model.provider_type_id == models.TypeLookup.id)
            .filter(
                models.Model.is_protected,
                models.Model.name == "Rhesis Polyphemus",
                models.TypeLookup.type_value == "polyphemus",
            )
            .all()
        )

        deleted_count = len(models_to_delete)

        # Delete each model individually
        for model in models_to_delete:
            session.delete(model)

        session.commit()
        print(f"\n🗑 Removed {deleted_count} Polyphemus model(s)\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Downgrade failed: {e}\n")
        raise
    finally:
        session.close()
