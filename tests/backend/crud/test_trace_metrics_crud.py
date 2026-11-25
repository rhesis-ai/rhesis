"""Writing turn and conversation metrics onto stored spans."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from rhesis.telemetry.schemas import SpanKind, StatusCode
from sqlalchemy import event

from rhesis.backend.app import models
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.crud.telemetry import (
    update_trace_conversation_metrics,
    update_trace_turn_metrics,
)
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate
from rhesis.backend.app.services.telemetry.span_storage import store_spans
from rhesis.backend.app.utils.crud_utils import get_or_create_status


def _store_trace(db, organization_id, project_id, span_count=1):
    trace_id = uuid4().hex
    start = datetime.now(timezone.utc)
    spans = [
        OTELSpanCreate(
            trace_id=trace_id,
            span_id=f"{i:016d}",
            parent_span_id=None if i == 0 else "0" * 16,
            project_id=project_id,
            environment="test",
            span_name="function.chat",
            span_kind=SpanKind.SERVER,
            start_time=start + timedelta(milliseconds=i),
            end_time=start + timedelta(milliseconds=i + 100),
            status_code=StatusCode.OK,
            attributes={},
        )
        for i in range(span_count)
    ]
    rows = store_spans(db, spans, organization_id)
    return trace_id, rows


def _rows(db, trace_id):
    db.expire_all()
    return db.query(models.Trace).filter(models.Trace.trace_id == trace_id).all()


@pytest.mark.integration
class TestUpdateTraceTurnMetrics:
    def test_sets_turn_metrics_on_one_span(self, test_db, test_organization, db_project):
        trace_id, rows = _store_trace(test_db, str(test_organization.id), str(db_project.id), 2)
        root = rows[0]

        updated = update_trace_turn_metrics(test_db, str(root.id), {"latency_ms": 42})

        assert updated == 1
        by_id = {row.id: row for row in _rows(test_db, trace_id)}
        assert by_id[root.id].trace_metrics == {"turn_metrics": {"latency_ms": 42}}
        assert by_id[root.id].trace_metrics_processed_at is not None
        assert by_id[rows[1].id].trace_metrics is None

    def test_keeps_conversation_metrics(self, test_db, test_organization, db_project):
        trace_id, rows = _store_trace(test_db, str(test_organization.id), str(db_project.id))
        update_trace_conversation_metrics(test_db, trace_id, {"conv": "data"})

        update_trace_turn_metrics(test_db, str(rows[0].id), {"new": 1})

        assert _rows(test_db, trace_id)[0].trace_metrics == {
            "conversation_metrics": {"conv": "data"},
            "turn_metrics": {"new": 1},
        }

    def test_a_missing_span_updates_nothing(self, test_db):
        assert update_trace_turn_metrics(test_db, str(uuid4()), {"x": 1}) == 0

    def test_writes_status_and_outcome(self, test_db, test_organization, db_project):
        trace_id, rows = _store_trace(test_db, str(test_organization.id), str(db_project.id))
        status = get_or_create_status(
            test_db, "Pass", EntityType.TRACE, organization_id=str(test_organization.id)
        )

        update_trace_turn_metrics(
            test_db,
            str(rows[0].id),
            {"k": "v"},
            status_id=str(status.id),
            execution="ok",
            verdict="pass",
        )

        row = _rows(test_db, trace_id)[0]
        assert row.trace_metrics_status_id == status.id
        assert (row.execution, row.verdict) == ("ok", "pass")

    def test_is_one_statement(self, test_db, test_organization, db_project):
        _, rows = _store_trace(test_db, str(test_organization.id), str(db_project.id))
        statements = []

        def record(conn, cursor, statement, *args):
            # The harness wraps each test in savepoints; tenant GUCs are not the write.
            if "set_config" not in statement and "SAVEPOINT" not in statement:
                statements.append(statement)

        engine = test_db.get_bind()
        event.listen(engine, "before_cursor_execute", record)
        try:
            update_trace_turn_metrics(test_db, str(rows[0].id), {"k": "v"})
        finally:
            event.remove(engine, "before_cursor_execute", record)

        assert len(statements) == 1, statements
        assert statements[0].lstrip().upper().startswith("UPDATE TRACE")


@pytest.mark.integration
class TestUpdateTraceConversationMetrics:
    def test_sets_conversation_metrics_on_every_span(self, test_db, test_organization, db_project):
        trace_id, _ = _store_trace(test_db, str(test_organization.id), str(db_project.id), 3)

        updated = update_trace_conversation_metrics(test_db, trace_id, {"overall": 0.9})

        assert updated == 3
        for row in _rows(test_db, trace_id):
            assert row.trace_metrics == {"conversation_metrics": {"overall": 0.9}}

    def test_keeps_each_spans_turn_metrics(self, test_db, test_organization, db_project):
        trace_id, rows = _store_trace(test_db, str(test_organization.id), str(db_project.id), 2)
        update_trace_turn_metrics(test_db, str(rows[0].id), {"t": 1})
        processed_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        update_trace_conversation_metrics(test_db, trace_id, {"c": 2}, processed_at=processed_at)

        by_id = {row.id: row for row in _rows(test_db, trace_id)}
        assert by_id[rows[0].id].trace_metrics == {
            "turn_metrics": {"t": 1},
            "conversation_metrics": {"c": 2},
        }
        assert by_id[rows[1].id].trace_metrics == {"conversation_metrics": {"c": 2}}
        assert {row.trace_metrics_processed_at for row in by_id.values()} == {processed_at}

    def test_an_unknown_trace_updates_nothing(self, test_db):
        assert update_trace_conversation_metrics(test_db, "b" * 32, {"c": 1}) == 0
