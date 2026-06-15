"""add_polyphemus_model_to_existing_orgs

This migration adds the Polyphemus model to all existing organizations.
For new organizations, the model is created during onboarding via load_initial_data.

Also serves as a merge migration consolidating the two heads from main.

Revision ID: 41a9355b3991
Revises: 2ff5b3e69a58, 33e3f87f44aa
Create Date: 2026-01-14

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from sqlalchemy import text

from rhesis.backend.app import models
from rhesis.backend.app.utils.crud_utils import create_default_rhesis_model

# revision identifiers, used by Alembic.
revision: str = "41a9355b3991"
down_revision = ("2ff5b3e69a58", "33e3f87f44aa")
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
        # Use raw SQL to avoid ORM model column set changing across migrations
        from sqlalchemy import text

        org_rows = (
            op.get_bind().execute(text("SELECT id, owner_id, user_id FROM organization")).fetchall()
        )

        print(f"\n📦 Creating Polyphemus model for {len(org_rows)} organization(s)...")
        created_count = 0
        skipped_count = 0

        for org_row in org_rows:
            org_id, org_owner_id, org_user_id = org_row[0], org_row[1], org_row[2]
            organization_id = str(org_id)
            # Use owner_id or fall back to user_id
            owner_or_user_id = org_owner_id or org_user_id

            if not owner_or_user_id:
                print(f"  ⚠ Skipping org {organization_id}: No owner or user")
                skipped_count += 1
                continue

            # Check if a protected Polyphemus model already exists.
            # Raw SQL avoids selecting columns (e.g. project_id) that may not
            # exist yet at this point in the migration chain.
            existing_model = session.execute(
                text(
                    "SELECT 1 FROM model m "
                    "JOIN type_lookup t ON m.provider_type_id = t.id "
                    "WHERE m.organization_id = :org_id "
                    "AND t.type_value = 'polyphemus' "
                    "AND m.is_protected = TRUE "
                    "LIMIT 1"
                ),
                {"org_id": str(org_id)},
            ).fetchone()

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
                    user_id=str(owner_or_user_id),
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
        # Raw SQL avoids selecting columns (e.g. project_id) that may not exist
        # yet at this point in the migration chain.
        result = session.execute(
            text(
                "DELETE FROM model "
                "WHERE is_protected = TRUE AND name = 'Rhesis Polyphemus' "
                "AND provider_type_id IN ("
                "  SELECT id FROM type_lookup WHERE type_value = 'polyphemus'"
                ") "
                "RETURNING id"
            )
        ).fetchall()

        deleted_count = len(result)
        session.commit()
        print(f"\n🗑 Removed {deleted_count} Polyphemus model(s)\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Downgrade failed: {e}\n")
        raise
    finally:
        session.close()
