"""Add Error status for test results

This migration adds the 'Error' status to all organizations for TestResult entities.
This status is used when a test execution completes but has no metrics to evaluate.

Revision ID: 416d3e2c6f1f
Revises: 415c0d01df0e
Create Date: 2025-10-28 23:25:00.000000

"""

from typing import Sequence, Union

from alembic import op

# Import our template loader utilities
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_status_template,
    load_status_template,
)


# revision identifiers, used by Alembic.
revision: str = "416d3e2c6f1f"
down_revision: Union[str, None] = "415c0d01df0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add 'Error' status for TestResult entity type to all organizations.
    """
    # Add Error status entry to status table for TestResult entity type
    status_values = "('Error', 'Test execution error (no metrics to evaluate)')"
    op.execute(load_status_template("EntityType", "TestResult", status_values))


def downgrade() -> None:
    """
    Remove 'Error' status for TestResult entity type.
    """
    # Remove Error status entry from status table
    status_names = "'Error'"
    op.execute(load_cleanup_status_template("EntityType", "TestResult", status_names))
