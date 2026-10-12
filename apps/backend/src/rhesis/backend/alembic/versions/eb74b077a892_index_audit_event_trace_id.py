"""Index audit_event on (organization_id, trace_id)

For the event detail's "Related events": the other events of the same request.
A plain CREATE INDEX: the table is new and still small.

Revision ID: eb74b077a892
Revises: ef7fe15a29ee
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "eb74b077a892"
down_revision: Union[str, None] = "ef7fe15a29ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_audit_event_org_trace"
# Dev still has an auto_rls_on_ddl event trigger (c1d2e3f4a5b6 dropped it elsewhere); keep it out.
_SKIP_AUTO_RLS = "SET LOCAL auto_rls.active = 'true'"


def upgrade() -> None:
    op.execute(_SKIP_AUTO_RLS)
    op.create_index(_INDEX, "audit_event", ["organization_id", "trace_id"])


def downgrade() -> None:
    op.execute(_SKIP_AUTO_RLS)
    op.drop_index(_INDEX, table_name="audit_event")
