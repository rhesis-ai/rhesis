"""Store notification timestamps with a time zone

The table was created with plain TIMESTAMP columns, unlike every other table (and
unlike the model, which declares DateTime(timezone=True)). The API then sent them
without an offset and browsers read the UTC values as local time, so a notification
created just now showed as "2h ago" in UTC+2. Existing values were written by now()
in UTC sessions, so they are converted as UTC.

Revision ID: c4f9e2a7d1b6
Revises: b5e2c8f41a93
Create Date: 2026-10-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c4f9e2a7d1b6"
down_revision: Union[str, None] = "b5e2c8f41a93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ("created_at", "updated_at", "deleted_at")


def _alter_all(target_type: str) -> None:
    # One statement, so the table is rewritten and locked once, not once per column.
    clauses = ", ".join(
        f"ALTER COLUMN {column} TYPE {target_type} USING {column} AT TIME ZONE 'UTC'"
        for column in COLUMNS
    )
    op.execute(f"ALTER TABLE notification {clauses}")


def upgrade() -> None:
    _alter_all("TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    _alter_all("TIMESTAMP WITHOUT TIME ZONE")
