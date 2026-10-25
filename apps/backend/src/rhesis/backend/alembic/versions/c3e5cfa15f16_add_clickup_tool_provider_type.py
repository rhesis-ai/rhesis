"""Add ClickUp ToolProviderType.

Revision ID: c3e5cfa15f16
Revises: b3e7c91d4a20
Create Date: 2026-10-24
"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

revision: str = "c3e5cfa15f16"
down_revision: Union[str, None] = "b3e7c91d4a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    provider_type_values = """
        ('ToolProviderType', 'clickup', 'ClickUp integration')
    """
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM tool
        WHERE tool_provider_type_id IN (
            SELECT id FROM type_lookup
            WHERE type_name = 'ToolProviderType' AND type_value = 'clickup'
        );
        """
    )
    op.execute(load_cleanup_type_lookup_template("ToolProviderType", "'clickup'"))
