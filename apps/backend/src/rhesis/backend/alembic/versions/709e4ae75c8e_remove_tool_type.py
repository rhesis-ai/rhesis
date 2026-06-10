"""Remove tool_type column and ToolType lookup entries

Revision ID: 709e4ae75c8e
Revises: d4e5f6a7b8c3
Create Date: 2026-06-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import rhesis.backend.app.models.guid
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

revision: str = "709e4ae75c8e"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tool_tool_type_id")
    op.execute("ALTER TABLE tool DROP CONSTRAINT IF EXISTS tool_tool_type_id_fkey")
    # Column may not exist on a fresh DB that never had tool_type_id
    conn = op.get_bind()
    col_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='tool' AND column_name='tool_type_id'"
        )
    ).fetchone()
    if col_exists:
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
