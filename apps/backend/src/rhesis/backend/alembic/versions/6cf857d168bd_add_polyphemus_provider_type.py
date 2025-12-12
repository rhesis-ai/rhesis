"""add_polyphemus_provider_type

Adds 'polyphemus' as a new ProviderType to support the Polyphemus-hosted model
infrastructure.

Revision ID: 6cf857d168bd
Revises: d77f90f52389
Create Date: 2025-12-12 10:00:00

"""

from typing import Sequence, Union

from alembic import op

# Import our simple template loader
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "6cf857d168bd"
down_revision: Union[str, None] = "d77f90f52389"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'polyphemus' provider type to support Polyphemus-hosted model infrastructure."""
    # Add ProviderType "polyphemus" to type_lookup table for all organizations
    provider_type_values = (
        "('ProviderType', 'polyphemus', 'Polyphemus hosted model infrastructure')"
    )
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    """Remove 'polyphemus' provider type from all organizations."""
    # Remove ProviderType "polyphemus" entry from type_lookup table
    provider_type_value = "'polyphemus'"
    op.execute(load_cleanup_type_lookup_template("ProviderType", provider_type_value))
