from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f8d34f13c9c"
down_revision: Union[str, None] = "2a8f096b0f6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing policy if it exists
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.test_set;")

    # Create new policy that allows access based on visibility levels:
    # - public: accessible to everyone
    # - organization: accessible to users in the same organization
    # - user: accessible only to the owner
    op.execute("""
        CREATE POLICY tenant_isolation ON public.test_set
        AS PERMISSIVE
        FOR ALL
        TO public
        USING (
            CASE 
                WHEN visibility = 'public' THEN TRUE
                WHEN visibility = 'organization' THEN organization_id = 
                    CURRENT_SETTING('app.current_organization', TRUE)::uuid
                WHEN visibility = 'user' THEN user_id = 
                    CURRENT_SETTING('app.current_user', TRUE)::uuid
                ELSE FALSE
            END
        )
        WITH CHECK (organization_id = CURRENT_SETTING('app.current_organization', TRUE)::uuid);
    """)


def downgrade() -> None:
    # Drop the specialized policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.test_set;")

    # Restore the original RLS policy that was created in the initial RLS implementation
    op.execute("""
        CREATE POLICY tenant_isolation ON public.test_set
        AS PERMISSIVE
        FOR ALL
        TO public
        USING (organization_id = current_setting('app.current_organization')::uuid);
    """)
