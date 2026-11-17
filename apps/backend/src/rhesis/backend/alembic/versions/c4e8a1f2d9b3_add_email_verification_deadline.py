"""add_email_verification_deadline

Adds ``user.email_verification_due_at`` and ``user.email_bounced_at``. A
password account that hasn't verified its email by the deadline, or whose
address bounced, can no longer sign in.

Existing unverified password accounts get the same 3-day grace from now.

Revision ID: c4e8a1f2d9b3
Revises: b7e2d4a9c31f
Create Date: 2026-11-16 12:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8a1f2d9b3"
down_revision: Union[str, None] = "b7e2d4a9c31f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "email_verification_due_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Unverified password accounts can't sign in after this",
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "email_bounced_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When mail to this address last hard-bounced",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE \"user\" SET email_verification_due_at = now() + interval '3 days' "
            "WHERE is_email_verified IS NOT TRUE AND password_hash IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("user", "email_bounced_at")
    op.drop_column("user", "email_verification_due_at")
