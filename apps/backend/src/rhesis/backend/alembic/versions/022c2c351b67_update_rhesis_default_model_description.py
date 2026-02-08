"""update_rhesis_default_model_description

Update the description of Rhesis Default models to "Default Rhesis-hosted model."
for all organizations.

Revision ID: 022c2c351b67
Revises: c9d8e7f6a5b4
Create Date: 2026-02-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = "022c2c351b67"
down_revision: Union[str, None] = "c9d8e7f6a5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update description for all Rhesis Default models."""
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Update all models where:
        # - name = "Rhesis Default"
        # - provider_type is "rhesis" (need to join with type_lookup)
        # Set description to "Default Rhesis-hosted model."

        update_query = sa.text("""
            UPDATE model
            SET description = 'Default Rhesis-hosted model.'
            WHERE name = 'Rhesis Default'
            AND provider_type_id IN (
                SELECT id FROM type_lookup 
                WHERE type_name = 'ProviderType' 
                AND type_value = 'rhesis'
            )
        """)

        result = session.execute(update_query)
        updated_count = result.rowcount
        session.commit()

        print(f"✓ Updated description for {updated_count} Rhesis Default model(s)")

    except Exception as e:
        session.rollback()
        print(f"✗ Error updating Rhesis Default model descriptions: {e}")
        raise
    finally:
        session.close()


def downgrade() -> None:
    """
    Revert description back to original.

    No-op since new orgs already use the new description.
    """
    # No action needed - new description is consistent across migrations and org creation
    pass
