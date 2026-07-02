"""Harden RLS on role and role_permission (RBAC catalog)

Two gaps from the SP7 catalog migration (d9e0f1a2b3c4), surfaced in the SP9–SP12
security audit:

1. ``role`` had a single ``USING``-only ``tenant_isolation`` policy.  Postgres
   reuses ``USING`` as the INSERT/UPDATE check when no ``WITH CHECK`` is given,
   and the policy's ``organization_id IS NULL`` branch (needed so every tenant
   can *read* the global built-in roles) therefore also let a tenant connection
   *write* NULL-org (built-in) or cross-org role rows.  We add an explicit
   ``WITH CHECK`` that keeps cross-tenant read of built-ins but blocks tenant
   writes to NULL-org / other-org rows.

2. ``role_permission`` had no RLS at all — cross-tenant isolation of custom-role
   permission maps relied entirely on the app-layer join through
   ``role.organization_id``.  We enable + force RLS and scope it via the parent
   role.

Trusted-context escape: both policies permit writes when
``app.current_organization`` is unset/empty.  That is the context of Alembic
data migrations and the local/quick-start startup seeding (``get_db()`` sets no
tenant GUC), which legitimately manage built-in rows.  A real tenant request
always has the GUC set, so it is held to its own org.  ``role`` and
``role_permission`` both run under FORCE ROW LEVEL SECURITY (added in
6c7d8e9f0a1b for ``role``; here for ``role_permission``), so these policies bind
the app role too.

Revision ID: a0b1c2d3e4f5
Revises: 9f0a1b2c3d4e
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "9f0a1b2c3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- role: add restrictive WITH CHECK (keep NULL-org readability) ---------
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
            WITH CHECK (
                -- Trusted server context (migrations, local seeding): no tenant GUC.
                NULLIF(current_setting('app.current_organization', true), '') IS NULL
                -- Otherwise a tenant may only write its own-org rows; never a
                -- NULL-org (built-in) or cross-org row.
                OR organization_id = NULLIF(
                    current_setting('app.current_organization', true), ''
                )::uuid
            )
        """
    )

    # --- role_permission: enable + force RLS, scope via the parent role -------
    op.execute("ALTER TABLE role_permission ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE role_permission FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON role_permission")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON role_permission
            USING (
                NULLIF(current_setting('app.current_organization', true), '') IS NULL
                OR EXISTS (
                    SELECT 1 FROM role r
                    WHERE r.id = role_permission.role_id
                      AND (
                          r.organization_id IS NULL
                          OR r.organization_id = NULLIF(
                              current_setting('app.current_organization', true), ''
                          )::uuid
                      )
                )
            )
            WITH CHECK (
                NULLIF(current_setting('app.current_organization', true), '') IS NULL
                OR EXISTS (
                    SELECT 1 FROM role r
                    WHERE r.id = role_permission.role_id
                      AND r.organization_id = NULLIF(
                          current_setting('app.current_organization', true), ''
                      )::uuid
                )
            )
        """
    )


def downgrade() -> None:
    # Restore the original USING-only role policy (d9e0f1a2b3c4). FORCE RLS stays
    # (it was added by 6c7d8e9f0a1b, not here).
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

    # role_permission had no RLS before this migration — remove it entirely.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON role_permission")
    op.execute("ALTER TABLE role_permission NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE role_permission DISABLE ROW LEVEL SECURITY")
