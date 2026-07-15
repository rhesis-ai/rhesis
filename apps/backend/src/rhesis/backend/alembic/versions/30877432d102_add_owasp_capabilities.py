"""Add owasp:create / owasp:read capabilities

Inserts the permission-catalog rows for the new OWASP Top 10 test set
generation router (``GET /owasp/categories``, ``POST /owasp/generate``).
Mirrors the existing ``garak:create`` / ``garak:read`` seed — both capabilities
are route-derived (``resource="owasp"`` on the router, verb → action) so no
``Permission`` enum entry is required, only this catalog row for the
drift-guard test and custom-role UI.

No ``role_permission`` rows are inserted — built-in roles compute their sets
from code via ``permissions_for_built_in_role()``.

Revision ID: 30877432d102
Revises: 38ed899b9f41
Create Date: 2026-07-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "30877432d102"
down_revision: Union[str, None] = "38ed899b9f41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("owasp:create", "Create owasp", "owasp", "create", "project"),
    ("owasp:read", "Read owasp", "owasp", "read", "project"),
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
