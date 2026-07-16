"""drop dimension and demographic tables

Revision ID: a1b2c3d4e5f6
Revises: e6f7a8b9c0d4
Create Date: 2026-07-16 18:00:00.000000

This migration is DESTRUCTIVE: it drops the `dimension` and `demographic`
tables and the `prompt.demographic_id` foreign key column. All data in
those tables is irrecoverably lost on upgrade. The downgrade recreates
the schema (empty) but cannot restore data.

The `Dimension` and `Demographic` entities were scaffolded end-to-end
(router, model, schema, CRUD, constants, service-layer wiring, test
suite) but never reached from any active frontend or SDK call path.
Issue #1240 tracks their removal as dead code.

NOTE: This migration must not be squashed or reordered ahead of any
migration that references the `dimension` or `demographic` tables.
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e6f7a8b9c0d4"
branch_labels: Union[str, None] = None
depends_on: Union[list[str], None] = None


def _constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    """Return True if a constraint with the given name exists on the table."""
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint WHERE conname = :name AND conrelid = :table::regclass"
        ),
        {"name": constraint_name, "table": table_name},
    )
    return result.scalar() is not None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    """Return True if a column with the given name exists on the table."""
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table_name, "column": column_name},
    )
    return result.scalar() is not None


def _table_exists(bind, table_name: str) -> bool:
    """Return True if a table with the given name exists in the schema."""
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :table"
        ),
        {"table": table_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Drop the FK constraint on prompt.demographic_id → demographic.id.
    #    Postgres default naming convention: <table>_<column>_fkey
    fk_name = "prompt_demographic_id_fkey"
    if _constraint_exists(bind, "prompt", fk_name):
        op.drop_constraint(fk_name, "prompt", type_="foreignkey")

    # 2. Drop the demographic_id column on prompt.
    if _column_exists(bind, "prompt", "demographic_id"):
        op.drop_column("prompt", "demographic_id")

    # 3. Drop the demographic table (has FK to dimension.id).
    if _table_exists(bind, "demographic"):
        op.drop_table("demographic")

    # 4. Drop the dimension table.
    if _table_exists(bind, "dimension"):
        op.drop_table("dimension")


def downgrade() -> None:
    """Best-effort schema recreation.

    Data lost on upgrade is NOT restored — only the empty table structure
    is recreated so future migrations can rely on the schema existing.
    """
    bind = op.get_bind()

    # Recreate dimension table
    if not _table_exists(bind, "dimension"):
        op.create_table(
            "dimension",
            sa.Column("id", sa.GUID(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("organization_id", sa.GUID(), sa.ForeignKey("organization.id")),
            sa.Column("user_id", sa.GUID(), sa.ForeignKey("user.id")),
        )

    # Recreate demographic table
    if not _table_exists(bind, "demographic"):
        op.create_table(
            "demographic",
            sa.Column("id", sa.GUID(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column(
                "dimension_id", sa.GUID(), sa.ForeignKey("dimension.id")
            ),
            sa.Column("organization_id", sa.GUID(), sa.ForeignKey("organization.id")),
            sa.Column("user_id", sa.GUID(), sa.ForeignKey("user.id")),
        )

    # Recreate prompt.demographic_id column + FK
    if not _column_exists(bind, "prompt", "demographic_id"):
        op.add_column(
            "prompt",
            sa.Column(
                "demographic_id",
                sa.GUID(),
                sa.ForeignKey("demographic.id"),
                comment="The demographic for this prompt",
            ),
        )
