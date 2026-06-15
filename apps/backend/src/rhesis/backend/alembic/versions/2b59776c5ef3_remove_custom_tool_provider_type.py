"""remove custom ToolProviderType from type_lookup

Revision ID: 2b59776c5ef3
Revises: 1cffd351c140
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2b59776c5ef3"
down_revision: Union[str, None] = "709e4ae75c8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM tool WHERE tool_provider_type_id IN ("
            "  SELECT id FROM type_lookup WHERE type_name = 'ToolProviderType' AND type_value = 'custom'"
            ")"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM type_lookup WHERE type_name = 'ToolProviderType' AND type_value = 'custom'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO type_lookup (type_name, type_value, description) "
            "VALUES ('ToolProviderType', 'custom', 'Custom provider with manual configuration') "
            "ON CONFLICT DO NOTHING"
        )
    )
