"""add_litellm_proxy_provider_type

Adds 'litellm_proxy' as a new ProviderType to support LiteLLM Proxy
for unified model access via OpenAI-compatible endpoints.

Revision ID: a7b8c9d0e1f2
Revises: aef6c47a8faa
Create Date: 2026-03-04 10:00:00

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "aef6c47a8faa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'litellm_proxy' provider type for LiteLLM Proxy unified model access."""
    provider_type_values = (
        "('ProviderType', 'litellm_proxy', 'LiteLLM Proxy for unified model access')"
    )
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    """Remove 'litellm_proxy' provider type from all organizations."""
    provider_type_value = "'litellm_proxy'"
    op.execute(load_cleanup_type_lookup_template("ProviderType", provider_type_value))
