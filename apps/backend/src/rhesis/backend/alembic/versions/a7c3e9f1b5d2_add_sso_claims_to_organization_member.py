"""Add the SSO claims snapshot to organization_member

- ``organization_member.sso_claims``: the list-valued claims (groups, roles) from the
  member's last SSO sign-in. SSO role mapping reads it to suggest groups and to preview
  who a mapping change affects.
- ``organization_member.sso_claims_at``: when that sign-in happened.
- ``organization_member.sso_grants``: the org role and project roles the mapping gave,
  so they can be taken back when the person leaves the group or the rule is removed.

Both nullable, so images without SSO role mapping keep working.

Revision ID: a7c3e9f1b5d2
Revises: e1f4a7c2b9d3
Create Date: 2026-11-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7c3e9f1b5d2"
down_revision: Union[str, None] = "e1f4a7c2b9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organization_member", sa.Column("sso_claims", postgresql.JSONB(), nullable=True))
    op.add_column(
        "organization_member",
        sa.Column("sso_claims_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("organization_member", sa.Column("sso_grants", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("organization_member", "sso_grants")
    op.drop_column("organization_member", "sso_claims_at")
    op.drop_column("organization_member", "sso_claims")
