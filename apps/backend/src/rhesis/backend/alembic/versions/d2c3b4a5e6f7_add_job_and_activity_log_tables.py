"""add job and activity_log tables

Backs the Jobs screen: ``job`` is one row per background-work dispatch,
``activity_log`` is the user-facing narrative attached to it.

``job.celery_task_id`` is indexed because polling a job's status by Celery id
is the hot read, and it replaces a lookup that loaded 100 test runs and scanned
a JSONB field in Python (``jobs/utils.py:get_test_run_by_task_id``).

``activity_log.job_id`` is **nullable** on purpose: an entry usually belongs to
a job, but a quota warning or a synchronous operation should be able to tell
the user something without a fake job to hang it from. CASCADE so purging a job
takes its narrative with it.

``project_id`` is nullable on both, following ``ProjectMixin``. NULL means
org-wide and visible from every project of the owning organization -- the
``project_isolation`` policy below spells that out with its
``OR project_id IS NULL`` arm. The tenant boundary is ``organization_id``.
NOT NULL was considered and rejected: a dispatch with no project in scope would
fail its insert, letting bookkeeping break real work.

RLS: both tables get ``tenant_isolation`` (ENABLE + FORCE) and, because both
carry ``project_id``, the RESTRICTIVE ``project_isolation`` policy. New tables
are not covered automatically, and
``tests/backend/security/test_rls_coverage.py`` fails without both.

Both tables are excluded from the generic recycle-bin routes (see
``routers/recycle.py``): restoring a swept job row is not a workflow anyone
wants, and the retention sweep hard-deletes rather than soft-deletes so rows do
not accumulate invisibly behind the soft-delete filter.

Revision ID: d2c3b4a5e6f7
Revises: 88430978b358
Create Date: 2026-08-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2c3b4a5e6f7"
down_revision: Union[str, None] = "88430978b358"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TENANT_ISOLATION = """
    CREATE POLICY tenant_isolation ON {table}
        USING (
            organization_id = NULLIF(
                current_setting('app.current_organization', true), ''
            )::uuid
        )
"""

_PROJECT_ISOLATION = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
            OR project_id IS NULL
            OR current_setting('app.current_project', true) = ''
        )
"""

# (index name, table, columns)
_INDEXES = [
    ("ix_job_celery_task_id", "job", ["celery_task_id"]),
    ("ix_job_organization_id", "job", ["organization_id"]),
    ("ix_job_project_created", "job", ["project_id", "created_at"]),
    ("ix_job_trace_id", "job", ["trace_id"]),
    # Not a duplicate of Base.deleted_at's index=True: raw op.create_table does
    # not honor that ORM-level flag, so nothing indexes the column until this
    # runs. Same two-step as 77df3dbea77d_add_usage_table.py.
    ("ix_job_deleted_at", "job", ["deleted_at"]),
    ("ix_activity_log_job_sequence", "activity_log", ["job_id", "sequence"]),
    ("ix_activity_log_organization_id", "activity_log", ["organization_id"]),
    ("ix_activity_log_project_created", "activity_log", ["project_id", "created_at"]),
    ("ix_activity_log_entity", "activity_log", ["entity_type", "entity_id"]),
    ("ix_activity_log_deleted_at", "activity_log", ["deleted_at"]),
]


def _base_columns() -> list:
    """The Base mixin's columns, which raw create_table must spell out."""
    return [
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("nano_id", sa.String(), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM information_schema.tables WHERE table_name=:t"),
            {"t": table},
        ).fetchone()
        is not None
    )


def _index_exists(conn, table: str, index: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE tablename=:t AND indexname=:i"),
            {"t": table, "i": index},
        ).fetchone()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "job"):
        op.create_table(
            "job",
            *_base_columns(),
            sa.Column(
                "organization_id",
                sa.dialects.postgresql.UUID(),
                sa.ForeignKey("organization.id"),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                sa.dialects.postgresql.UUID(),
                sa.ForeignKey("user.id"),
                nullable=True,
            ),
            sa.Column(
                "project_id",
                sa.dialects.postgresql.UUID(),
                sa.ForeignKey("project.id"),
                nullable=True,
            ),
            sa.Column("celery_task_id", sa.String(255), nullable=True),
            sa.Column("trace_id", sa.String(32), nullable=True),
            sa.Column("job_type", sa.String(255), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column(
                "status",
                sa.String(32),
                server_default=sa.text("'queued'"),
                nullable=False,
            ),
            sa.Column("entity_type", sa.String(64), nullable=True),
            sa.Column("entity_id", sa.dialects.postgresql.UUID(), nullable=True),
            sa.Column("progress_current", sa.Integer(), nullable=True),
            sa.Column("progress_total", sa.Integer(), nullable=True),
            sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.String(), nullable=True),
            sa.Column("error_type", sa.String(255), nullable=True),
            sa.Column("attempt", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("job_metadata", sa.dialects.postgresql.JSONB(), nullable=True),
        )

    if not _table_exists(conn, "activity_log"):
        op.create_table(
            "activity_log",
            *_base_columns(),
            sa.Column(
                "organization_id",
                sa.dialects.postgresql.UUID(),
                sa.ForeignKey("organization.id"),
                nullable=True,
            ),
            sa.Column(
                "project_id",
                sa.dialects.postgresql.UUID(),
                sa.ForeignKey("project.id"),
                nullable=True,
            ),
            sa.Column(
                "job_id",
                sa.dialects.postgresql.UUID(),
                sa.ForeignKey("job.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("entity_type", sa.String(64), nullable=True),
            sa.Column("entity_id", sa.dialects.postgresql.UUID(), nullable=True),
            sa.Column("source", sa.String(128), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=True),
            sa.Column("level", sa.String(16), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("context", sa.dialects.postgresql.JSONB(), nullable=True),
        )

    for index_name, table, columns in _INDEXES:
        if not _index_exists(conn, table, index_name):
            op.create_index(index_name, table, columns)

    for table in ("job", "activity_log"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(_TENANT_ISOLATION.format(table=table))
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(_PROJECT_ISOLATION.format(table=table))
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in ("activity_log", "job"):
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    # activity_log first: its job_id FK references job.
    op.drop_table("activity_log")
    op.drop_table("job")
