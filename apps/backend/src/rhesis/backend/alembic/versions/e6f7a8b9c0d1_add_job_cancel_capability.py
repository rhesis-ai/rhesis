"""Add the job:cancel capability to the permission catalog

POST /jobs/{id}/cancel asks a running background job to stop. Reading the
Jobs screen and being able to stop other people's work are different
privileges, so cancelling gets its own capability rather than riding on
job:read.

Project-scoped, matching job:read: jobs belong to a project, and the Jobs
screen shows one project at a time.

job:read itself is already in the catalog -- it was derived from the /jobs
route by the capability deriver before Permission.Job existed, so the seed
migration picked it up. Only cancel is new.

Built-in roles need no role_permission rows -- the EE provider computes their
sets from code -- so this only inserts the catalog row that custom roles FK
against, per the contract in
tests/backend/security/test_capability_catalog.py.

Revision ID: e6f7a8b9c0d1
Revises: d2c3b4a5e6f7
Create Date: 2026-08-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d2c3b4a5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CAPABILITY = "job:cancel"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permission "
            "(id, name, display_name, resource_type, action, scope, "
            "is_retired, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :name, 'Cancel job', 'job', 'cancel', "
            "'project', false, now(), now()) "
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
