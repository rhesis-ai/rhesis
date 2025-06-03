from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "80b99c90028e"
down_revision: Union[str, None] = "dfc884bee642"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing policy and create new one with proper permissions
    op.execute("""
        DROP POLICY IF EXISTS tenant_isolation ON public.organization;
        CREATE POLICY tenant_isolation ON public.organization
        AS PERMISSIVE
        FOR ALL
        TO public
        USING (
            CASE 
                WHEN CURRENT_SETTING('app.current_organization', TRUE) IS NULL THEN TRUE
                ELSE id = CURRENT_SETTING('app.current_organization', TRUE)::uuid
            END
        )
        WITH CHECK (
            CASE 
                WHEN CURRENT_SETTING('app.current_organization', TRUE) IS NULL THEN TRUE
                ELSE id = CURRENT_SETTING('app.current_organization', TRUE)::uuid
            END
        );
    """)


def downgrade() -> None:
    # Restore original restrictive policy
    op.execute("""
        DROP POLICY IF EXISTS tenant_isolation ON public.organization;
        CREATE POLICY tenant_isolation ON public.organization
        USING (id = current_setting('app.current_organization')::uuid);
    """)
