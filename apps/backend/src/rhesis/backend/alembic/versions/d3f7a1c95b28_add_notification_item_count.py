"""add_notification_item_count

One notification row can cover several entities -- a Garak import that creates
three test sets writes a single row carrying all three ids in
``payload["entity_ids"]``. The sidebar badge counted rows, so that batch read
as "1". ``item_count`` records how many things the row is about so the badge
can sum instead of count.

Backfilled from the existing payload for rows written before this column
existed; everything else stays at the default 1.

Revision ID: d3f7a1c95b28
Revises: b857edcac3c0
Create Date: 2026-08-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f7a1c95b28"
down_revision: Union[str, None] = "b857edcac3c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification",
        sa.Column("item_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.execute(
        """
        UPDATE notification
        SET item_count = jsonb_array_length(payload -> 'entity_ids')
        WHERE jsonb_typeof(payload -> 'entity_ids') = 'array'
          AND jsonb_array_length(payload -> 'entity_ids') > 0
        """
    )


def downgrade() -> None:
    op.drop_column("notification", "item_count")
