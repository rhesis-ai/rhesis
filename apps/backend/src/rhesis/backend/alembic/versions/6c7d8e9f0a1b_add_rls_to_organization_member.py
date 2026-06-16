"""Fix missed RLS on organization_member and role tables

The auto-RLS event trigger installed by migration d4e5f6a7b8c3 did not
fire for ``organization_member`` or ``role`` when d9e0f1a2b3c4 created
them.  d9e0f1a2b3c4 set ENABLE ROW LEVEL SECURITY on ``role`` but omitted
FORCE, so table-owner connections (including the app superuser) could
bypass the policy.  This migration corrects both gaps.

``organization_member.organization_id`` is NOT NULL, so the standard
``organization_id = current_setting(...)::uuid`` policy is correct.

``role`` carries built-in rows with a NULL org_id; its NULL-tolerant policy
was already created by d9e0f1a2b3c4 — we only add FORCE here.

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
    # organization_member — enable + force + standard tenant policy
    op.execute("ALTER TABLE organization_member ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization_member FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organization_member")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON organization_member
            USING (organization_id = current_setting('app.current_organization')::uuid)
        """
    )

    # role — d9e0f1a2b3c4 set ENABLE but not FORCE; add it here
    op.execute("ALTER TABLE role FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organization_member")
    # Do not disable RLS on either table — DISABLE ROW LEVEL SECURITY would
    # affect any policies added later. The trigger may re-add the policy on
    # the next schema migration; that is harmless.
