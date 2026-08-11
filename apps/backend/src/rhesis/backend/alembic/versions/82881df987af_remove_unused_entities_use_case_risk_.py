"""Remove unused entities: use_case, risk, response_pattern, test_context

These four entities had zero frontend/SDK consumers (confirmed by repo-wide
usage audit — see backend AGENTS.md-adjacent memory of the schema audit that
first flagged them). Drops:

- The four entity tables themselves.
- Their two many-to-many junction tables (risk_use_case, prompt_use_case).
- test_configuration.use_case_id, the one column on a live, still-used table
  that pointed at use_case.

Drop order matters: risk_use_case and prompt_use_case both hold FKs to
use_case, and test_configuration.use_case_id does too, so all three must go
before use_case itself. response_pattern and test_context have no incoming
FKs and can be dropped at any point. risk's self-referential parent_id FK is
dropped along with the table, no special handling needed.

All four tables carry FORCE ROW LEVEL SECURITY with a permissive
tenant_isolation policy and a restrictive project_isolation policy; dropping
a table drops its own policies for free, no explicit DROP POLICY needed.

Revision ID: 82881df987af
Revises: 40a5b6b88a52
Create Date: 2026-08-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import rhesis.backend

# revision identifiers, used by Alembic.
revision: str = "82881df987af"
down_revision: Union[str, None] = "40a5b6b88a52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RETIRED_CAPS = [
    "use_case:create",
    "use_case:delete",
    "use_case:read",
    "use_case:update",
    "risk:create",
    "risk:delete",
    "risk:read",
    "risk:update",
    "response_pattern:create",
    "response_pattern:delete",
    "response_pattern:read",
    "response_pattern:update",
    "test_context:create",
    "test_context:delete",
    "test_context:read",
    "test_context:update",
]


def upgrade() -> None:
    bind = op.get_bind()

    # Junction tables reference use_case; drop before use_case itself.
    op.drop_table("risk_use_case")
    op.drop_table("prompt_use_case")

    # test_configuration.use_case_id also FKs to use_case; dropping the column
    # drops its FK constraint with it.
    op.drop_column("test_configuration", "use_case_id")

    # No incoming FKs on these two.
    op.drop_table("response_pattern")
    op.drop_table("test_context")

    # risk's self-FK (parent_id) and its own FK into risk_use_case (already
    # dropped above) are both gone once the table is.
    op.drop_table("risk")

    # Safe now that risk_use_case, prompt_use_case, and
    # test_configuration.use_case_id have all been dropped.
    op.drop_table("use_case")

    # Retire the four resources' CRUD capabilities from the permission
    # catalog — their routers are removed in this same PR, so the
    # capabilities no longer appear in get_all_capabilities() and must be
    # marked retired to keep test_capability_catalog in sync (see
    # 6867d319c0a5, the dimension/demographic precedent for this pattern).
    bind.execute(
        sa.text("UPDATE permission SET is_retired = true WHERE name IN :caps").bindparams(
            sa.bindparam("caps", expanding=True)
        ),
        {"caps": _RETIRED_CAPS},
    )
    bind.execute(
        sa.text(
            "DELETE FROM role_permission "
            "WHERE permission_id IN ("
            "  SELECT id FROM permission WHERE name IN :caps"
            ")"
        ).bindparams(sa.bindparam("caps", expanding=True)),
        {"caps": _RETIRED_CAPS},
    )


def downgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "use_case",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("application", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("status_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("nano_id", sa.String(), nullable=True),
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("user_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("project_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.ForeignKeyConstraint(["status_id"], ["status.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nano_id", name="uq_use_case_nano_id"),
    )
    op.create_index("ix_use_case_id", "use_case", ["id"], unique=True)
    op.create_index("ix_use_case_deleted_at", "use_case", ["deleted_at"])
    op.create_index("ix_use_case_project_id", "use_case", ["project_id"])

    op.create_table(
        "risk",
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("status_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("nano_id", sa.String(), nullable=True),
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("user_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("project_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["risk.id"]),
        sa.ForeignKeyConstraint(["status_id"], ["status.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nano_id", name="uq_risk_nano_id"),
    )
    op.create_index("ix_risk_id", "risk", ["id"], unique=True)
    op.create_index("ix_risk_deleted_at", "risk", ["deleted_at"])
    op.create_index("ix_risk_project_id", "risk", ["project_id"])

    op.create_table(
        "response_pattern",
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("response_pattern_type_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("behavior_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("nano_id", sa.String(), nullable=True),
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("user_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("project_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.ForeignKeyConstraint(["behavior_id"], ["behavior.id"]),
        sa.ForeignKeyConstraint(["response_pattern_type_id"], ["type_lookup.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nano_id", name="uq_response_pattern_nano_id"),
    )
    op.create_index("ix_response_pattern_id", "response_pattern", ["id"], unique=True)
    op.create_index("ix_response_pattern_deleted_at", "response_pattern", ["deleted_at"])
    op.create_index("ix_response_pattern_project_id", "response_pattern", ["project_id"])

    op.create_table(
        "test_context",
        sa.Column("test_id", rhesis.backend.app.models.guid.GUID(), nullable=False),
        sa.Column("entity_id", rhesis.backend.app.models.guid.GUID(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("nano_id", sa.String(), nullable=True),
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("user_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("project_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.ForeignKeyConstraint(["test_id"], ["test.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nano_id", name="uq_test_context_nano_id"),
    )
    op.create_index("ix_test_context_id", "test_context", ["id"], unique=True)
    op.create_index("ix_test_context_deleted_at", "test_context", ["deleted_at"])
    op.create_index("ix_test_context_project_id", "test_context", ["project_id"])

    op.add_column(
        "test_configuration", sa.Column("use_case_id", rhesis.backend.app.models.guid.GUID(), nullable=True)
    )
    op.create_foreign_key(
        "test_configuration_use_case_id_fkey", "test_configuration", "use_case", ["use_case_id"], ["id"]
    )

    op.create_table(
        "risk_use_case",
        sa.Column("risk_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("use_case_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("user_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.ForeignKeyConstraint(["risk_id"], ["risk.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_case.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
    )

    op.create_table(
        "prompt_use_case",
        sa.Column("prompt_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("use_case_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("user_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_case.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
    )

    # Re-enable RLS to match the live shape these tables had before removal
    # (FORCE ROW LEVEL SECURITY + tenant_isolation + fail-closed
    # project_isolation, per c3d4e5f6a7b2 / b8c9d0e1f2a3). auto_rls.active is
    # the auto_rls_on_ddl event trigger's own reentry guard (see
    # a9b8c7d6e5f4) — set it first so the trigger doesn't also try to add
    # policies from these CREATE TABLEs and collide with the explicit ones
    # below.
    conn.execute(sa.text("SET LOCAL auto_rls.active = 'true'"))

    for table in ("use_case", "risk", "response_pattern", "test_context", "risk_use_case", "prompt_use_case"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (organization_id = current_setting('app.current_organization')::uuid)
        """)

    for table in ("use_case", "risk", "response_pattern", "test_context"):
        op.execute(f"""
            CREATE POLICY project_isolation ON {table}
                AS RESTRICTIVE
                FOR ALL
                USING (
                    project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
                    OR project_id IS NULL
                    OR current_setting('app.current_organization', true) = ''
                )
        """)

    conn.execute(sa.text("SET LOCAL auto_rls.active = 'false'"))

    # Unretire the capabilities (reverses the upgrade's retire step). The
    # role_permission rows deleted on upgrade are not restored — same
    # limitation as 6867d319c0a5's downgrade; operators needing that data
    # back must restore from a pre-upgrade backup.
    conn.execute(
        sa.text("UPDATE permission SET is_retired = false WHERE name IN :caps").bindparams(
            sa.bindparam("caps", expanding=True)
        ),
        {"caps": _RETIRED_CAPS},
    )
