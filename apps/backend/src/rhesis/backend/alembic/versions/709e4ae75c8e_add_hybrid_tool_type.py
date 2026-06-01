"""Add hybrid tool type for tools supporting both REST API and MCP

Revision ID: 709e4ae75c8e
Revises: fe4a8b2c9d1e
Create Date: 2026-06-01

"""

from typing import Sequence, Union

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
    hybrid_type = (
        "('ToolType', 'hybrid', 'Tool supporting both REST API and Model Context Protocol')"
    )
    op.execute(load_type_lookup_template(hybrid_type))


def downgrade() -> None:
    op.execute(load_cleanup_type_lookup_template("ToolType", "'hybrid'"))
