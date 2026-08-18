"""Add the notification:read capability

Gates all three notification routes: GET /notifications/summary,
GET /notifications, and POST /notifications/read. Granted to built-in Viewer,
Member, Admin, and Owner via ``permissions_for_built_in_role()`` (generic
":read" rule) -- no role-specific carve-out needed.

Mark-as-read rides on this one capability rather than a separate
``notification:update``: see ``Permission.Notification`` for why (a separate
:update would be denied to Viewer, who would then never be able to clear
their own badge).

Revision ID: 81fbf5ad9a1f
Revises: 449d5364b4ff
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "81fbf5ad9a1f"
down_revision: Union[str, None] = "449d5364b4ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    (
        "notification:read",
        "Read notifications",
        "notification",
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
    """Retire rather than delete, matching the catalog's append-only contract."""
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE permission SET is_retired = true WHERE name = :name"),
        [{"name": name} for name, *_ in _NEW_PERMISSIONS],
    )
