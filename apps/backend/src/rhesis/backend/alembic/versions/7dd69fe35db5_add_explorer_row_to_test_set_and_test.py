"""Add explorer_row to test_set and test

Replaces the JSONB marker (attributes.metadata.behaviors contains "Adaptive
Testing") with a real boolean column, backfilled from that marker and from the
test_test_set association. The marker is left in attributes, not stripped: an
org with a real Behavior literally named "Adaptive Testing" on an unrelated
test set would otherwise have that tag destructively deleted. New Explorer
test sets never write the marker (services/explorer/tests.py sets
explorer_row directly), so this is a one-time wart on pre-migration rows only.

downgrade() only drops the column and its index -- it does not write the
marker back into attributes. A backend rolled back to a pre-explorer_row
version will not recognize as Explorer any test set created after this
migration shipped (those never had the marker); this migration does not
attempt to fix that up, to avoid mutating attributes/behaviors data at all
on the way down.

test_set/test have FORCE ROW LEVEL SECURITY, so a plain UPDATE under a
non-BYPASSRLS role would silently match zero rows. upgrade()'s backfill
disables RLS around its writes and fails loud if a verification query finds
unmatched rows, before RLS goes back on -- except when the role already has
BYPASSRLS (prod's rhesis-admin), which skips the disable/enable dance since
its ALTER TABLE ... ROW LEVEL SECURITY takes an ACCESS EXCLUSIVE lock on
these hot tables for no benefit to a role that ignores RLS anyway. downgrade()
does no DML, so it never needs that dance.

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
down_revision: Union[str, None] = "9550c62e80a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    """True if the connection's role already bypasses RLS (prod's rhesis-admin)."""
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

    prior_rls = {} if bypasses_rls else _disable_rls(conn)

    # No deleted_at filter -- flag soft-deleted rows too.
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

    # explorer_row is the WHERE filter on every /test_sets (exclude) and
    # /explorer (include) listing, and had no index before this.
    if not index_exists(conn, "ix_test_set_explorer_row"):
        op.create_index("ix_test_set_explorer_row", "test_set", ["explorer_row"])
    if not index_exists(conn, "ix_test_explorer_row"):
        op.create_index("ix_test_explorer_row", "test", ["explorer_row"])

    _restore_rls(conn, prior_rls)


def downgrade() -> None:
    conn = op.get_bind()
    _neutralize_rls_trigger_and_lock_timeout(conn)

    if index_exists(conn, "ix_test_explorer_row"):
        op.drop_index("ix_test_explorer_row", table_name="test")
    if index_exists(conn, "ix_test_set_explorer_row"):
        op.drop_index("ix_test_set_explorer_row", table_name="test_set")

    op.drop_column("test", "explorer_row")
    op.drop_column("test_set", "explorer_row")
