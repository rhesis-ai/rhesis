"""Add test_result.execution/verdict, the source of truth for pass/fail/error

test_result.status_id (Pass/Fail/Error) was the only place that decision
lived, and being a free-text status name with no constraint, every reader
grew its own synonym list to cope with legacy values -- see
playground/outcome-model/inventory.md for the resulting 14 vocabularies and
10 user-visible bugs, and playground/outcome-model/proposal.md for the model
this implements.

Two columns replace it as the source of truth for aggregation:

``execution`` -- did we obtain a usable observation? not_run / running / ok
    / error / cancelled.
``verdict`` -- given it ran, did it meet its criteria? pass / fail /
    inconclusive. Only meaningful when execution = 'ok', which the CHECK
    constraint below enforces rather than leaves to convention.

``status_id`` stays as a display/review artefact (app/outcomes.py's
docstring), but nothing should derive an outcome from it going forward.

Backfill reads the *status name*, not the stored metrics JSONB: the status
name already reflects any review override applied via
_set_pass_fail_status, so it is the more complete record for existing rows.
The synonym lists are hardcoded rather than imported, matching the existing
convention in the v_test_result_stats migrations -- an import here would
silently change historical backfill behavior if constants.py is edited
later.

Also drops the seeded 'Review' TestResult status: never written by any code
path, and read as an error by the backend and a Fail by the frontend where
it did appear. Guarded to skip any row that (unexpectedly) still references
it.

Revision ID: ff71b040aebf
Revises: f2b3c4d5e6a7
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "ff71b040aebf"
down_revision: Union[str, None] = "f2b3c4d5e6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors constants.py's TEST_RESULT_STATUS_PASSED / _FAILED at the time of
# this migration. Deliberately not imported -- see module docstring.
_PASSED_NAMES = (
    "'pass', 'passed', 'completed', 'complete', 'success', 'successful', 'finished', 'done'"
)
_FAILED_NAMES = "'fail', 'failed'"


def upgrade() -> None:
    op.execute("ALTER TABLE test_result ADD COLUMN execution TEXT")
    op.execute("ALTER TABLE test_result ADD COLUMN verdict TEXT")

    op.execute(
        f"""
        UPDATE test_result tr
        SET execution = CASE
                WHEN lower(s.name) = ANY (ARRAY[{_PASSED_NAMES}]) THEN 'ok'
                WHEN lower(s.name) = ANY (ARRAY[{_FAILED_NAMES}]) THEN 'ok'
                WHEN lower(s.name) = 'error' THEN 'error'
                ELSE 'not_run'
            END,
            verdict = CASE
                WHEN lower(s.name) = ANY (ARRAY[{_PASSED_NAMES}]) THEN 'pass'
                WHEN lower(s.name) = ANY (ARRAY[{_FAILED_NAMES}]) THEN 'fail'
                ELSE NULL
            END
        FROM status s
        WHERE tr.status_id = s.id
        """
    )
    # A test_result with no status_id at all (nullable FK) has no evidence
    # it ever ran -- same bucket as an unrecognized status name.
    op.execute("UPDATE test_result SET execution = 'not_run' WHERE execution IS NULL")

    op.alter_column("test_result", "execution", nullable=False, server_default="not_run")
    op.create_check_constraint(
        "ck_test_result_execution",
        "test_result",
        "execution IN ('not_run','running','ok','error','cancelled')",
    )
    op.create_check_constraint(
        "ck_test_result_verdict",
        "test_result",
        "verdict IS NULL OR verdict IN ('pass','fail','inconclusive')",
    )
    op.create_check_constraint(
        "ck_test_result_verdict_requires_ok",
        "test_result",
        "(execution = 'ok') = (verdict IS NOT NULL)",
    )

    op.execute(
        """
        DELETE FROM status s
        USING type_lookup tl
        WHERE s.entity_type_id = tl.id
          AND tl.type_name = 'EntityType'
          AND tl.type_value = 'TestResult'
          AND lower(s.name) = 'review'
          AND NOT EXISTS (
              SELECT 1 FROM test_result tr WHERE tr.status_id = s.id
          )
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_test_result_verdict_requires_ok", "test_result", type_="check")
    op.drop_constraint("ck_test_result_verdict", "test_result", type_="check")
    op.drop_constraint("ck_test_result_execution", "test_result", type_="check")
    op.drop_column("test_result", "verdict")
    op.drop_column("test_result", "execution")
