"""add_vertex_ai_provider_type

Adds 'vertex_ai' as a new ProviderType to support Google Vertex AI
embedding models for semantic search and similarity tasks.

Revision ID: c0974af513a6
Revises: 1776e6dd47d3
Create Date: 2026-02-11 10:47:11

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "c0974af513a6"
down_revision: Union[str, None] = "1776e6dd47d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'vertex_ai' provider type for Google Vertex AI embedding models."""
    provider_type_values = (
        "('ProviderType', 'vertex_ai', 'Google Vertex AI')"
    )
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    """Remove 'vertex_ai' provider type from all organizations."""
    provider_type_value = "'vertex_ai'"
    op.execute(load_cleanup_type_lookup_template("ProviderType", provider_type_value))
