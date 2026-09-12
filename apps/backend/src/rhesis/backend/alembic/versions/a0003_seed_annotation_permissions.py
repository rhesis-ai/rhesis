"""Seed annotation permission catalog entries and catch up EE custom roles

Seeds six ``annotation:*`` permissions into the ``permission`` table. Built-in
roles compute their sets from code (``permissions_for_built_in_role``), so no
``role_permission`` rows are needed for them.

For EE custom roles that already grant ``test_result:<action>``, a matching
``annotation:<action>`` row is inserted into ``role_permission`` so the custom
role's effective permissions mirror what its test_result grants imply.

Revision ID: a0003annperms
Revises: a0002annotbl
Create Date: 2026-09-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a0003annperms"
down_revision: Union[str, None] = "a0002annotbl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("annotation:read", "Read annotations", "annotation", "read", "project"),
    ("annotation:create", "Create annotation", "annotation", "create", "project"),
    ("annotation:update", "Update annotation", "annotation", "update", "project"),
    ("annotation:delete", "Delete annotation", "annotation", "delete", "project"),
    ("annotation:update:own", "Update own annotation", "annotation", "update:own", "project"),
    ("annotation:delete:own", "Delete own annotation", "annotation", "delete:own", "project"),
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

    result = conn.execute(
        sa.text(
            """
            INSERT INTO role_permission (id, role_id, permission_id, created_at, updated_at)
            SELECT gen_random_uuid(),
                   rp.role_id,
                   ann_perm.id,
                   now(),
                   now()
            FROM role_permission rp
            JOIN permission tr_perm ON rp.permission_id = tr_perm.id
            JOIN permission ann_perm ON ann_perm.resource_type = 'annotation'
                                    AND ann_perm.action = tr_perm.action
            JOIN role r ON rp.role_id = r.id
            WHERE tr_perm.resource_type = 'test_result'
              AND tr_perm.action IN (
                  'read', 'create', 'update', 'delete', 'update:own', 'delete:own'
              )
              AND r.is_built_in = false
            ON CONFLICT DO NOTHING
            """
        )
    )
    count = result.rowcount if result.rowcount is not None else 0
    if count:
        print(f"[a0003annperms] Granted annotation caps to custom roles: {count} row(s).")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM role_permission
            WHERE permission_id IN (
                SELECT id FROM permission WHERE resource_type = 'annotation'
            )
            """
        )
    )
    conn.execute(
        sa.text("DELETE FROM permission WHERE name = ANY(:names)"),
        {"names": [name for name, *_ in _NEW_PERMISSIONS]},
    )
