"""Add standalone indexes for the job retention sweep

The retention sweep (jobs/retention.py) deletes old job/activity_log rows,
looping per organization (both tables' tenant_isolation RLS policy is
FORCE'd, so a cross-org scan needs to be scoped per org rather than global).
Both tables' only existing created_at-shaped index is project-led
(ix_job_project_created, ix_activity_log_project_created), which does not
serve an org-scoped "past cutoff" scan efficiently.

``job`` is indexed on ``finished_at``, not ``created_at``: the sweep keys on
when a job finished, not when it started, so a long-running job is never a
candidate just because it's old. ``activity_log`` has no such distinction and
is indexed on its own ``created_at``.

Revision ID: f2b3c4d5e6a7
Revises: e6f7a8b9c0d1
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f2b3c4d5e6a7"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_job_finished_at", "job", ["finished_at"])
    op.create_index("ix_activity_log_created_at", "activity_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_log_created_at", table_name="activity_log")
    op.drop_index("ix_job_finished_at", table_name="job")
