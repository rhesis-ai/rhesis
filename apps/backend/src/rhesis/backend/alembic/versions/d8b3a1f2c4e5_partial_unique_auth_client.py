"""scope auth_client uniqueness to live rows

Convert the ``(organization_id, client_id)`` UniqueConstraint to a
**partial unique index** with ``WHERE deleted_at IS NULL``, and tighten
the existing ``(organization_id, name)`` partial index with the same
predicate.

Why
----
Soft-deleting an AuthClient (set ``deleted_at = now()``) keeps the
audit trail intact but, with a plain UniqueConstraint, also forever
poisons the ``(org_id, client_id)`` slot it occupied. An org that
disables their ``brain`` integration and later wants to recreate it
would get a 409 forever, or be forced to hard-delete the audit trail
to free the slot. Both are bad: the first is a usability papercut, the
second is an availability-vs-forensics trade we should never push onto
operators.

A partial unique index restricts the uniqueness invariant to live rows
(``deleted_at IS NULL``) only. Multiple soft-deleted rows with the
same ``(org_id, client_id)`` are allowed; at most one live row remains
the invariant we actually care about.

Idempotent
----------
Both DROP CONSTRAINT and CREATE INDEX guards check
``information_schema`` / ``pg_indexes`` first so re-running on a
partially-applied DB is a no-op.

Revision ID: d8b3a1f2c4e5
Revises: d8a5e0f3c4b2
Create Date: 2026-05-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8b3a1f2c4e5"
down_revision: Union[str, None] = "d8a5e0f3c4b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ---- (organization_id, client_id) -----------------------------------

    constraint_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name='auth_client' "
            "AND constraint_name='uq_auth_client_org_client'"
        )
    ).fetchone()
    if constraint_exists:
        op.drop_constraint("uq_auth_client_org_client", "auth_client", type_="unique")

    new_index_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename='auth_client' "
            "AND indexname='uq_auth_client_org_client_active'"
        )
    ).fetchone()
    if not new_index_exists:
        op.create_index(
            "uq_auth_client_org_client_active",
            "auth_client",
            ["organization_id", "client_id"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )

    # ---- (organization_id, name) ----------------------------------------
    # The original index already had ``WHERE name IS NOT NULL`` to allow
    # multiple unnamed rows; widen the predicate to also exclude
    # soft-deleted rows so renaming a client and recreating with the old
    # name is not blocked.

    name_index_old_predicate = conn.execute(
        sa.text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename='auth_client' "
            "AND indexname='uq_auth_client_org_name'"
        )
    ).fetchone()
    if name_index_old_predicate is not None:
        # Replace the index by drop + recreate. Postgres cannot ALTER
        # the WHERE clause of an existing index in place.
        op.drop_index("uq_auth_client_org_name", table_name="auth_client")
        op.create_index(
            "uq_auth_client_org_name",
            "auth_client",
            ["organization_id", "name"],
            unique=True,
            postgresql_where=sa.text("name IS NOT NULL AND deleted_at IS NULL"),
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Revert (org, name) index predicate to the original.
    name_idx = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename='auth_client' "
            "AND indexname='uq_auth_client_org_name'"
        )
    ).fetchone()
    if name_idx is not None:
        op.drop_index("uq_auth_client_org_name", table_name="auth_client")
        op.create_index(
            "uq_auth_client_org_name",
            "auth_client",
            ["organization_id", "name"],
            unique=True,
            postgresql_where=sa.text("name IS NOT NULL"),
        )

    # Drop partial-unique on client_id and restore the original
    # UniqueConstraint. Note: this downgrade WILL fail if the table
    # currently has soft-deleted duplicates -- by design, because that
    # is the exact state the upgrade was supposed to make legal.
    partial_idx = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename='auth_client' "
            "AND indexname='uq_auth_client_org_client_active'"
        )
    ).fetchone()
    if partial_idx is not None:
        op.drop_index("uq_auth_client_org_client_active", table_name="auth_client")

    constraint_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name='auth_client' "
            "AND constraint_name='uq_auth_client_org_client'"
        )
    ).fetchone()
    if not constraint_exists:
        op.create_unique_constraint(
            "uq_auth_client_org_client",
            "auth_client",
            ["organization_id", "client_id"],
        )
