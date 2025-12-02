"""rename_protocol_to_connection_type_add_metadata

Renames protocol to connection_type in endpoint table, adds endpoint_metadata field,
and updates enum to include SDK connection type.

Revision ID: c6e7f9f35a99
Revises: 179eb8de14f1
Create Date: 2025-11-22 21:32:06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c6e7f9f35a99"
down_revision: Union[str, None] = "179eb8de14f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add endpoint_metadata column as JSONB
    op.add_column("endpoint", sa.Column("endpoint_metadata", postgresql.JSON(), nullable=True))

    # Rename protocol column to connection_type
    op.alter_column("endpoint", "protocol", new_column_name="connection_type")

    # Make url column nullable for SDK endpoints (which don't have URLs)
    op.alter_column("endpoint", "url", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Make url column non-nullable again
    op.alter_column("endpoint", "url", existing_type=sa.String(), nullable=False)

    # Rename connection_type back to protocol
    op.alter_column("endpoint", "connection_type", new_column_name="protocol")

    # Drop endpoint_metadata column
    op.drop_column("endpoint", "endpoint_metadata")
