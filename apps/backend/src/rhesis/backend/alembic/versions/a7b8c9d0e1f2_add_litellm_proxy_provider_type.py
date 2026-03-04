"""add_litellm_proxy_azure_ai_and_azure_openai_provider_types

Adds 'litellm_proxy', 'azure_ai', and 'azure' as new ProviderType entries
to support LiteLLM Proxy, Azure AI Studio, and Azure OpenAI model access.

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
    """Add 'litellm_proxy', 'azure_ai', and 'azure' provider types."""
    litellm_proxy_values = (
        "('ProviderType', 'litellm_proxy', 'LiteLLM Proxy for unified model access')"
    )
    op.execute(load_type_lookup_template(litellm_proxy_values))

    azure_ai_values = "('ProviderType', 'azure_ai', 'Azure AI Studio model provider')"
    op.execute(load_type_lookup_template(azure_ai_values))

    azure_openai_values = "('ProviderType', 'azure', 'Azure OpenAI model provider')"
    op.execute(load_type_lookup_template(azure_openai_values))


def downgrade() -> None:
    """Remove 'litellm_proxy', 'azure_ai', and 'azure' provider types."""
    op.execute(load_cleanup_type_lookup_template("ProviderType", "'litellm_proxy'"))
    op.execute(load_cleanup_type_lookup_template("ProviderType", "'azure_ai'"))
    op.execute(load_cleanup_type_lookup_template("ProviderType", "'azure'"))
