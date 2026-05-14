"""add parameter management tables and columns

Introduces the data model that backs the Parameter Management feature:

- ``project.parameters_schema`` and ``project.parameter_environments`` are
  added as JSONB columns on the existing ``project`` table. Both default
  to empty Pydantic-shaped JSON (``{"fields": []}`` / ``{"environments": {}}``)
  so existing projects pick up the feature without a row migration.
- ``experiment`` is a new per-organization table holding named, owned
  attempts at a configuration. Versions are stored inline in a JSONB
  array so a single row carries the full history; idempotent appends
  and visibility checks are enforced at the route layer.
- Two partial unique indexes split the ``(project_id, name)``
  invariant by visibility: private experiments are unique per
  ``(project_id, owner_user_id, name)``, shared experiments are unique
  per ``(project_id, name)``. Visibility flips (``private`` → ``shared``
  and vice versa) re-enter the other invariant; the route layer
  validates that flipping does not produce a collision before issuing
  the UPDATE.
- Two btree expression indexes on ``test_run.attributes->>'…'`` cover
  the run-side queries that Phases 4 and 5 rely on (resolve "which
  runs used this experiment / version"). Adding them here means Phase
  4 ships without a follow-up migration.
- RLS is explicitly enabled and a tenant_isolation policy is created
  on the new ``experiment`` table. The original blanket RLS migration
  ran a one-time loop over existing tables, so any new
  ``organization_id``-bearing table must opt in itself.

Revision ID: e1a2b3c4d5e6
Revises: d8b3a1f2c4e5
Create Date: 2026-05-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, None] = "d8b3a1f2c4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def _index_exists(table: str, index_name: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename = :t AND indexname = :i"
        ),
        {"t": table, "i": index_name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # project: add the two JSONB columns                                 #
    # ------------------------------------------------------------------ #
    if not _column_exists("project", "parameters_schema"):
        op.add_column(
            "project",
            sa.Column(
                "parameters_schema",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{\"fields\": []}'::jsonb"),
            ),
        )
    if not _column_exists("project", "parameter_environments"):
        op.add_column(
            "project",
            sa.Column(
                "parameter_environments",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{\"environments\": {}}'::jsonb"),
            ),
        )

    # ------------------------------------------------------------------ #
    # experiment: new table                                              #
    # ------------------------------------------------------------------ #
    if not _table_exists("experiment"):
        op.create_table(
            "experiment",
            sa.Column(
                "id",
                postgresql.UUID(),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("nano_id", sa.String(), unique=True, nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column(
                "organization_id",
                postgresql.UUID(),
                sa.ForeignKey("organization.id"),
                nullable=False,
            ),
            sa.Column(
                "project_id",
                postgresql.UUID(),
                sa.ForeignKey("project.id"),
                nullable=False,
            ),
            sa.Column(
                "owner_user_id",
                postgresql.UUID(),
                sa.ForeignKey("user.id"),
                nullable=False,
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "visibility",
                sa.String(16),
                nullable=False,
                server_default="private",
            ),
            sa.Column(
                "versions",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "update_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.CheckConstraint(
                "visibility IN ('private', 'shared')",
                name="ck_experiment_visibility",
            ),
        )

    # Indexes ---------------------------------------------------------- #
    if not _index_exists("experiment", "ix_experiment_organization_id"):
        op.create_index(
            "ix_experiment_organization_id",
            "experiment",
            ["organization_id"],
        )
    if not _index_exists("experiment", "ix_experiment_project_id"):
        op.create_index(
            "ix_experiment_project_id",
            "experiment",
            ["project_id"],
        )
    if not _index_exists("experiment", "ix_experiment_owner_user_id"):
        op.create_index(
            "ix_experiment_owner_user_id",
            "experiment",
            ["owner_user_id"],
        )
    if not _index_exists("experiment", "ix_experiment_deleted_at"):
        op.create_index(
            "ix_experiment_deleted_at",
            "experiment",
            ["deleted_at"],
        )

    # Partial unique indexes split by visibility. The WHERE predicate
    # also excludes soft-deleted rows so renaming a private experiment
    # and recreating with the old name is not blocked by tombstones.
    if not _index_exists("experiment", "uq_experiment_private_name"):
        op.create_index(
            "uq_experiment_private_name",
            "experiment",
            ["project_id", "owner_user_id", "name"],
            unique=True,
            postgresql_where=sa.text(
                "visibility = 'private' AND deleted_at IS NULL"
            ),
        )
    if not _index_exists("experiment", "uq_experiment_shared_name"):
        op.create_index(
            "uq_experiment_shared_name",
            "experiment",
            ["project_id", "name"],
            unique=True,
            postgresql_where=sa.text(
                "visibility = 'shared' AND deleted_at IS NULL"
            ),
        )

    # ------------------------------------------------------------------ #
    # RLS for the new experiment table                                   #
    # ------------------------------------------------------------------ #
    op.execute(
        "ALTER TABLE public.experiment ENABLE ROW LEVEL SECURITY"
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.experiment")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON public.experiment
        USING (organization_id = current_setting('app.current_organization')::uuid);
        """
    )

    # ------------------------------------------------------------------ #
    # test_run expression indexes used by Phases 4 / 5                   #
    # ------------------------------------------------------------------ #
    if not _index_exists("test_run", "ix_test_run_attr_parameter_version"):
        op.execute(
            "CREATE INDEX ix_test_run_attr_parameter_version "
            "ON public.test_run "
            "((attributes->>'parameter_version')) "
            "WHERE attributes ? 'parameter_version'"
        )
    if not _index_exists("test_run", "ix_test_run_attr_parameter_experiment_id"):
        op.execute(
            "CREATE INDEX ix_test_run_attr_parameter_experiment_id "
            "ON public.test_run "
            "((attributes->>'parameter_experiment_id')) "
            "WHERE attributes ? 'parameter_experiment_id'"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_test_run_attr_parameter_experiment_id")
    op.execute("DROP INDEX IF EXISTS ix_test_run_attr_parameter_version")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.experiment")

    op.execute("DROP INDEX IF EXISTS uq_experiment_shared_name")
    op.execute("DROP INDEX IF EXISTS uq_experiment_private_name")
    op.execute("DROP INDEX IF EXISTS ix_experiment_deleted_at")
    op.execute("DROP INDEX IF EXISTS ix_experiment_owner_user_id")
    op.execute("DROP INDEX IF EXISTS ix_experiment_project_id")
    op.execute("DROP INDEX IF EXISTS ix_experiment_organization_id")
    op.execute("DROP TABLE IF EXISTS public.experiment")

    op.execute("ALTER TABLE project DROP COLUMN IF EXISTS parameter_environments")
    op.execute("ALTER TABLE project DROP COLUMN IF EXISTS parameters_schema")
