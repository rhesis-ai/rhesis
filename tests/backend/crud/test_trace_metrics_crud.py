"""Unit tests for trace metrics CRUD helpers."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud


@pytest.mark.unit
class TestUpdateTraceTurnMetrics:
    """Tests for update_trace_turn_metrics."""

    def test_updates_single_span(self):
        db = MagicMock(spec=Session)
        span_id = str(uuid4())
        turn_metrics = {"latency_ms": 42}

        span = MagicMock()
        span.trace_metrics = None

        chain_first = MagicMock()
        chain_first.first.return_value = span
        chain_update = MagicMock()
        chain_update.update.return_value = 1

        mock_query = MagicMock()
        mock_query.filter.side_effect = [chain_first, chain_update]
        db.query.return_value = mock_query

        result = crud.update_trace_turn_metrics(db, span_id, turn_metrics)

        assert result == 1
        chain_update.update.assert_called_once()
        update_values = chain_update.update.call_args[0][0]
        assert update_values["trace_metrics"] == {"turn_metrics": turn_metrics}
        assert "trace_metrics_processed_at" in update_values
        assert "updated_at" in update_values
        assert "trace_metrics_status_id" not in update_values
        db.commit.assert_called_once()

    def test_preserves_conversation_metrics(self):
        db = MagicMock(spec=Session)
        span_id = str(uuid4())
        turn_metrics = {"new": 1}
        preserved = {"conv": "data"}

        span = MagicMock()
        span.trace_metrics = {"conversation_metrics": preserved}

        chain_first = MagicMock()
        chain_first.first.return_value = span
        chain_update = MagicMock()
        chain_update.update.return_value = 1

        mock_query = MagicMock()
        mock_query.filter.side_effect = [chain_first, chain_update]
        db.query.return_value = mock_query

        crud.update_trace_turn_metrics(db, span_id, turn_metrics)

        update_values = chain_update.update.call_args[0][0]
        assert update_values["trace_metrics"]["conversation_metrics"] == preserved
        assert update_values["trace_metrics"]["turn_metrics"] == turn_metrics

    def test_span_not_found(self):
        db = MagicMock(spec=Session)
        span_id = str(uuid4())

        chain_first = MagicMock()
        chain_first.first.return_value = None
        mock_query = MagicMock()
        mock_query.filter.return_value = chain_first
        db.query.return_value = mock_query

        result = crud.update_trace_turn_metrics(db, span_id, {"x": 1})

        assert result == 0
        db.commit.assert_not_called()

    def test_sets_status_id(self):
        db = MagicMock(spec=Session)
        span_id = str(uuid4())
        status_id = str(uuid4())

        span = MagicMock()
        span.trace_metrics = None

        chain_first = MagicMock()
        chain_first.first.return_value = span
        chain_update = MagicMock()
        chain_update.update.return_value = 1

        mock_query = MagicMock()
        mock_query.filter.side_effect = [chain_first, chain_update]
        db.query.return_value = mock_query

        crud.update_trace_turn_metrics(db, span_id, {"k": "v"}, status_id=status_id)

        update_values = chain_update.update.call_args[0][0]
        assert update_values["trace_metrics_status_id"] == status_id


@pytest.mark.unit
class TestUpdateTraceConversationMetrics:
    """Tests for update_trace_conversation_metrics."""

    def test_updates_all_spans(self):
        db = MagicMock(spec=Session)
        trace_id = "a" * 32
        conversation_metrics = {"overall": 0.9}

        spans = [MagicMock(), MagicMock(), MagicMock()]
        for s in spans:
            s.trace_metrics = None

        chain = MagicMock()
        chain.all.return_value = spans
        mock_query = MagicMock()
        mock_query.filter.return_value = chain
        db.query.return_value = mock_query

        result = crud.update_trace_conversation_metrics(db, trace_id, conversation_metrics)

        assert result == 3
        for s in spans:
            assert s.trace_metrics == {"conversation_metrics": conversation_metrics}
        db.commit.assert_called_once()

    def test_no_spans(self):
        db = MagicMock(spec=Session)
        trace_id = "b" * 32

        chain = MagicMock()
        chain.all.return_value = []
        mock_query = MagicMock()
        mock_query.filter.return_value = chain
        db.query.return_value = mock_query

        result = crud.update_trace_conversation_metrics(
            db, trace_id, {"conversation_metrics": {}}
        )

        assert result == 0
        db.commit.assert_not_called()

    def test_sets_status_and_processed_at(self):
        db = MagicMock(spec=Session)
        trace_id = "c" * 32
        status_id = str(uuid4())
        processed_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        spans = [MagicMock(), MagicMock()]
        for s in spans:
            s.trace_metrics = {"turn_metrics": {"t": 1}}

        chain = MagicMock()
        chain.all.return_value = spans
        mock_query = MagicMock()
        mock_query.filter.return_value = chain
        db.query.return_value = mock_query

        result = crud.update_trace_conversation_metrics(
            db,
            trace_id,
            {"c": 2},
            status_id=status_id,
            processed_at=processed_at,
        )

        assert result == 2
        for s in spans:
            assert s.trace_metrics_status_id == status_id
            assert s.trace_metrics_processed_at == processed_at
            assert s.updated_at is not None
        db.commit.assert_called_once()
