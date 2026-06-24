"""Add :own-qualified comment capabilities (SP10)

Inserts ``comment:update:own`` and ``comment:delete:own`` into the ``permission``
table.  These capabilities are used by :func:`authorize_object` in SP10 to
enforce object-level ownership semantics: a caller may update or delete a
comment they created (``obj.user_id == principal.user_id``) without holding
the unrestricted ``comment:update`` / ``comment:delete`` permission.

No ``role_permission`` rows are inserted — built-in roles compute their sets
from code via ``permissions_for_built_in_role()``.  The EE models'
``_member_permissions`` helper already includes ``:own``-qualified project caps
(Owner/Admin/Member roles receive them; Viewer does not).

Developer rule: any new ``:own``-qualified capability must be added here AND to
the ``Permission`` enum in ``capabilities.py``.

Revision ID: 8e9f0a1b2c3d
Revises: 7d8e9f0a1b2c
Create Date: 2026-06-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8e9f0a1b2c3d"
down_revision: Union[str, None] = "7d8e9f0a1b2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("comment:update:own", "Update own comment", "comment", "update:own", "project"),
    ("comment:delete:own", "Delete own comment", "comment", "delete:own", "project"),
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
