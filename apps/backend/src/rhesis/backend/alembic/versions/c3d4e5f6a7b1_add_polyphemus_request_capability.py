"""Add polyphemus:request capability

Gates self-service Polyphemus access requests. Granted to built-in Member,
Admin, and Owner roles via ``permissions_for_built_in_role()``; excluded
from Viewer.

Revision ID: c3d4e5f6a7b1
Revises: b2c3d4e5f6a0
Create Date: 2026-07-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b1"
down_revision: Union[str, None] = "b2c3d4e5f6a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    (
        "polyphemus:request",
        "Request Polyphemus access",
        "polyphemus",
        "request",
        "organization",
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
