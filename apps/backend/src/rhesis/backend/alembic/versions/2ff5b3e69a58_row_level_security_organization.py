from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2ff5b3e69a58"
down_revision: Union[str, None] = "fcac5b8b5eb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable RLS on organization table
    op.execute("ALTER TABLE public.organization ENABLE ROW LEVEL SECURITY;")

    # Create organization isolation policy
    op.execute("""
        DROP POLICY IF EXISTS tenant_isolation ON public.organization;
        CREATE POLICY tenant_isolation ON public.organization
        USING (id = current_setting('app.current_organization')::uuid);
    """)


def downgrade() -> None:
    # Drop policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.organization;")

    # Disable RLS
    op.execute("ALTER TABLE public.organization DISABLE ROW LEVEL SECURITY;")
