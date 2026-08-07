"""Add the usage:read capability to the permission catalog

``GET /usage`` and ``GET /usage/history`` were authz-exempt (authenticated,
but no permission check), so any org member could read the org's metered
consumption and plan limits over the API. They now require ``usage:read``.

A dedicated capability rather than reusing ``organization:read``: that one is
part of the read-only Viewer baseline (see ``_VIEWER_EXCLUDED_READS`` in
``ee.rbac.models``) for basic org context, so gating on it would not have
restricted anyone. ``usage:read`` is excluded from that baseline instead,
which lands it on Owner/Admin in EE, and on the org owner in community (via
``_OWNER_ONLY_CAPABILITIES`` in ``app.auth.rbac``).

Built-in roles need no ``role_permission`` rows -- the EE provider computes
their sets from code -- so this only inserts the catalog row that custom
roles FK against, per the contract in
``tests/backend/security/test_capability_catalog.py``.

Revision ID: e90c29496562
Revises: 7dd69fe35db5
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e90c29496562"
down_revision: Union[str, None] = "7dd69fe35db5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CAPABILITY = "usage:read"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permission "
            "(id, name, display_name, resource_type, action, scope, "
            "is_retired, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :name, 'Read usage', 'usage', 'read', "
            "'organization', false, now(), now()) "
            "ON CONFLICT (name) DO NOTHING"
        ).bindparams(name=_CAPABILITY)
    )


def downgrade() -> None:
    """Retire rather than delete, matching the catalog's append-only contract.

    ``permission`` rows are never hard-deleted: custom roles may hold
    ``role_permission`` rows pointing at this one, and those must stay
    auditable.
    """
    op.execute(
        sa.text("UPDATE permission SET is_retired = true WHERE name = :name").bindparams(
            name=_CAPABILITY
        )
    )
