"""Add parameter schema and request mapping to Insurance Chatbot

Adds the supported chatbot parameter schema to existing
"Example Project (Insurance Chatbot)" projects and the corresponding
parameter fields to existing "Insurance Chatbot" endpoint
``request_mapping`` rows so resolved project parameters are forwarded to
the chatbot during test execution.

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
PROJECT_NAME = "Example Project (Insurance Chatbot)"

CHATBOT_PARAMETER_SCHEMA = {
    "fields": [
        {
            "name": "system_prompt",
            "type": "text",
            "description": "Override the system prompt (blank = use markdown file)",
        },
        {
            "name": "use_case",
            "type": "enum",
            "default": {"type": "enum", "value": "insurance"},
            "options": [
                "baufinanzierung",
                "echo",
                "finance",
                "health",
                "insurance",
                "legal",
                "travel",
            ],
            "description": "Persona / context to adopt",
        },
        {
            "name": "model",
            "type": "string",
            "default": {"type": "string", "value": "rhesis/rhesis-default"},
            "description": "LLM provider string (e.g. vertex_ai/gemini-2.0-flash)",
        },
        {
            "name": "temperature",
            "type": "number",
            "default": {"type": "number", "value": 0.7},
        },
        {
            "name": "max_tokens",
            "type": "integer",
            "default": {"type": "integer", "value": 1024},
        },
        {
            "name": "output_mode",
            "type": "enum",
            "default": {"type": "enum", "value": "text"},
            "options": ["text", "json"],
        },
        {
            "name": "context_strategy",
            "type": "enum",
            "default": {"type": "enum", "value": "heuristic"},
            "options": ["heuristic", "rag", "none"],
        },
    ]
}

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
    """Add chatbot parameter schema and request_mapping keys."""
    conn = op.get_bind()

    conn.execute(
        text(
            """
            UPDATE project
            SET parameters_schema = CAST(:schema AS jsonb)
            WHERE name = :name
              AND (
                  parameters_schema IS NULL
                  OR jsonb_array_length(
                      COALESCE(parameters_schema::jsonb -> 'fields', '[]'::jsonb)
                  ) = 0
              )
            """
        ),
        {"name": PROJECT_NAME, "schema": json.dumps(CHATBOT_PARAMETER_SCHEMA)},
    )

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
    """Remove the chatbot parameter schema and request_mapping keys."""
    conn = op.get_bind()

    conn.execute(
        text(
            """
            UPDATE project
            SET parameters_schema = '{"fields": []}'::jsonb
            WHERE name = :name
              AND parameters_schema::jsonb = CAST(:schema AS jsonb)
            """
        ),
        {"name": PROJECT_NAME, "schema": json.dumps(CHATBOT_PARAMETER_SCHEMA)},
    )

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
