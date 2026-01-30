"""add_lmformatenforcer_provider_type

Adds 'lmformatenforcer' as a new ProviderType to support constrained decoding
with guaranteed JSON schema compliance using LM Format Enforcer library.

This provider uses the same underlying HuggingFace models but enforces JSON
schema constraints during generation for 100% schema compliance.

Revision ID: c9d8e7f6a5b4
Revises: b18dc9a57319
Create Date: 2026-01-29 13:09:50

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "c9d8e7f6a5b4"
down_revision: Union[str, None] = "b18dc9a57319"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'lmformatenforcer' provider type for constrained decoding with HuggingFace models."""
    provider_type_values = (
        "('ProviderType', 'lmformatenforcer', "
        "'LM Format Enforcer for guaranteed JSON schema compliance')"
    )
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    """Remove 'lmformatenforcer' provider type from all organizations."""
    provider_type_value = "'lmformatenforcer'"
    op.execute(load_cleanup_type_lookup_template("ProviderType", provider_type_value))
