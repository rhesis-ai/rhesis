"""Add explorer_row to test_set and test

Replaces the JSONB marker (attributes.metadata.behaviors contains "Adaptive
Testing") with a real boolean column, backfilled from that marker and from the
test_test_set association, then strips the marker out of attributes.

downgrade() restores the marker before dropping the column, using explorer_row
itself to know which rows need it back -- not a byte-for-byte inverse (the
original attributes.behaviors UUID reference isn't restored), but it makes a
rolled-back backend recognize Explorer sets again, including ones created after
this migration shipped (which never had the marker at all).

test/test_set/test_test_set have FORCE ROW LEVEL SECURITY, so a plain UPDATE
under a non-BYPASSRLS role would silently match zero rows. Both directions
disable RLS around their writes and fail loud if a verification query finds
rows the write should have touched but didn't, before RLS goes back on.

Revision ID: 7dd69fe35db5
Revises: 91607f0dd412
Create Date: 2026-08-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.idempotency import column_exists

# revision identifiers, used by Alembic.
revision: str = "7dd69fe35db5"
down_revision: Union[str, None] = "91607f0dd412"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables whose RLS we toggle for the backfill.
_RLS_TABLES = ("test_set", "test", "test_test_set")

# Mirrors EXPLORER_BEHAVIOR_NAME (app/constants.py) -- migrations can't import app code.
_EXPLORER_BEHAVIOR_NAME = "Adaptive Testing"

_TEST_SET_MATCH_PREDICATE = """
    attributes -> 'metadata' -> 'behaviors' @> :behavior_marker
"""


def _neutralize_rls_trigger_and_lock_timeout(conn) -> None:
    conn.execute(sa.text("SET LOCAL lock_timeout = '120s'"))
    conn.execute(sa.text("SET LOCAL auto_rls.active = 'true'"))


def _disable_rls(conn) -> dict:
    prior_rls: dict[str, bool] = {}
    for tbl in _RLS_TABLES:
        enabled = conn.execute(
            sa.text("SELECT relrowsecurity FROM pg_class WHERE relname = :t"),
            {"t": tbl},
        ).scalar()
        prior_rls[tbl] = bool(enabled)
        conn.execute(sa.text(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY"))
    return prior_rls


def _restore_rls(conn, prior_rls: dict) -> None:
    for tbl in _RLS_TABLES:
        if prior_rls[tbl]:
            conn.execute(sa.text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("SET LOCAL auto_rls.active = 'false'"))


def upgrade() -> None:
    conn = op.get_bind()
    behavior_marker = f'["{_EXPLORER_BEHAVIOR_NAME}"]'
    _neutralize_rls_trigger_and_lock_timeout(conn)

    # 1. Idempotent column adds.
    if not column_exists(conn, "test_set", "explorer_row"):
        op.add_column(
            "test_set",
            sa.Column("explorer_row", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not column_exists(conn, "test", "explorer_row"):
        op.add_column(
            "test",
            sa.Column("explorer_row", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    # 2. Disable RLS, capturing prior state to restore afterward.
    prior_rls = _disable_rls(conn)

    # 3. Backfill. No deleted_at filter -- flag soft-deleted rows too.
    conn.execute(
        sa.text(
            f"""
            UPDATE test_set SET explorer_row = true
            WHERE explorer_row = false
              AND {_TEST_SET_MATCH_PREDICATE}
            """
        ),
        {"behavior_marker": behavior_marker},
    )

    conn.execute(
        sa.text(
            """
            UPDATE test t SET explorer_row = true
            FROM test_test_set tts JOIN test_set ts ON ts.id = tts.test_set_id
            WHERE tts.test_id = t.id AND ts.explorer_row = true AND t.explorer_row = false
            """
        )
    )

    # 4. Fail loud if RLS silently filtered the backfill to zero rows.
    unflagged_test_sets = conn.execute(
        sa.text(
            f"SELECT count(*) FROM test_set WHERE explorer_row = false "
            f"AND {_TEST_SET_MATCH_PREDICATE}"
        ),
        {"behavior_marker": behavior_marker},
    ).scalar()
    if unflagged_test_sets:
        raise RuntimeError(
            f"explorer_row backfill left {unflagged_test_sets} test_set row(s) unflagged -- "
            "RLS likely filtered the UPDATE silently. Aborting before re-enabling RLS."
        )

    unflagged_tests = conn.execute(
        sa.text(
            """
            SELECT count(*)
            FROM test t
            JOIN test_test_set tts ON tts.test_id = t.id
            JOIN test_set ts ON ts.id = tts.test_set_id
            WHERE ts.explorer_row = true AND t.explorer_row = false
            """
        )
    ).scalar()
    if unflagged_tests:
        raise RuntimeError(
            f"explorer_row backfill left {unflagged_tests} test row(s) unflagged -- "
            "RLS likely filtered the UPDATE silently. Aborting before re-enabling RLS."
        )

    # 5. Strip the marker, then drop behaviors if that left it empty.
    conn.execute(
        sa.text(
            f"""
            UPDATE test_set
            SET attributes = jsonb_set(
                attributes,
                '{{metadata,behaviors}}',
                (attributes #> '{{metadata,behaviors}}') - :behavior_name
            )
            WHERE {_TEST_SET_MATCH_PREDICATE}
            """
        ),
        {"behavior_marker": behavior_marker, "behavior_name": _EXPLORER_BEHAVIOR_NAME},
    )
    conn.execute(
        sa.text(
            """
            UPDATE test_set
            SET attributes = attributes #- '{metadata,behaviors}'
            WHERE attributes #> '{metadata,behaviors}' = '[]'::jsonb
            """
        )
    )

    # 6. Restore RLS to its prior per-table state.
    _restore_rls(conn, prior_rls)


def downgrade() -> None:
    conn = op.get_bind()
    behavior_marker = f'["{_EXPLORER_BEHAVIOR_NAME}"]'
    _neutralize_rls_trigger_and_lock_timeout(conn)
    prior_rls = _disable_rls(conn)

    # Restore the marker on every row explorer_row still flags -- read it now,
    # before dropping the column erases that information for good.
    #
    # jsonb_set() raises "cannot set path in scalar" if the value already at
    # its target path exists but isn't an object/array (e.g. attributes.metadata
    # is a string). The two CASE guards below fall back to an empty object/array
    # in that situation instead of passing the scalar straight through -- same
    # "not a byte-for-byte inverse, just good enough to re-recognize the row"
    # philosophy as the null/malformed handling on the upgrade() side.
    conn.execute(
        sa.text(
            """
            UPDATE test_set
            SET attributes = jsonb_set(
                CASE WHEN jsonb_typeof(attributes) = 'object'
                     THEN attributes ELSE '{}'::jsonb END,
                '{metadata}',
                jsonb_set(
                    CASE WHEN jsonb_typeof(attributes -> 'metadata') = 'object'
                         THEN attributes -> 'metadata' ELSE '{}'::jsonb END,
                    '{behaviors}',
                    (CASE WHEN jsonb_typeof(attributes #> '{metadata,behaviors}') = 'array'
                          THEN attributes #> '{metadata,behaviors}' ELSE '[]'::jsonb END)
                        || CAST(:behavior_marker AS jsonb)
                )
            )
            WHERE explorer_row = true
              AND NOT COALESCE(attributes #> '{metadata,behaviors}', '[]'::jsonb)
                  @> CAST(:behavior_marker AS jsonb)
            """
        ),
        {"behavior_marker": behavior_marker},
    )

    unrestored = conn.execute(
        sa.text(
            """
            SELECT count(*) FROM test_set
            WHERE explorer_row = true
              AND NOT COALESCE(attributes #> '{metadata,behaviors}', '[]'::jsonb)
                  @> CAST(:behavior_marker AS jsonb)
            """
        ),
        {"behavior_marker": behavior_marker},
    ).scalar()
    if unrestored:
        raise RuntimeError(
            f"downgrade left {unrestored} test_set row(s) without the marker restored -- "
            "RLS likely filtered the UPDATE silently. Aborting before dropping the columns."
        )

    _restore_rls(conn, prior_rls)

    op.drop_column("test", "explorer_row")
    op.drop_column("test_set", "explorer_row")
