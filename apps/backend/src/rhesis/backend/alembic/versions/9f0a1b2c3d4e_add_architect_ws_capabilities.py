"""Add architect/preflight WebSocket capabilities (SP11)

Seeds the capability strings used by the WebSocket channel authorizer and the
architect message → agent-run enqueue gate.  These are checked in handler code
(``services/websocket/...``) rather than on an HTTP route, so they never appear
via the resource×verb route deriver — but they must exist in the ``permission``
table so custom roles can be granted them and so the catalog stays complete.

- ``architect:read``   — subscribe to an ``architect:{id}`` channel.
- ``architect:create`` — send a message that enqueues an agent run (SP11 gate).
- ``preflight:create`` — initiate an ephemeral preflight operation channel.

Built-in roles compute their sets from code (``permissions_for_built_in_role``):
Member/Owner/Admin receive these (project-scoped create/read); Viewer receives
only ``architect:read``.  No ``role_permission`` rows are inserted.

Developer rule: any new WebSocket-checked capability must be added here AND to
the ``Permission`` enum in ``capabilities.py``.

Revision ID: 9f0a1b2c3d4e
Revises: 8e9f0a1b2c3d
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9f0a1b2c3d4e"
down_revision: Union[str, None] = "8e9f0a1b2c3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("architect:read", "Read architect sessions", "architect", "read", "project"),
    ("architect:create", "Run architect agent", "architect", "create", "project"),
    ("preflight:create", "Run preflight checks", "preflight", "create", "project"),
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
