"""Add GitLab ToolProviderType

Revision ID: f1a2b3c4d5e0
Revises: 6c7d8e9f0a1b
Create Date: 2026-06-16

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

revision: str = "f1a2b3c4d5e0"
down_revision: Union[str, None] = "6c7d8e9f0a1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    provider_type_values = """
        ('ToolProviderType', 'gitlab', 'GitLab integration')
    """
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM tool
        WHERE tool_provider_type_id IN (
            SELECT id FROM type_lookup
            WHERE type_name = 'ToolProviderType' AND type_value = 'gitlab'
        );
        """
    )
    op.execute(load_cleanup_type_lookup_template("ToolProviderType", "'gitlab'"))
