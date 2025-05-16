"""add owner to organization

Revision ID: 3a611474f360
Revises: 2ff5b3e69a58
Create Date: 2025-03-24 09:56:24.411

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.app.models.guid import GUID

# revision identifiers, used by Alembic.
revision: str = "3a611474f360"
down_revision: Union[str, None] = (
    "2ff5b3e69a58"  # This was the last migration we saw in your codebase
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First add the columns without foreign key constraints
    op.add_column("organization", sa.Column("owner_id", GUID(), nullable=True))
    op.add_column("organization", sa.Column("user_id", GUID(), nullable=True))

    # Create the foreign key constraints with "initially deferred"
    op.create_foreign_key(
        "fk_organization_owner_id_user",
        "organization",
        "user",
        ["owner_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_organization_user_id_user",
        "organization",
        "user",
        ["user_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint("fk_organization_user_id_user", "organization", type_="foreignkey")
    op.drop_constraint("fk_organization_owner_id_user", "organization", type_="foreignkey")
    op.drop_column("organization", "user_id")
    op.drop_column("organization", "owner_id")
