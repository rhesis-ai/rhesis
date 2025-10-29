"""rename_provider_types_together_meta

This migration renames provider types in the type_lookup table:
- 'together' -> 'together_ai'
- 'meta' -> 'meta_llama'

Revision ID: e9320c797e43
Revises: e8dd05d20cd0
Create Date: 2025-10-29 12:22:21

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9320c797e43"
down_revision: Union[str, None] = "416d3e2c6f1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename provider types from 'together' to 'together_ai' and 'meta' to 'meta_llama'."""
    # Update 'together' to 'together_ai'
    op.execute(
        """
        UPDATE type_lookup 
        SET type_value = 'together_ai' 
        WHERE type_name = 'ProviderType' 
        AND type_value = 'together'
        AND deleted_at IS NULL
        """
    )

    # Update 'meta' to 'meta_llama'
    op.execute(
        """
        UPDATE type_lookup 
        SET type_value = 'meta_llama' 
        WHERE type_name = 'ProviderType' 
        AND type_value = 'meta'
        AND deleted_at IS NULL
        """
    )

    print("✓ Renamed provider type 'together' to 'together_ai'")
    print("✓ Renamed provider type 'meta' to 'meta_llama'")


def downgrade() -> None:
    """Revert provider types from 'together_ai' to 'together' and 'meta_llama' to 'meta'."""
    # Revert 'together_ai' to 'together'
    op.execute(
        """
        UPDATE type_lookup 
        SET type_value = 'together' 
        WHERE type_name = 'ProviderType' 
        AND type_value = 'together_ai'
        AND deleted_at IS NULL
        """
    )

    # Revert 'meta_llama' to 'meta'
    op.execute(
        """
        UPDATE type_lookup 
        SET type_value = 'meta' 
        WHERE type_name = 'ProviderType' 
        AND type_value = 'meta_llama'
        AND deleted_at IS NULL
        """
    )

    print("✓ Reverted provider type 'together_ai' to 'together'")
    print("✓ Reverted provider type 'meta_llama' to 'meta'")
