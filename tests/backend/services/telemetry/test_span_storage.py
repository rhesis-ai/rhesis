"""Spans are enriched in the transaction that stores them (span_storage.store_spans)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app import models
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate
from rhesis.backend.app.services.telemetry.span_storage import store_spans


def _span(trace_id: str, project_id: str, span_id: str, parent=None, offset=0) -> OTELSpanCreate:
    start = datetime.now(timezone.utc) + timedelta(seconds=offset)
    return OTELSpanCreate(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent,
        project_id=project_id,
        environment="test",
        span_name="ai.llm.invoke",
        span_kind=SpanKind.INTERNAL,
        start_time=start,
        end_time=start + timedelta(milliseconds=250),
        status_code=StatusCode.OK,
        attributes={},
    )


def _stored(test_db, trace_id):
    test_db.expire_all()
    return test_db.query(models.Trace).filter(models.Trace.trace_id == trace_id).all()


@pytest.mark.integration
class TestStoreSpans:
    def test_new_spans_are_stored_enriched(self, test_db, test_organization, db_project):
        trace_id = uuid4().hex
        spans = [
            _span(trace_id, str(db_project.id), "a" * 16),
            _span(trace_id, str(db_project.id), "b" * 16, parent="a" * 16, offset=1),
        ]

        stored = store_spans(test_db, spans, str(test_organization.id))

        assert len(stored) == 2
        for row in _stored(test_db, trace_id):
            assert row.processed_at is not None
            assert row.enriched_data["metrics"]["span_count"] == 2

    def test_a_later_batch_re_enriches_the_whole_trace(
        self, test_db, test_organization, db_project
    ):
        trace_id = uuid4().hex
        project = str(db_project.id)
        store_spans(test_db, [_span(trace_id, project, "a" * 16)], str(test_organization.id))

        store_spans(
            test_db,
            [_span(trace_id, project, "b" * 16, parent="a" * 16, offset=1)],
            str(test_organization.id),
        )

        rows = _stored(test_db, trace_id)
        assert len(rows) == 2
        assert {row.enriched_data["metrics"]["span_count"] for row in rows} == {2}

    def test_a_resent_span_is_not_stored_twice(self, test_db, test_organization, db_project):
        trace_id = uuid4().hex
        span = _span(trace_id, str(db_project.id), "a" * 16)
        store_spans(test_db, [span], str(test_organization.id))

        again = store_spans(test_db, [span], str(test_organization.id))

        assert again == []
        assert len(_stored(test_db, trace_id)) == 1

    def test_a_span_repeated_in_one_batch_is_stored_once(
        self, test_db, test_organization, db_project
    ):
        trace_id = uuid4().hex
        span = _span(trace_id, str(db_project.id), "a" * 16)

        stored = store_spans(test_db, [span, span], str(test_organization.id))

        assert len(stored) == 1
        assert len(_stored(test_db, trace_id)) == 1

    def test_spans_are_kept_when_enrichment_fails(self, test_db, test_organization, db_project):
        trace_id = uuid4().hex
        with patch(
            "rhesis.backend.app.services.telemetry.span_storage.calculate_enrichment",
            side_effect=RuntimeError("no price list"),
        ):
            stored = store_spans(
                test_db, [_span(trace_id, str(db_project.id), "a" * 16)], str(test_organization.id)
            )

        assert len(stored) == 1
        assert _stored(test_db, trace_id)[0].processed_at is None


@pytest.mark.integration
def test_a_batch_is_stored_with_one_insert(test_db, test_organization, db_project):
    # A root span has no parent; it must not split the batch into two statements.
    from sqlalchemy import event

    inserts = []

    def count(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO TRACE"):
            inserts.append(statement)

    engine = test_db.get_bind()
    event.listen(engine, "before_cursor_execute", count)
    try:
        trace_id = uuid4().hex
        project = str(db_project.id)
        spans = [_span(trace_id, project, "0" * 16)] + [
            _span(trace_id, project, f"{i:016d}", parent="0" * 16, offset=i) for i in range(1, 9)
        ]
        stored = store_spans(test_db, spans, str(test_organization.id))
    finally:
        event.remove(engine, "before_cursor_execute", count)

    assert len(inserts) == 1
    assert len(stored) == 9
    assert len(_stored(test_db, trace_id)) == 9


@pytest.mark.integration
def test_a_later_batch_commits_once_with_the_lock_held(test_db, test_organization, db_project):
    # A commit before the insert would release the trace's ingest lock mid-store.
    from sqlalchemy import event

    trace_id = uuid4().hex
    project = str(db_project.id)
    store_spans(test_db, [_span(trace_id, project, "a" * 16)], str(test_organization.id))
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(" ".join(statement.split())[:40])

    engine = test_db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        store_spans(
            test_db,
            [_span(trace_id, project, "b" * 16, parent="a" * 16, offset=1)],
            str(test_organization.id),
        )
    finally:
        event.remove(engine, "before_cursor_execute", record)

    lock = next(i for i, s in enumerate(statements) if "pg_advisory_xact_lock" in s)
    ends = [i for i, s in enumerate(statements) if s.startswith(("COMMIT", "RELEASE SAVEPOINT"))]
    writes = [
        i for i, s in enumerate(statements) if s.startswith(("UPDATE trace", "INSERT INTO trace"))
    ]
    assert len(ends) == 1, statements
    assert lock < min(writes) and max(writes) < ends[0]


@pytest.mark.integration
def test_naive_timestamps_are_enriched_with_stored_spans(test_db, test_organization, db_project):
    trace_id = uuid4().hex
    project = str(db_project.id)
    store_spans(test_db, [_span(trace_id, project, "a" * 16)], str(test_organization.id))
    later = _span(trace_id, project, "b" * 16, parent="a" * 16, offset=1)
    later.start_time = later.start_time.replace(tzinfo=None)
    later.end_time = later.end_time.replace(tzinfo=None)

    store_spans(test_db, [later], str(test_organization.id))

    assert {row.enriched_data["metrics"]["span_count"] for row in _stored(test_db, trace_id)} == {2}


@pytest.mark.integration
def test_spans_stored_unenriched_are_enriched_for_legacy_messages(
    test_db, test_organization, db_project
):
    from rhesis.backend.app.crud.telemetry import create_trace_spans
    from rhesis.backend.app.services.telemetry.post_ingest import enrich_unprocessed_traces

    trace_id = uuid4().hex
    rows = create_trace_spans(
        test_db, [_span(trace_id, str(db_project.id), "a" * 16)], str(test_organization.id)
    )

    enriched = enrich_unprocessed_traces(
        test_db, rows, str(test_organization.id), str(db_project.id)
    )

    assert enriched == 1
    assert all(row.processed_at is not None for row in _stored(test_db, trace_id))


@pytest.mark.unit
def test_a_failed_linking_step_still_queues_evaluations_and_meters():
    from unittest.mock import MagicMock

    from rhesis.backend.app.services.telemetry.post_ingest import process_stored_spans

    db = MagicMock()
    spans = [MagicMock()]
    service = "rhesis.backend.app.services.telemetry"
    with (
        patch(
            f"{service}.linking_service.TraceLinkingService.link_traces_for_incoming_batch",
            side_effect=RuntimeError("statement timeout"),
        ),
        patch(f"{service}.conversation_linking.apply_pending_conversation_links", return_value=0),
        patch(f"{service}.conversation_linking.apply_pending_files", return_value=0),
        patch(
            f"{service}.enrichment.EnrichmentService.dispatch_for_spans", return_value=(1, 0)
        ) as dispatch,
        patch(f"{service}.post_ingest.usage_coalescer.add") as meter,
    ):
        result = process_stored_spans(db, spans, ["t"], "org", "project")

    db.rollback.assert_called()
    dispatch.assert_called_once()
    meter.assert_called_once()
    assert result["evaluations_queued"] == 1


@pytest.mark.integration
def test_stored_rows_are_persistent_and_load_server_defaults(
    test_db, test_organization, db_project
):
    from sqlalchemy import event, inspect

    rows = store_spans(
        test_db, [_span(uuid4().hex, str(db_project.id), "a" * 16)], str(test_organization.id)
    )
    row = rows[0]
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement.lstrip().split()[0].upper())

    engine = test_db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        test_db.flush()
        created_at = row.created_at
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert inspect(row).persistent
    assert "INSERT" not in statements
    assert created_at is not None
