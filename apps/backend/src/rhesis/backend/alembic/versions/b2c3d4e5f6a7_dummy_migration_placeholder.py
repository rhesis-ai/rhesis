"""dummy migration placeholder

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-10-13

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a placeholder migration to fix the revision chain
    # No actual database changes needed
    pass


def downgrade() -> None:
    # This is a placeholder migration to fix the revision chain
    # No actual database changes needed
    pass
