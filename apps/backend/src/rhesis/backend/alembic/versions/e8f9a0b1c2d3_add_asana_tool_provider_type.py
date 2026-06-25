"""Add Asana ToolProviderType

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-06-17

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    provider_type_values = """
        ('ToolProviderType', 'asana', 'Asana integration')
    """
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM tool
        WHERE tool_provider_type_id IN (
            SELECT id FROM type_lookup
            WHERE type_name = 'ToolProviderType' AND type_value = 'asana'
        );
        """
    )
    op.execute(load_cleanup_type_lookup_template("ToolProviderType", "'asana'"))
