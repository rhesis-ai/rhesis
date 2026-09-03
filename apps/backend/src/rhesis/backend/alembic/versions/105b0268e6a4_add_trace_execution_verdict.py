"""Add trace.execution/verdict, so a trace has the same source of truth as a test result

ff71b040aebf gave ``test_result`` the two-axis outcome model
(app/outcomes.py). ``trace`` was left behind: its only record of an
outcome was ``trace_metrics_status_id``, a free-text status name. That
forced every trace reader -- backend and frontend alike -- to re-derive
pass/fail from the raw ``trace_metrics`` JSONB, which is exactly the
duplication the outcome model exists to remove.

The evaluation path already computes the pair and threw it away:
``jobs/telemetry/evaluate.py`` calls ``classify_metrics`` and keeps only
``outcome_to_test_result_status_name(...)``. These columns give it
somewhere to land.

``trace_metrics_status_id`` stays as the display/review artefact and as
the column the traces list filters on, exactly as ``status_id`` did for
``test_result``.

Backfill reads the status name, mirroring ff71b040aebf's reasoning: the
name already reflects any review override applied through
``trace_review_override``, so it is the more complete record for existing
rows. Unlike that migration this one also maps ``inconclusive`` -- the
status name existed before this column did (``TestResultStatus`` gained
INCONCLUSIVE in the same change that added ``classify_metrics``), so
trace rows carrying it can already exist.

A trace with no ``trace_metrics_status_id`` was never evaluated, which is
``not_run`` rather than an error.

Revision ID: 105b0268e6a4
Revises: 84d6c1464b96
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op

revision: str = "105b0268e6a4"
down_revision: Union[str, None] = "84d6c1464b96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors constants.py's TEST_RESULT_STATUS_PASSED / _FAILED at the time of
# this migration. Deliberately not imported -- an import would silently
# change historical backfill behaviour if constants.py is edited later
# (same convention as ff71b040aebf).
_PASSED_NAMES = (
    "'pass', 'passed', 'completed', 'complete', 'success', 'successful', 'finished', 'done'"
)
_FAILED_NAMES = "'fail', 'failed'"


def upgrade() -> None:
    op.execute("ALTER TABLE trace ADD COLUMN execution TEXT")
    op.execute("ALTER TABLE trace ADD COLUMN verdict TEXT")

    op.execute(
        f"""
        UPDATE trace t
        SET execution = CASE
                WHEN lower(s.name) = ANY (ARRAY[{_PASSED_NAMES}]) THEN 'ok'
                WHEN lower(s.name) = ANY (ARRAY[{_FAILED_NAMES}]) THEN 'ok'
                WHEN lower(s.name) = 'inconclusive' THEN 'ok'
                WHEN lower(s.name) = 'error' THEN 'error'
                ELSE 'not_run'
            END,
            verdict = CASE
                WHEN lower(s.name) = ANY (ARRAY[{_PASSED_NAMES}]) THEN 'pass'
                WHEN lower(s.name) = ANY (ARRAY[{_FAILED_NAMES}]) THEN 'fail'
                WHEN lower(s.name) = 'inconclusive' THEN 'inconclusive'
                ELSE NULL
            END
        FROM status s
        WHERE t.trace_metrics_status_id = s.id
        """
    )
    # Never evaluated (no status at all) -- no evidence it ever ran.
    op.execute("UPDATE trace SET execution = 'not_run' WHERE execution IS NULL")

    op.alter_column("trace", "execution", nullable=False, server_default="not_run")
    op.create_check_constraint(
        "ck_trace_execution",
        "trace",
        "execution IN ('not_run','running','ok','error','cancelled')",
    )
    op.create_check_constraint(
        "ck_trace_verdict",
        "trace",
        "verdict IS NULL OR verdict IN ('pass','fail','inconclusive')",
    )
    op.create_check_constraint(
        "ck_trace_verdict_requires_ok",
        "trace",
        "(execution = 'ok') = (verdict IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_trace_verdict_requires_ok", "trace", type_="check")
    op.drop_constraint("ck_trace_verdict", "trace", type_="check")
    op.drop_constraint("ck_trace_execution", "trace", type_="check")
    op.drop_column("trace", "verdict")
    op.drop_column("trace", "execution")
