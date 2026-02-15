"""set null endpoint status to active

Set all endpoints with NULL status_id to the 'Active' status for the
'General' entity type within their respective organization.  The join
through type_lookup ensures we pick the correct 'Active' status (the
one scoped to EntityType / General) rather than an 'Active' status that
may belong to a different entity type such as Source or Tool.

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-02-12 18:00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Set all endpoints without a status_id to the 'Active' status for the
    'General' entity type within their respective organization.
    """
    op.execute("""
        UPDATE endpoint
        SET status_id = s.id
        FROM status s
        JOIN type_lookup tl
          ON s.entity_type_id = tl.id
        WHERE endpoint.status_id IS NULL
          AND endpoint.organization_id = s.organization_id
          AND s.name = 'Active'
          AND tl.type_name = 'EntityType'
          AND tl.type_value = 'General'
    """)


def downgrade() -> None:
    """
    Endpoint status changes are intentionally NOT reverted during
    downgrade.  We cannot reliably distinguish which endpoints were
    NULL before the upgrade versus which were already Active.
    Reverting all Active endpoints to NULL would corrupt pre-existing
    Active statuses.
    """
    pass
