"""add_rhesis_provider_type

Adds 'rhesis' as a new ProviderType to support the default Rhesis-hosted model
infrastructure for new users during onboarding.

Revision ID: d99dc2079c4d
Revises: fe5d9ca98fca
Create Date: 2025-10-26 18:29:27.481341

"""
from alembic import op
from typing import Union, Sequence

# Import our simple template loader
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)


# revision identifiers, used by Alembic.
revision: str = 'd99dc2079c4d'
down_revision: Union[str, None] = 'fe5d9ca98fca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'rhesis' provider type to support Rhesis-hosted model infrastructure."""
    # Add ProviderType "rhesis" to type_lookup table for all organizations
    provider_type_values = "('ProviderType', 'rhesis', 'Rhesis hosted model infrastructure')"
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    """Remove 'rhesis' provider type from all organizations."""
    # Remove ProviderType "rhesis" entry from type_lookup table
    provider_type_value = "'rhesis'"
    op.execute(load_cleanup_type_lookup_template("ProviderType", provider_type_value))