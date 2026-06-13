"""Enable FORCE ROW LEVEL SECURITY on project and association tables

Three tables had RLS enabled and the correct tenant_isolation policy but
were missing FORCE ROW LEVEL SECURITY:

  - project
  - prompt_use_case
  - risk_use_case

FORCE ROW LEVEL SECURITY makes the policies apply even when the current
role is the table owner.  Without it, the table owner (typically the
migration/admin role) bypasses RLS entirely.  In production the APP_DB_USER
is not the owner so this was not an active exploit, but it is an inconsistency
that makes the security model harder to reason about and leaves a gap if the
role configuration ever changes.

Revision ID: b7c8d9e0f1a2
Revises: a9b8c7d6e5f4
Create Date: 2026-06-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ["project", "prompt_use_case", "risk_use_case"]


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        already_forced = conn.execute(
            sa.text(
                "SELECT relforcerowsecurity FROM pg_class "
                "WHERE relnamespace = 'public'::regnamespace AND relname = :tbl"
            ),
            {"tbl": table},
        ).scalar()
        if not already_forced:
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    conn = op.get_bind()
    for table in reversed(_TABLES):
        is_forced = conn.execute(
            sa.text(
                "SELECT relforcerowsecurity FROM pg_class "
                "WHERE relnamespace = 'public'::regnamespace AND relname = :tbl"
            ),
            {"tbl": table},
        ).scalar()
        if is_forced:
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
