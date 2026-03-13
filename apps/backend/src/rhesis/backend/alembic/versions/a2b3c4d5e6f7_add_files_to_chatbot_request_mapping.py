"""Add files to Insurance Chatbot endpoint request_mapping

Adds ``"files": "{{ files }}"`` to the ``request_mapping`` json column of
every "Insurance Chatbot" endpoint that does not yet have it, so that file
attachments on tests are forwarded to the chatbot during execution.

The operation is fully idempotent: endpoints already carrying a ``files`` key
in their request_mapping are left untouched, so the migration is safe to run
more than once and handles organisations that configured this ahead of the
release.

Revision ID: a2b3c4d5e6f7
Revises: c4d5e6f7a8b9
Create Date: 2026-03-13
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENDPOINT_NAME = "Insurance Chatbot"


def upgrade() -> None:
    """Add files key to request_mapping where it is absent."""
    conn = op.get_bind()

    # request_mapping is stored as json (not jsonb), so cast to jsonb for the
    # merge operator (||) and key-existence check, then cast back to json.
    conn.execute(
        text(
            """
            UPDATE endpoint
            SET request_mapping = (
                COALESCE(request_mapping::jsonb, '{}'::jsonb)
                || '{"files": "{{ files }}"}'::jsonb
            )::json
            WHERE name = :name
              AND (
                  request_mapping IS NULL
                  OR (request_mapping->>'files') IS NULL
              )
            """
        ),
        {"name": ENDPOINT_NAME},
    )


def downgrade() -> None:
    """Remove the files key from request_mapping."""
    conn = op.get_bind()

    conn.execute(
        text(
            """
            UPDATE endpoint
            SET request_mapping = (request_mapping::jsonb - 'files')::json
            WHERE name = :name
              AND (request_mapping->>'files') IS NOT NULL
            """
        ),
        {"name": ENDPOINT_NAME},
    )
