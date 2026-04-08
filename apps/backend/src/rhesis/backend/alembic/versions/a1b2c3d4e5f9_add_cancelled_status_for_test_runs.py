"""Add Cancelled status for test runs

This migration adds the 'Cancelled' status to all organizations for TestRun entities.
This status is used when a test run is cancelled by the user before completion.

Revision ID: a1b2c3d4e5f9
Revises: 533ebb47f308
Create Date: 2026-04-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_status_template,
    load_status_template,
)

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f9"
down_revision: Union[str, None] = "533ebb47f308"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'Cancelled' status for TestRun entity type to all organizations."""
    status_values = "('Cancelled', 'Describes a cancelled test run')"
    op.execute(load_status_template("EntityType", "TestRun", status_values))


def downgrade() -> None:
    """Remove 'Cancelled' status for TestRun entity type."""
    status_names = "'Cancelled'"
    op.execute(load_cleanup_status_template("EntityType", "TestRun", status_names))
