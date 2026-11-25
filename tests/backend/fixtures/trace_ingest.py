"""Run queued trace ingest inline, on the test's own session.

Both ingest routes queue spans for a Celery worker. Tests have no worker, and a
worker's own session could not see (or be rolled back with) the test's
transaction, so the queue is replaced by storing each message right away in a
session of its own on the test connection (as a worker has its own session).
The message still goes through its wire format.
"""

import pytest


@pytest.fixture(autouse=True)
def inline_trace_ingest(request, monkeypatch):
    from rhesis.backend.app.auth import feature_gates, quota_gates
    from rhesis.backend.app.config.settings import get_trace_ingest_settings
    from rhesis.backend.app.routers import telemetry_intake
    from rhesis.backend.app.services.telemetry.ingest import IngestJob, process_ingest_job
    from rhesis.backend.jobs.telemetry import ingest as ingest_jobs

    stored = []

    def enqueue_inline(job: IngestJob, max_message_bytes: int) -> int:
        from tests.backend.fixtures.database import TestingSessionLocal

        test_db = request.getfixturevalue("test_db")
        messages = job.messages(max_message_bytes)
        for message in messages:
            # Opened and closed inside the request's own savepoint, so they nest.
            db = TestingSessionLocal(
                bind=test_db.get_bind(), join_transaction_mode="create_savepoint"
            )
            try:
                stored.append(process_ingest_job(db, IngestJob.from_message(message)))
            finally:
                db.close()
        return len(messages)

    def check_project_access_on_test_db(http_request, current_user, project_id):
        # The routes check on a session of their own, which could not see the
        # test's uncommitted project; check on one bound to the test connection.
        from rhesis.backend.app.dependencies import assert_project_access
        from tests.backend.fixtures.database import _yield_fresh_session

        with _yield_fresh_session(request.getfixturevalue("test_db")) as db:
            return assert_project_access(http_request, current_user, project_id, db=db)

    def test_db_session(*_args):
        from tests.backend.fixtures.database import _yield_fresh_session

        return _yield_fresh_session(request.getfixturevalue("test_db"))

    # The ingest gates check on short sessions of their own; point them at the test connection.
    monkeypatch.setattr(feature_gates, "short_session", test_db_session)
    monkeypatch.setattr(quota_gates, "backstop_session", test_db_session)
    monkeypatch.setattr(ingest_jobs, "enqueue_ingest", enqueue_inline)
    monkeypatch.setattr(telemetry_intake, "check_project_access", check_project_access_on_test_db)
    # The shared Redis checks are off by default here: the test broker's queue
    # fills with post-ingest jobs nobody consumes. Tests of the limits opt in.
    limits = get_trace_ingest_settings().model_copy(
        update={"max_queue_depth": 0, "org_bytes_per_minute": 0}
    )
    monkeypatch.setattr(telemetry_intake, "settings", lambda: limits)
    return stored
