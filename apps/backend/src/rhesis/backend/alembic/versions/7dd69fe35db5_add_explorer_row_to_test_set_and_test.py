"""Add explorer_row to test_set and test

Replaces the JSONB marker (attributes.metadata.behaviors contains "Adaptive
Testing") with a real boolean column, backfilled from that marker and from the
test_test_set association. The marker itself is left in attributes, not
stripped: an org that happens to have a real Behavior literally named
"Adaptive Testing" tagged on an unrelated test set would otherwise have that
tag destructively deleted on top of the (already-possible) misflagging. Every
Explorer test set created going forward never writes the marker in the first
place (services/explorer/tests.py sets explorer_row directly), so this is a
one-time, existing-rows-only wart -- new sessions are clean, and the leftover
marker on old ones is inert once explorer_row is the source of truth.

downgrade() restores the marker before dropping the column, using explorer_row
itself to know which rows need it back -- not a byte-for-byte inverse (the
original attributes.behaviors UUID reference isn't restored), but it makes a
rolled-back backend recognize Explorer sets again, including ones created after
this migration shipped (which never had the marker at all). For rows that still
carry the marker from before upgrade() stopped stripping it, this is a no-op.

test/test_set/test_test_set have FORCE ROW LEVEL SECURITY, so a plain UPDATE
under a non-BYPASSRLS role would silently match zero rows. Both directions
disable RLS around their writes and fail loud if a verification query finds
rows the write should have touched but didn't, before RLS goes back on --
except when the connection's role already has BYPASSRLS (prod's rhesis-admin),
in which case the disable/enable dance is skipped entirely. That dance is
ALTER TABLE ... ROW LEVEL SECURITY, which takes an ACCESS EXCLUSIVE lock; on
these three hot tables that's a real production risk (a9b8c7d6e5f4 hit this
exact problem and stayed off hot tables entirely for that reason), so it's
worth skipping whenever the role doesn't actually need it.

Revision ID: 7dd69fe35db5
Revises: 91607f0dd412
Create Date: 2026-08-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.idempotency import column_exists, index_exists

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


def _has_bypassrls(conn) -> bool:
    """True if the connection's role already bypasses RLS (prod's rhesis-admin).

    When true, _disable_rls()/_restore_rls() below are skipped: their ALTER
    TABLE ... ROW LEVEL SECURITY calls take an ACCESS EXCLUSIVE lock, which is
    unnecessary risk on hot tables for a role that ignores RLS anyway.
    """
    return bool(
        conn.execute(
            sa.text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    )


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
        if prior_rls.get(tbl):
            conn.execute(sa.text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("SET LOCAL auto_rls.active = 'false'"))


def upgrade() -> None:
    conn = op.get_bind()
    behavior_marker = f'["{_EXPLORER_BEHAVIOR_NAME}"]'
    _neutralize_rls_trigger_and_lock_timeout(conn)
    bypasses_rls = _has_bypassrls(conn)

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

    # 2. Disable RLS, capturing prior state to restore afterward. Skipped when
    # the role already bypasses RLS -- see _has_bypassrls().
    prior_rls = {} if bypasses_rls else _disable_rls(conn)

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

    # 5. Index explorer_row -- it's the WHERE filter on every /test_sets
    # (exclude) and /explorer (include) listing, and had no index before this.
    if not index_exists(conn, "ix_test_set_explorer_row"):
        op.create_index("ix_test_set_explorer_row", "test_set", ["explorer_row"])
    if not index_exists(conn, "ix_test_explorer_row"):
        op.create_index("ix_test_explorer_row", "test", ["explorer_row"])

    # 6. Restore RLS to its prior per-table state (no-op if it was never disabled).
    # The marker itself is left in attributes on purpose -- see module docstring.
    _restore_rls(conn, prior_rls)


def downgrade() -> None:
    conn = op.get_bind()
    behavior_marker = f'["{_EXPLORER_BEHAVIOR_NAME}"]'
    _neutralize_rls_trigger_and_lock_timeout(conn)
    bypasses_rls = _has_bypassrls(conn)
    prior_rls = {} if bypasses_rls else _disable_rls(conn)

    # Restore the marker on every row explorer_row still flags -- read it now,
    # before dropping the column erases that information for good. The CASE
    # guards fall back to {}/[] when a value isn't the expected shape, since
    # jsonb_set() errors ("cannot set path in scalar") on a non-object target.
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

    if index_exists(conn, "ix_test_explorer_row"):
        op.drop_index("ix_test_explorer_row", table_name="test")
    if index_exists(conn, "ix_test_set_explorer_row"):
        op.drop_index("ix_test_set_explorer_row", table_name="test_set")

    op.drop_column("test", "explorer_row")
    op.drop_column("test_set", "explorer_row")
