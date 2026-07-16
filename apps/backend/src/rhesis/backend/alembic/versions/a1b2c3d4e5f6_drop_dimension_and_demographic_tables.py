"""drop dimension and demographic tables

Revision ID: a1b2c3d4e5f6
Revises: e6f7a8b9c0d4
Create Date: 2026-07-16 18:00:00.000000

This migration is DESTRUCTIVE: it drops the `dimension` and `demographic`
tables and the `prompt.demographic_id` foreign key column. All data in
those tables is irrecoverably lost on upgrade. The downgrade recreates
the full pre-drop schema (empty) so the alembic chain stays consistent
at the schema level, but it cannot restore data — operators needing
actual data rollback must restore from a backup taken before upgrade.

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

from rhesis.backend.app.models.guid import GUID

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
    """Recreate the pre-drop schema (empty).

    Restores the full schema for `dimension`, `demographic`, and
    `prompt.demographic_id` as it existed at `e6f7a8b9c0d4`, so the
    alembic downgrade chain stays consistent at the schema level. Data
    lost on upgrade is NOT restored — operators needing actual data
    rollback must restore from a pre-upgrade backup.
    """
    bind = op.get_bind()

    # 1. Recreate the dimension table with all columns that existed at
    #    the down_revision (initial schema + multitenancy + nano_id +
    #    soft-delete + project_id migrations).
    if not _table_exists(bind, "dimension"):
        op.create_table(
            "dimension",
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "id",
                GUID(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
            sa.Column("nano_id", sa.String(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("organization_id", GUID(), nullable=True),
            sa.Column("user_id", GUID(), nullable=True),
            sa.Column(
                "project_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("project.id"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_dimension_id"), "dimension", ["id"], unique=True)
        op.create_index(op.f("ix_dimension_deleted_at"), "dimension", ["deleted_at"], unique=False)
        op.create_index(
            op.f("ix_dimension_project_id"), "dimension", ["project_id"], unique=False
        )

    # 2. Recreate the demographic table (depends on dimension.id FK).
    if not _table_exists(bind, "demographic"):
        op.create_table(
            "demographic",
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("dimension_id", GUID(), nullable=True),
            sa.Column(
                "id",
                GUID(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
            sa.Column("nano_id", sa.String(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("organization_id", GUID(), nullable=True),
            sa.Column("user_id", GUID(), nullable=True),
            sa.Column(
                "project_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("project.id"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["dimension_id"], ["dimension.id"]),
            sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_demographic_id"), "demographic", ["id"], unique=True)
        op.create_index(op.f("ix_demographic_deleted_at"), "demographic", ["deleted_at"], unique=False)
        op.create_index(
            op.f("ix_demographic_project_id"), "demographic", ["project_id"], unique=False
        )

    # 3. Recreate prompt.demographic_id column + FK (default postgres name
    #    `prompt_demographic_id_fkey`, which the upgrade looks up by name).
    if not _column_exists(bind, "prompt", "demographic_id"):
        op.add_column(
            "prompt",
            sa.Column(
                "demographic_id",
                GUID(),
                nullable=True,
                comment="The demographic for this prompt",
            ),
        )
        op.create_foreign_key(
            "prompt_demographic_id_fkey",
            "prompt",
            "demographic",
            ["demographic_id"],
            ["id"],
        )
