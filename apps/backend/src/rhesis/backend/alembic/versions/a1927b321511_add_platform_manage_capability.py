"""Add the platform:manage capability to the permission catalog

PUT/DELETE /platform/rhesis-key (org-scoped Rhesis platform API key
management for local/self-hosted deployments) previously required only
authentication, letting any org member overwrite or clear the org-wide key.
They now require platform:manage, which resolves to the org owner only in
community mode via _OWNER_ONLY_CAPABILITIES in app.auth.rbac.

Built-in roles need no role_permission rows -- the EE provider computes
their sets from code -- so this only inserts the catalog row that custom
roles FK against, per the contract in
tests/backend/security/test_capability_catalog.py.

Revision ID: a1927b321511
Revises: a7f3c2e1d9b4
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1927b321511"
down_revision: Union[str, None] = "a7f3c2e1d9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CAPABILITY = "platform:manage"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permission "
            "(id, name, display_name, resource_type, action, scope, "
            "is_retired, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :name, 'Manage platform key', 'platform', 'manage', "
            "'organization', false, now(), now()) "
            "ON CONFLICT (name) DO NOTHING"
        ).bindparams(name=_CAPABILITY)
    )


def downgrade() -> None:
    """Retire rather than delete, matching the catalog's append-only contract.

    permission rows are never hard-deleted: custom roles may hold
    role_permission rows pointing at this one, and those must stay auditable.
    """
    op.execute(
        sa.text("UPDATE permission SET is_retired = true WHERE name = :name").bindparams(
            name=_CAPABILITY
        )
    )
