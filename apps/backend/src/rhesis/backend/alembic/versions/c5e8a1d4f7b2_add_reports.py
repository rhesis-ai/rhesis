"""Add reports

- ``report``: one endpoint's test runs, summarized; live while draft, frozen once published.
- ``report_test_run`` and ``report_requirement``: what the author picked. Org-scoped
  link tables, so ``tenant_isolation`` only, as on ``requirement_source``.
- ``report_result``: the counted results, written at publish.
- Eight ``report:*`` permissions, including ``update:own`` and ``delete:own``. Built-in roles compute their sets from code, so no
  ``role_permission`` rows.

Revision ID: c5e8a1d4f7b2
Revises: 72094f4a1948
Create Date: 2026-11-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e8a1d4f7b2"
down_revision: Union[str, None] = "72094f4a1948"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Keeps a hand-installed auto_rls_on_ddl event trigger from adding its own policies.
_SKIP_AUTO_RLS = "SET LOCAL auto_rls.active = 'true'"

# The bodies from f4a91c3e7b52 and b8d2f3e4a5c6.
_TENANT = """
    CREATE POLICY tenant_isolation ON {table}
        USING (organization_id = (SELECT NULLIF(current_setting('app.current_organization', true), '')::uuid))
"""
_PROJECT = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = (SELECT NULLIF(current_setting('app.current_project', true), '')::uuid)
            OR project_id IS NULL
            OR (SELECT current_setting('app.current_organization', true)) = ''
        )
"""

_PROJECT_TABLES = ("report", "report_result")
_LINK_TABLES = (
    ("report_test_run", "test_run_id", "test_run"),
    ("report_requirement", "requirement_id", "requirement"),
)

_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("report:read", "Read reports", "report", "read", "project"),
    ("report:create", "Create report", "report", "create", "project"),
    ("report:update", "Update report", "report", "update", "project"),
    ("report:delete", "Delete report", "report", "delete", "project"),
    ("report:publish", "Publish report", "report", "publish", "project"),
    ("report:export", "Export report", "report", "export", "project"),
    ("report:update:own", "Update own report", "report", "update:own", "project"),
    ("report:delete:own", "Delete own report", "report", "delete:own", "project"),
]


def _guid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", _guid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("nano_id", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", _guid(), sa.ForeignKey("project.id"), nullable=True),
    ]


def _enable_rls(table: str, *, project: bool) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(_TENANT.format(table=table))
    if project:
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(_PROJECT.format(table=table))


def _create_report() -> None:
    op.create_table(
        "report",
        *_base_columns(),
        sa.Column("organization_id", _guid(), sa.ForeignKey("organization.id"), nullable=True),
        sa.Column("user_id", _guid(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("endpoint_id", _guid(), sa.ForeignKey("endpoint.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("result_rule", sa.String(), nullable=False, server_default="latest"),
        sa.Column("is_release", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("run_tag", sa.String(), nullable=True),
        sa.Column(
            "baseline_report_id",
            _guid(),
            sa.ForeignKey("report.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.String(), nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_by_id", _guid(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("endpoint_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("sections", postgresql.JSONB(), nullable=True),
        sa.Column("snapshot_hash", sa.String(), nullable=True),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_report_status"),
        sa.CheckConstraint("result_rule IN ('latest','all','worst')", name="ck_report_result_rule"),
        sa.CheckConstraint(
            "recommendation IS NULL OR recommendation IN ('ready','ready_with_risks','not_ready')",
            name="ck_report_recommendation",
        ),
    )
    op.create_index("ix_report_organization_id", "report", ["organization_id"])
    op.create_index("ix_report_project_id", "report", ["project_id"])
    op.create_index("ix_report_endpoint_id", "report", ["endpoint_id"])


def _create_report_result() -> None:
    op.create_table(
        "report_result",
        *_base_columns(),
        sa.Column(
            "report_id",
            _guid(),
            sa.ForeignKey("report.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization_id", _guid(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("test_id", _guid(), nullable=False),
        sa.Column("test_result_id", _guid(), nullable=False),
        sa.Column("test_run_id", _guid(), nullable=False),
        sa.Column("requirement_id", _guid(), nullable=True),
        sa.Column("parent_requirement_id", _guid(), nullable=True),
        sa.Column("execution", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=True),
        sa.Column("overridden", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_report_result_report_id", "report_result", ["report_id"])
    op.create_index("ix_report_result_organization_id", "report_result", ["organization_id"])
    op.create_index("ix_report_result_project_id", "report_result", ["project_id"])


def _create_link_table(table: str, column: str, target: str) -> None:
    op.create_table(
        table,
        sa.Column(
            "report_id",
            _guid(),
            sa.ForeignKey("report.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            column, _guid(), sa.ForeignKey(f"{target}.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("user_id", _guid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("organization_id", _guid(), sa.ForeignKey("organization.id"), nullable=False),
    )
    op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])


def _seed_permissions() -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO permission (
                id, name, display_name, resource_type, action, scope,
                is_retired, created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), :name, :display_name, :resource_type,
                :action, :scope, false, now(), now()
            )
            ON CONFLICT (name) DO NOTHING
            """
        ),
        [
            {
                "name": name,
                "display_name": display_name,
                "resource_type": resource_type,
                "action": action,
                "scope": scope,
            }
            for name, display_name, resource_type, action, scope in _PERMISSIONS
        ],
    )


def upgrade() -> None:
    op.execute(_SKIP_AUTO_RLS)
    _create_report()
    _create_report_result()
    for table, column, target in _LINK_TABLES:
        _create_link_table(table, column, target)
    for table in _PROJECT_TABLES:
        _enable_rls(table, project=True)
    for table, _, _ in _LINK_TABLES:
        _enable_rls(table, project=False)
    _seed_permissions()


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM permission WHERE name = ANY(:names)"),
        {"names": [name for name, *_ in _PERMISSIONS]},
    )
    op.execute(_SKIP_AUTO_RLS)
    for table, _, _ in reversed(_LINK_TABLES):
        op.drop_table(table)
    op.drop_table("report_result")
    op.drop_table("report")
