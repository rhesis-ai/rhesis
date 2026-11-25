"""The ingest gates' own sessions open and close (tests otherwise patch them)."""

from sqlalchemy import text

from rhesis.backend.app.auth import feature_gates, quota_gates


def test_feature_gate_short_session_runs_a_query():
    with feature_gates.short_session() as db:
        assert db.execute(text("SELECT 1")).scalar() == 1


def test_backstop_session_runs_a_query(test_org_id, authenticated_user_id):
    with quota_gates.backstop_session(test_org_id, authenticated_user_id) as db:
        assert db.execute(text("SELECT 1")).scalar() == 1
