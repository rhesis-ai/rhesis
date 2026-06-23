"""Add EE RBAC catalog tables: permission, role, role_permission, organization_member (SP7)

Creates the four tables that form the EE RBAC catalog.  These tables are
seeded idempotently by the EE bootstrap sync (``ee/rbac/sync.py``) and are
only active when the ``rhesis-backend-ee`` package is installed.  The
migration itself is always present in the core chain so that a Community →
EE upgrade does not require a separate migration run.

Table summary:
- ``permission``         — one row per ``resource:action`` capability string
- ``role``               — built-in and org-owned custom roles
- ``role_permission``    — M2M: which permissions belong to which role
- ``organization_member``— org-level role assignment for a user

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-06-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_uuid = sa.dialects.postgresql.UUID(as_uuid=True)


def _table_exists(conn, table):
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :t"
            ),
            {"t": table},
        ).fetchone()
        is not None
    )


def _index_exists(conn, index_name):
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
            {"n": index_name},
        ).fetchone()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # permission
    # ------------------------------------------------------------------
    if not _table_exists(conn, "permission"):
        op.create_table(
            "permission",
            sa.Column(
                "id",
                _uuid,
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("nano_id", sa.String(), nullable=True, unique=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), nullable=False, server_default=""),
            sa.Column(
                "resource_type",
                sa.String(),
                nullable=False,
                server_default="",
            ),
            sa.Column("action", sa.String(), nullable=False, server_default=""),
            sa.Column("scope", sa.String(), nullable=False, server_default="project"),
            sa.Column(
                "is_retired",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_permission_id", "permission", ["id"], unique=True)
        op.create_index(
            "ix_permission_name",
            "permission",
            ["name"],
            unique=True,
        )
        op.create_index(
            "ix_permission_resource_type",
            "permission",
            ["resource_type"],
        )

    # ------------------------------------------------------------------
    # role
    # ------------------------------------------------------------------
    if not _table_exists(conn, "role"):
        op.create_table(
            "role",
            sa.Column(
                "id",
                _uuid,
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("nano_id", sa.String(), nullable=True, unique=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column(
                "display_name",
                sa.String(),
                nullable=False,
                server_default="",
            ),
            sa.Column(
                "scope",
                sa.String(),
                nullable=False,
                server_default="project",
            ),
            sa.Column(
                "level",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "is_built_in",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "organization_id",
                _uuid,
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_role_id", "role", ["id"], unique=True)
        op.create_index("ix_role_organization_id", "role", ["organization_id"])
        op.create_index(
            "ix_role_name_org",
            "role",
            ["name", "organization_id"],
            unique=True,
        )
        op.create_index(
            "uq_role_builtin_name",
            "role",
            ["name"],
            unique=True,
            postgresql_where=sa.text("organization_id IS NULL"),
        )

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON role")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON role
            USING (
                organization_id IS NULL
                OR organization_id = NULLIF(
                    current_setting('app.current_organization', true), ''
                )::uuid
            )
        """
    )
    op.execute("ALTER TABLE role ENABLE ROW LEVEL SECURITY")

    # ------------------------------------------------------------------
    # role_permission  (M2M)
    # ------------------------------------------------------------------
    if not _table_exists(conn, "role_permission"):
        op.create_table(
            "role_permission",
            sa.Column(
                "id",
                _uuid,
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("nano_id", sa.String(), nullable=True, unique=True),
            sa.Column(
                "role_id",
                _uuid,
                sa.ForeignKey("role.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "permission_id",
                _uuid,
                sa.ForeignKey("permission.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "role_id",
                "permission_id",
                name="uq_role_permission",
            ),
        )
        op.create_index(
            "ix_role_permission_id",
            "role_permission",
            ["id"],
            unique=True,
        )
        op.create_index(
            "ix_role_permission_role_id",
            "role_permission",
            ["role_id"],
        )
        op.create_index(
            "ix_role_permission_permission_id",
            "role_permission",
            ["permission_id"],
        )

    # ------------------------------------------------------------------
    # organization_member  (org-level role assignment)
    # ------------------------------------------------------------------
    if not _table_exists(conn, "organization_member"):
        op.create_table(
            "organization_member",
            sa.Column(
                "id",
                _uuid,
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("nano_id", sa.String(), nullable=True, unique=True),
            sa.Column(
                "organization_id",
                _uuid,
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                _uuid,
                sa.ForeignKey("user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "role_id",
                _uuid,
                sa.ForeignKey("role.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "organization_id",
                "user_id",
                name="uq_organization_member_org_user",
            ),
        )
        op.create_index(
            "ix_organization_member_id",
            "organization_member",
            ["id"],
            unique=True,
        )
        op.create_index(
            "ix_organization_member_organization_id",
            "organization_member",
            ["organization_id"],
        )
        op.create_index(
            "ix_organization_member_user_id",
            "organization_member",
            ["user_id"],
        )
        op.create_index(
            "ix_organization_member_role_id",
            "organization_member",
            ["role_id"],
        )


def downgrade() -> None:
    op.drop_table("organization_member")
    op.drop_table("role_permission")
    # tenant_isolation policy and the partial unique index drop with the table.
    op.drop_table("role")
    op.drop_table("permission")
