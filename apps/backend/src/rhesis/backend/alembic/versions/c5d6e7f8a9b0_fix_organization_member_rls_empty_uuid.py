"""Fix organization_member RLS policy crash on empty GUC

The tenant_isolation policy on organization_member (added in
6c7d8e9f0a1b) casts current_setting('app.current_organization')
directly to ::uuid.  When no tenant GUC is set (e.g. SSO callback,
migrations, seeding), the setting defaults to '' and the cast fails
with ``invalid input syntax for type uuid: ""``.

The hardened policies on role and role_permission (a0b1c2d3e4f5)
already use NULLIF(..., '')::uuid and a trusted-context escape.
This migration applies the same pattern to organization_member:

- USING: trusted context (empty GUC) sees all rows; tenant context
  is scoped to its own org.
- WITH CHECK: trusted context may write any row; tenant context may
  only write its own org.

Revision ID: c5d6e7f8a9b0
Revises: b4b371a45639
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4b371a45639"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organization_member")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON organization_member
            USING (
                NULLIF(current_setting('app.current_organization', true), '') IS NULL
                OR organization_id = NULLIF(
                    current_setting('app.current_organization', true), ''
                )::uuid
            )
            WITH CHECK (
                NULLIF(current_setting('app.current_organization', true), '') IS NULL
                OR organization_id = NULLIF(
                    current_setting('app.current_organization', true), ''
                )::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organization_member")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON organization_member
            USING (organization_id = current_setting('app.current_organization')::uuid)
        """
    )
