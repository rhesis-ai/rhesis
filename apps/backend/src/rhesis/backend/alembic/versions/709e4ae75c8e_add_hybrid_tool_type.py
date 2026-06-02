"""Remove tool_type column and ToolType lookup entries

Revision ID: 709e4ae75c8e
Revises: fe4a8b2c9d1e
Create Date: 2026-06-01

"""

from typing import Sequence, Union

import rhesis.backend.app.models.guid
import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

revision: str = "709e4ae75c8e"
down_revision: Union[str, Sequence[str], None] = ("fe4a8b2c9d1e", "f3a4b5c6d7e8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_tool_tool_type_id"), table_name="tool")
    op.drop_constraint("tool_tool_type_id_fkey", "tool", type_="foreignkey")
    op.drop_column("tool", "tool_type_id")

    op.execute(load_cleanup_type_lookup_template("ToolType", "'mcp', 'api', 'hybrid'"))


def downgrade() -> None:
    tool_type_values = """
        ('ToolType', 'mcp', 'Model Context Protocol tool'),
        ('ToolType', 'api', 'REST API tool'),
        ('ToolType', 'hybrid', 'Tool supporting both REST API and Model Context Protocol')
    """
    op.execute(load_type_lookup_template(tool_type_values))

    op.add_column(
        "tool",
        sa.Column("tool_type_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
    )
    op.create_foreign_key("tool_tool_type_id_fkey", "tool", "type_lookup", ["tool_type_id"], ["id"])
    op.create_index(op.f("ix_tool_tool_type_id"), "tool", ["tool_type_id"], unique=False)
