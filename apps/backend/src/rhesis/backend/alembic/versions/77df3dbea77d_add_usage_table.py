"""add usage table

Per-organization, per-resource, per-billing-period cumulative usage
counter backing the read-only ``GET /usage`` endpoint. ``resource``
stores ``QuotaResource`` string values (see
``rhesis.backend.app.quota``); the unique constraint on
``(organization_id, resource, period_start)`` is what
``increment_usage`` upserts against.

``organization_id`` cascades on delete so removing an org does not
leave orphaned counters behind.

RLS: ``usage`` gets the same ``tenant_isolation`` policy (ENABLE +
FORCE) as every other tenant table, following the per-table pattern
established after the original blanket-RLS migration (see e.g.
``d9e0f1a2b3c4_add_rbac_catalog_tables.py``) -- new tables are not
covered automatically. This matters more than usual here: the usage
service intentionally runs its reads/writes under
``bypass_tenant_filter()`` (the ORM-level auto-filter, which the raw
``INSERT ... ON CONFLICT`` upserts bypass entirely anyway), so without
this policy the application-level ``org_id`` predicate would be the
*only* tenant boundary on a table that tracks billable usage.

Excluded from the generic recycle-bin routes (``routers/recycle.py``):
see the accompanying change there. A `usage` row reachable through
generic soft-delete/restore/hard-delete would let an org member zero
their own metered usage (hard delete bypasses the soft-delete check
entirely) or, on restore, resurrect a row the increment path's
raw SQL would keep updating invisibly (the ORM's soft-delete filter
would hide it from `GET /usage`'s SELECT while the accrual still lands
on it).

Revision ID: 77df3dbea77d
Revises: c4ca0e395084
Create Date: 2026-08-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "77df3dbea77d"
down_revision: Union[str, None] = "c4ca0e395084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    table_exists = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name='usage'")
    ).fetchone()

    if not table_exists:
        op.create_table(
            "usage",
            sa.Column(
                "id",
                sa.dialects.postgresql.UUID(),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("nano_id", sa.String(), nullable=True, unique=True),
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
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "organization_id",
                sa.dialects.postgresql.UUID(),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("resource", sa.String(64), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column(
                "used",
                sa.BigInteger(),
                server_default=sa.text("0"),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "organization_id",
                "resource",
                "period_start",
                name="uq_usage_org_resource_period",
            ),
        )

    index_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename='usage' "
            "AND indexname='ix_usage_organization_id'"
        )
    ).fetchone()
    if not index_exists:
        op.create_index(
            "ix_usage_organization_id",
            "usage",
            ["organization_id"],
        )

    # Not a duplicate of Base.deleted_at's `index=True`: raw op.create_table
    # above does not honor that ORM-level flag, so nothing indexes this
    # column until this explicit op.create_index runs. Same two-step
    # (unindexed column in create_table, then this idempotent check) as
    # c7f4d9b2e1a3_add_auth_client_table.py's ix_auth_client_deleted_at.
    deleted_at_index_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename='usage' AND indexname='ix_usage_deleted_at'"
        )
    ).fetchone()
    if not deleted_at_index_exists:
        op.create_index(
            "ix_usage_deleted_at",
            "usage",
            ["deleted_at"],
        )

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON usage")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON usage
            USING (
                organization_id = NULLIF(
                    current_setting('app.current_organization', true), ''
                )::uuid
            )
        """
    )
    op.execute("ALTER TABLE usage ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE usage FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON usage")
    op.drop_index("ix_usage_deleted_at", table_name="usage")
    op.drop_index("ix_usage_organization_id", table_name="usage")
    op.drop_table("usage")
