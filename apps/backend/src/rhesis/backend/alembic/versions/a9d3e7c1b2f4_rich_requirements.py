"""Richer requirements: hierarchy, impact, sources, review and examples

- ``requirement.parent_id`` (self-FK, SET NULL), ``impact_id`` (type_lookup), ``review`` (the last AI quality review, JSONB).
- ``requirement_source``: requirement <-> source links with a ``note``. Org-scoped, no
  ``project_id``, so ``tenant_isolation`` only, as on ``requirement_metric``.
- ``annotation.requirement_id``, backfilled for TestResult annotations from the
  result's test.
- ``RequirementImpact`` lookups for every organization.

Revision ID: a9d3e7c1b2f4
Revises: f2c8d4e6a913
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)
from rhesis.backend.alembic.utils.tenant_scope import iter_tenant_scopes

revision: str = "a9d3e7c1b2f4"
down_revision: Union[str, None] = "f2c8d4e6a913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LINK_TABLE = "requirement_source"
# Keeps a hand-installed auto_rls_on_ddl event trigger from adding its own policies.
_SKIP_AUTO_RLS = "SET LOCAL auto_rls.active = 'true'"
# The body from f4a91c3e7b52.
_TENANT_POLICY = f"""
CREATE POLICY tenant_isolation ON {_LINK_TABLE} AS PERMISSIVE FOR ALL TO public
USING (organization_id = (SELECT NULLIF(current_setting('app.current_organization', true), '')::uuid))
"""

_TYPE_LOOKUPS = """
    ('RequirementImpact', 'Safety', 'Someone could get hurt'),
    ('RequirementImpact', 'Legal & compliance', 'Breaks a law, regulation, contract or internal policy'),
    ('RequirementImpact', 'Privacy & security', 'Exposes personal data or secrets, or opens a security hole'),
    ('RequirementImpact', 'Financial', 'Costs money'),
    ('RequirementImpact', 'Reputation', 'Damages trust in the company'),
    ('RequirementImpact', 'Customer experience', 'The user doesn''t get what they came for')
"""
_TYPE_VALUES = {
    "RequirementImpact": (
        "'Safety', 'Legal & compliance', 'Privacy & security', 'Financial', 'Reputation', 'Customer experience'"
    ),
}

_BACKFILL_ANNOTATIONS = sa.text("""
    UPDATE annotation a
    SET requirement_id = t.requirement_id
    FROM test_result tr
    JOIN test t ON t.id = tr.test_id
    WHERE a.entity_type = 'TestResult'
      AND a.entity_id = tr.id
      AND a.requirement_id IS NULL
      AND t.requirement_id IS NOT NULL
      AND a.organization_id = CAST(:org_id AS uuid)
      AND a.project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)
""")


def _add_requirement_columns() -> None:
    guid = postgresql.UUID(as_uuid=True)
    op.add_column("requirement", sa.Column("parent_id", guid, nullable=True))
    op.add_column("requirement", sa.Column("impact_id", guid, nullable=True))
    op.add_column(
        "requirement", sa.Column("review", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.create_foreign_key(
        "fk_requirement_parent_id",
        "requirement",
        "requirement",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_requirement_parent_id", "requirement", ["parent_id"])
    op.create_foreign_key(
        "fk_requirement_impact_id", "requirement", "type_lookup", ["impact_id"], ["id"]
    )


def _create_link_table() -> None:
    guid = postgresql.UUID(as_uuid=True)
    op.execute(_SKIP_AUTO_RLS)
    op.create_table(
        _LINK_TABLE,
        sa.Column(
            "requirement_id",
            guid,
            sa.ForeignKey("requirement.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_id", guid, sa.ForeignKey("source.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("user_id", guid, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("organization_id", guid, sa.ForeignKey("organization.id"), nullable=False),
    )
    op.create_index(f"ix_{_LINK_TABLE}_source_id", _LINK_TABLE, ["source_id"])
    op.create_index(f"ix_{_LINK_TABLE}_organization_id", _LINK_TABLE, ["organization_id"])
    op.execute(f"ALTER TABLE {_LINK_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_LINK_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_LINK_TABLE}")
    op.execute(_TENANT_POLICY)


def _add_annotation_column() -> None:
    op.add_column(
        "annotation",
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_annotation_requirement_id",
        "annotation",
        "requirement",
        ["requirement_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_annotation_requirement_id", "annotation", ["requirement_id"])


def _seed_and_backfill() -> None:
    conn = op.get_bind()
    for org_id, project_id in iter_tenant_scopes(conn):
        if project_id is None:
            # type_lookup is org-scoped; the template inserts for the orgs it can see.
            conn.execute(sa.text(load_type_lookup_template(_TYPE_LOOKUPS)))
        conn.execute(_BACKFILL_ANNOTATIONS, {"org_id": org_id, "project_id": project_id})


def upgrade() -> None:
    _add_requirement_columns()
    _create_link_table()
    _add_annotation_column()
    _seed_and_backfill()


def downgrade() -> None:
    op.drop_index("ix_annotation_requirement_id", table_name="annotation")
    op.drop_constraint("fk_annotation_requirement_id", "annotation", type_="foreignkey")
    op.drop_column("annotation", "requirement_id")

    op.execute(_SKIP_AUTO_RLS)
    op.drop_table(_LINK_TABLE)

    op.drop_constraint("fk_requirement_impact_id", "requirement", type_="foreignkey")
    op.drop_index("ix_requirement_parent_id", table_name="requirement")
    op.drop_constraint("fk_requirement_parent_id", "requirement", type_="foreignkey")
    for column in ("review", "impact_id", "parent_id"):
        op.drop_column("requirement", column)

    conn = op.get_bind()
    for _org_id, project_id in iter_tenant_scopes(conn):
        if project_id is not None:
            continue
        for type_name, values in _TYPE_VALUES.items():
            conn.execute(sa.text(load_cleanup_type_lookup_template(type_name, values)))
