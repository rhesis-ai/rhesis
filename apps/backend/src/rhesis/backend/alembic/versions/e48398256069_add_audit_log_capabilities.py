"""Add the audit_log:read, audit_log:export and audit_log:manage capabilities

Org-scoped, for the Enterprise audit log. Owner and Admin hold all three. They
are kept out of the Viewer read baseline (``_VIEWER_EXCLUDED_READS`` in
``ee.rbac.models``) and, in community, reserved to the org owner
(``_OWNER_ONLY_CAPABILITIES`` in ``app.auth.rbac``).

Built-in roles need no ``role_permission`` rows -- the EE provider computes
their sets from code -- so this only inserts the catalog rows that custom roles
FK against, per the contract in
``tests/backend/security/test_capability_catalog.py``.

Revision ID: e48398256069
Revises: a9828a095ff7
Create Date: 2026-10-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e48398256069"
down_revision: Union[str, None] = "a9828a095ff7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name, display name, action)
_CAPABILITIES = [
    ("audit_log:read", "Read audit log", "read"),
    ("audit_log:export", "Export audit log", "export"),
    ("audit_log:manage", "Manage audit log settings", "manage"),
]


def upgrade() -> None:
    for name, display_name, action in _CAPABILITIES:
        op.execute(
            sa.text(
                "INSERT INTO permission "
                "(id, name, display_name, resource_type, action, scope, "
                "is_retired, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :name, :display_name, 'audit_log', :action, "
                "'organization', false, now(), now()) "
                # Un-retires the row when re-applied after a downgrade.
                "ON CONFLICT (name) DO UPDATE SET is_retired = false, updated_at = now()"
            ).bindparams(name=name, display_name=display_name, action=action)
        )


def downgrade() -> None:
    """Retire rather than delete, matching the catalog's append-only contract.

    ``permission`` rows are never hard-deleted: custom roles may hold
    ``role_permission`` rows pointing at these, and those must stay auditable.
    """
    for name, _, _ in _CAPABILITIES:
        op.execute(
            sa.text("UPDATE permission SET is_retired = true WHERE name = :name").bindparams(
                name=name
            )
        )
