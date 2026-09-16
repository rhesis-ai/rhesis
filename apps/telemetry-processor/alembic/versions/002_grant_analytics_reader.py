"""grant the Grafana reader role read-only access

Revision ID: 002
Revises: 001
Create Date: 2026-09-16

The Grafana telemetry dashboard reads these tables through the "grafana-viewer" role,
which the infrastructure creates alongside the cluster (spec.managed.roles in the stg/prd
CNPG manifests, an initdb script in dev). That role cannot be granted access by the
infrastructure, though: these tables live in a second database that CNPG's bootstrap
hooks cannot reach, and they do not exist yet at bootstrap time because this migration
chain is what creates them. The owner of the tables is the only party that can grant on
them, and that owner is whoever runs this migration.

Deployments without Grafana, including self-hosted ones, have no such role. The grant is
therefore skipped when the role is absent rather than failing the migration, since this
runs on every startup path including theirs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed identifier, not caller input. Postgres cannot parameterize identifiers, so it is
# interpolated; keep it a literal constant so there is nothing to inject.
READER_ROLE = "grafana-viewer"


def _role_exists(conn) -> bool:
    return bool(
        conn.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": READER_ROLE}
        ).scalar()
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _role_exists(conn):
        return

    conn.execute(sa.text(f'GRANT USAGE ON SCHEMA public TO "{READER_ROLE}"'))
    conn.execute(sa.text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{READER_ROLE}"'))
    # No FOR ROLE: this applies to the role running the migration, which is the one that
    # creates the tables, so tables added by later revisions are covered without needing
    # another grant.
    conn.execute(
        sa.text(
            f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "{READER_ROLE}"'
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not _role_exists(conn):
        return

    conn.execute(
        sa.text(
            f'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM "{READER_ROLE}"'
        )
    )
    conn.execute(sa.text(f'REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM "{READER_ROLE}"'))
    conn.execute(sa.text(f'REVOKE USAGE ON SCHEMA public FROM "{READER_ROLE}"'))
