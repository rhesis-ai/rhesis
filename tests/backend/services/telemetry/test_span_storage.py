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
