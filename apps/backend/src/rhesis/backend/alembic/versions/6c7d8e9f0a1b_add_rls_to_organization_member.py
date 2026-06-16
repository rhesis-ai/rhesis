"""Add RLS to organization_member table (missed by auto-trigger)

The auto-RLS event trigger installed by migration d4e5f6a7b8c3 should have
applied the standard ``tenant_isolation`` policy when d9e0f1a2b3c4 created
``organization_member``. In practice the trigger did not fire for this table
(d9e0f1a2b3c4 handles ``role`` explicitly for the same reason). This
migration applies the policy explicitly, consistent with the pattern used
for every other table that has ``organization_id``.

``organization_member.organization_id`` is NOT NULL, so the standard
``organization_id = current_setting(...)::uuid`` policy is correct (no
NULL-tolerance needed, unlike the ``role`` table which carries built-in rows
with a NULL org).

Revision ID: 6c7d8e9f0a1b
Revises: 5b6c7d8e9f0a
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op

revision: str = "6c7d8e9f0a1b"
down_revision: Union[str, None] = "5b6c7d8e9f0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE organization_member ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization_member FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organization_member")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON organization_member
            USING (organization_id = current_setting('app.current_organization')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organization_member")
    # Do not disable RLS — DISABLE ENABLE ROW LEVEL SECURITY would affect other
    # policies if any were added later. The trigger may re-add this policy on
    # the next schema migration; that is harmless.
