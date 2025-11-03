"""add_is_protected_to_model

Adds is_protected column to the model table to mark system models that
cannot be deleted by users (e.g., the default Rhesis model).

Revision ID: 10c4e8124417
Revises: d99dc2079c4d
Create Date: 2025-10-26 18:30:34.419651

"""

from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence


# revision identifiers, used by Alembic.
revision: str = "10c4e8124417"
down_revision: Union[str, None] = "d99dc2079c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_protected column to model table."""
    op.add_column(
        "model", sa.Column("is_protected", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade() -> None:
    """Remove is_protected column from model table."""
    op.drop_column("model", "is_protected")
