"""Add endpoint.token_endpoint_auth_method

How an OAuth client-credentials endpoint sends its client ID and secret to the
token URL (RFC 7591 names). NULL means client_secret_basic, the method RFC 6749
requires every server to support.

Revision ID: d7a3e9b2c4f1
Revises: c4f9e2a7d1b6
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a3e9b2c4f1"
down_revision: Union[str, None] = "c4f9e2a7d1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("endpoint", sa.Column("token_endpoint_auth_method", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("endpoint", "token_endpoint_auth_method")
