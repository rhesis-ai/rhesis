"""Add task, experiment, test_result and test_run :own/:assigned capabilities (SP10 follow-up)

Seeds eight new entries into the ``permission`` table:

- ``task:update:own``      – creator may edit a task
- ``task:update:assigned`` – assignee may edit a task
- ``task:delete:own``      – creator may delete a task
- ``experiment:update:own``  – creator may update an experiment  (was missing)
- ``experiment:delete:own``  – creator may delete an experiment  (was missing)
- ``test_result:update:own`` – creator may update a test_result (was missing)
- ``test_result:delete:own`` – creator may delete a test_result (was missing)
- ``test_run:delete:own``    – creator may delete a test_run    (was missing)

The experiment, test_result, and test_run caps were declared in ``Permission``
during earlier sprints but never seeded; without this migration the
capability-catalog drift guard test would fail.

No ``role_permission`` rows are inserted — built-in roles compute their sets
from code via ``permissions_for_built_in_role()`` / EE ``_member_permissions``.

Developer rule: any new ``:own`` / ``:assigned`` capability must also be
added to the ``Permission`` enum in ``capabilities.py``.

Revision ID: c0d1e2f3a4b5
Revises: b1c2d3e4f5a6
Create Date: 2026-06-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("task:update:own", "Update own task", "task", "update:own", "project"),
    ("task:update:assigned", "Update assigned task", "task", "update:assigned", "project"),
    ("task:delete:own", "Delete own task", "task", "delete:own", "project"),
    ("experiment:update:own", "Update own experiment", "experiment", "update:own", "project"),
    ("experiment:delete:own", "Delete own experiment", "experiment", "delete:own", "project"),
    ("test_result:update:own", "Update own test result", "test_result", "update:own", "project"),
    ("test_result:delete:own", "Delete own test result", "test_result", "delete:own", "project"),
    ("test_run:delete:own", "Delete own test run", "test_run", "delete:own", "project"),
]


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO permission (
                id, name, display_name, resource_type, action, scope,
                is_retired, created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), :name, :display_name, :resource_type,
                :action, :scope, false, now(), now()
            )
            ON CONFLICT (name) DO NOTHING
            """
        ),
        [
            {
                "name": name,
                "display_name": display_name,
                "resource_type": resource_type,
                "action": action,
                "scope": scope,
            }
            for name, display_name, resource_type, action, scope in _NEW_PERMISSIONS
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM permission WHERE name = ANY(:names)"),
        {"names": [name for name, *_ in _NEW_PERMISSIONS]},
    )
