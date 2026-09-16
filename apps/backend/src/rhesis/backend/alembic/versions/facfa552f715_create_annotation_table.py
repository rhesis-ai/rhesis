"""Create annotation table and add original_status_id to test_result and trace

``original_status_id`` snapshots the automated verdict before the first
annotation overwrites it, so ``matches_annotation`` can tell agreement from a
status the annotation itself just set. Traces never had that snapshot.

Revision ID: facfa552f715
Revises: a0a48c28ad64
Create Date: 2026-09-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "facfa552f715"
down_revision: Union[str, None] = "a0a48c28ad64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_annotation_id", ["id"], True),
    ("ix_annotation_nano_id", ["nano_id"], True),
    ("ix_annotation_deleted_at", ["deleted_at"], False),
    ("ix_annotation_entity", ["entity_type", "entity_id"], False),
    ("ix_annotation_org_project_updated", ["organization_id", "project_id", "updated_at"], False),
]


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(op.get_bind()).get_columns(table)]


def upgrade() -> None:
    if not _table_exists("annotation"):
        op.create_table(
            "annotation",
            sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("nano_id", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("organization_id", UUID(), sa.ForeignKey("organization.id"), nullable=True),
            sa.Column("project_id", UUID(), sa.ForeignKey("project.id"), nullable=True),
            sa.Column("user_id", UUID(), sa.ForeignKey("user.id"), nullable=True),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("entity_id", UUID(), nullable=False),
            sa.Column("target_type", sa.String(), nullable=False),
            sa.Column("target_reference", sa.String(), nullable=True),
            sa.Column("status_id", UUID(), sa.ForeignKey("status.id"), nullable=False),
            sa.Column("comments", sa.Text(), nullable=True),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("resolved_by_id", UUID(), sa.ForeignKey("user.id"), nullable=True),
            sa.Column("attributes", JSONB(), nullable=True),
        )
        for name, columns, unique in _INDEXES:
            op.create_index(name, "annotation", columns, unique=unique)

        # Same policy bodies as every other project-scoped table (d4e5f6a7b8c3,
        # c3d4e5f6a7b2): PERMISSIVE tenant_isolation ANDed with RESTRICTIVE
        # project_isolation, the latter passing through when no project is bound.
        op.execute("ALTER TABLE annotation ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE annotation FORCE ROW LEVEL SECURITY")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON annotation")
        op.execute("""
            CREATE POLICY tenant_isolation ON annotation
                USING (organization_id = current_setting('app.current_organization')::uuid)
        """)
        op.execute("DROP POLICY IF EXISTS project_isolation ON annotation")
        op.execute("""
            CREATE POLICY project_isolation ON annotation
                AS RESTRICTIVE
                FOR ALL
                USING (
                    project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
                    OR project_id IS NULL
                    OR current_setting('app.current_project', true) = ''
                )
        """)

    for table in ("test_result", "trace"):
        if not _column_exists(table, "original_status_id"):
            op.add_column(
                table,
                sa.Column("original_status_id", UUID(), sa.ForeignKey("status.id"), nullable=True),
            )


def downgrade() -> None:
    for table in ("trace", "test_result"):
        if _column_exists(table, "original_status_id"):
            op.drop_column(table, "original_status_id")
    if _table_exists("annotation"):
        op.execute("DROP POLICY IF EXISTS project_isolation ON annotation")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON annotation")
        for name, _, _ in reversed(_INDEXES):
            op.drop_index(name, table_name="annotation")
        op.drop_table("annotation")
