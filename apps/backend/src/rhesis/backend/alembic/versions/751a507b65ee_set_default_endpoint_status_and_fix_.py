"""Set default endpoint status and fix metric context requirements

Revision ID: 751a507b65ee
Revises: 85ba2badbec1
Create Date: 2025-11-24

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "751a507b65ee"
down_revision: Union[str, None] = "85ba2badbec1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Set all endpoints without a status_id to the 'Active' status_id of their organization
    2. Set context_required to False for 'Refusal Detection' and 'Jailbreak Detection' metrics
    """
    # Update endpoints without a status_id to 'Active' status_id for each organization
    # Join with status table to get the 'Active' status_id for each organization
    op.execute("""
        UPDATE endpoint 
        SET status_id = s.id
        FROM status s
        WHERE endpoint.status_id IS NULL
        AND endpoint.organization_id = s.organization_id
        AND s.name = 'Active'
    """)

    # Update metrics to set context_required to False for specific metrics
    op.execute("""
        UPDATE metric 
        SET context_required = FALSE 
        WHERE name IN ('Refusal Detection', 'Jailbreak Detection')
    """)


def downgrade() -> None:
    """
    Revert the changes:
    1. Endpoint status changes are NOT reverted (see note below)
    2. Set context_required back to TRUE for the specified metrics
    """
    # Note: We cannot reliably revert endpoints to NULL as we don't know
    # which ones were NULL before the upgrade versus which were already Active.
    # Reverting all Active endpoints to NULL would corrupt pre-existing Active statuses.
    # This is effectively a one-way migration for endpoint status changes.
    # The endpoint status changes are intentionally NOT reverted during downgrade.

    # Revert metrics context_required to TRUE
    op.execute("""
        UPDATE metric 
        SET context_required = TRUE 
        WHERE name IN ('Refusal Detection', 'Jailbreak Detection')
    """)
