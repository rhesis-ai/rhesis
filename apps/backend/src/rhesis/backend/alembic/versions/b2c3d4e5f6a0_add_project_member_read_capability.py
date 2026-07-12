"""Add project_member:read capability

Split listing project members from add/remove management. Viewers (and any
enrolled project member in the community tier) may list a project's roster via
``GET /projects/{id}/members``; ``project_member:manage`` continues to gate
POST/DELETE.

No ``role_permission`` rows are inserted — built-in roles compute their sets
from code via ``permissions_for_built_in_role()``.

Revision ID: b2c3d4e5f6a0
Revises: f9e8d7c6b5a4
Create Date: 2026-07-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a0"
down_revision: Union[str, None] = "f9e8d7c6b5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    (
        "project_member:read",
        "Read project member",
        "project_member",
        "read",
        "project",
    ),
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
