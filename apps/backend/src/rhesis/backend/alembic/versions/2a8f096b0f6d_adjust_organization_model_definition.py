from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a8f096b0f6d"
down_revision: Union[str, None] = "55f5352df067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old policies if they exist
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.organization;")

    op.execute("""
        CREATE POLICY tenant_isolation ON public.organization
        AS PERMISSIVE
        FOR ALL
        TO public
        USING (
            CASE 
                WHEN CURRENT_SETTING('app.current_organization', TRUE) IS NULL THEN TRUE
                WHEN CURRENT_SETTING('app.current_organization', TRUE) = '' THEN TRUE
                ELSE id = CURRENT_SETTING('app.current_organization', TRUE)::uuid
            END
        )
        WITH CHECK (TRUE);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.organization;")

    # Restore the old policy that covered all actions
    op.execute("""
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
