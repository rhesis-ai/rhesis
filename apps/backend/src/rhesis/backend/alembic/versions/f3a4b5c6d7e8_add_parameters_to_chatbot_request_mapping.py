"""Add parameter fields to Insurance Chatbot endpoint request_mapping

Adds the supported chatbot parameter fields to existing "Insurance Chatbot"
endpoint ``request_mapping`` rows so resolved project parameters are forwarded
to the chatbot during test execution.

Revision ID: f3a4b5c6d7e8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-20
"""

import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENDPOINT_NAME = "Insurance Chatbot"
PARAMETER_MAPPINGS = {
    "system_prompt": "{{ params.system_prompt | default(none) }}",
    "use_case": "{{ params.use_case | default('insurance') }}",
    "model": "{{ params.model | default(none) }}",
    "temperature": "{{ params.temperature | default(0.7) }}",
    "max_tokens": "{{ params.max_tokens | default(1024) }}",
    "mode": "{{ params.output_mode | default('text') }}",
    "context_strategy": "{{ params.context_strategy | default('heuristic') }}",
}
PARAMETER_KEYS = tuple(PARAMETER_MAPPINGS)


def upgrade() -> None:
    """Add supported parameter keys to request_mapping where absent."""
    conn = op.get_bind()

    for key, template in PARAMETER_MAPPINGS.items():
        conn.execute(
            text(
                """
                UPDATE endpoint
                SET request_mapping = (
                    COALESCE(request_mapping::jsonb, '{}'::jsonb)
                    || CAST(:mapping AS jsonb)
                )::json
                WHERE name = :name
                  AND (
                      request_mapping IS NULL
                      OR (request_mapping ->> :key) IS NULL
                  )
                """
            ),
            {"name": ENDPOINT_NAME, "key": key, "mapping": json.dumps({key: template})},
        )

    conn.execute(
        text(
            """
            UPDATE endpoint
            SET request_mapping = (request_mapping::jsonb - 'parameters')::json
            WHERE name = :name
              AND (request_mapping ->> 'parameters') IS NOT NULL
            """
        ),
        {"name": ENDPOINT_NAME},
    )


def downgrade() -> None:
    """Remove the parameter keys from request_mapping."""
    conn = op.get_bind()

    for key in PARAMETER_KEYS:
        conn.execute(
            text(
                """
                UPDATE endpoint
                SET request_mapping = (request_mapping::jsonb - :key)::json
                WHERE name = :name
                  AND (request_mapping ->> :key) IS NOT NULL
                """
            ),
            {"name": ENDPOINT_NAME, "key": key},
        )
