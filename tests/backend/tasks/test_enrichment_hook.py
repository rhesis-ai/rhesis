"""Tests verifying enrichment triggers evaluate_turn_trace_metrics.delay()."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.tasks.telemetry.enrich import enrich_trace_async

TRACE_ID = "test-trace-id"
PROJECT_ID = "test-project-id"
ORG_ID = "test-org-id"


@pytest.mark.unit
class TestEnrichmentTriggersTraceMetrics:
    """Verify that successful enrichment chains to trace metrics evaluation."""

    def test_triggers_evaluate_on_success(self):
        mock_db = MagicMock(spec=Session)
        mock_enricher = MagicMock()
        mock_enriched = MagicMock()
        mock_enriched.model_dump.return_value = {"field1": "value1", "field2": None}
        mock_enricher.enrich_trace.return_value = mock_enriched

        with (
            patch(
                "rhesis.backend.tasks.telemetry.enrich.SessionLocal",
                return_value=mock_db,
            ),
            patch(
                "rhesis.backend.tasks.telemetry.enrich.TraceEnricher",
                return_value=mock_enricher,
            ),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.evaluate_turn_trace_metrics",
            ) as mock_eval_task,
        ):
            result = enrich_trace_async.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert result["status"] == "success"
        mock_eval_task.delay.assert_called_once_with(TRACE_ID, PROJECT_ID, ORG_ID)
        mock_db.close.assert_called_once()

    def test_does_not_trigger_when_no_spans(self):
        mock_db = MagicMock(spec=Session)
        mock_enricher = MagicMock()
        mock_enricher.enrich_trace.return_value = None

        with (
            patch(
                "rhesis.backend.tasks.telemetry.enrich.SessionLocal",
                return_value=mock_db,
            ),
            patch(
                "rhesis.backend.tasks.telemetry.enrich.TraceEnricher",
                return_value=mock_enricher,
            ),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.evaluate_turn_trace_metrics",
            ) as mock_eval_task,
        ):
            result = enrich_trace_async.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert result["status"] == "no_spans"
        mock_eval_task.delay.assert_not_called()

    def test_enrichment_succeeds_even_if_eval_scheduling_fails(self):
        mock_db = MagicMock(spec=Session)
        mock_enricher = MagicMock()
        mock_enriched = MagicMock()
        mock_enriched.model_dump.return_value = {"field1": "value1"}
        mock_enricher.enrich_trace.return_value = mock_enriched

        with (
            patch(
                "rhesis.backend.tasks.telemetry.enrich.SessionLocal",
                return_value=mock_db,
            ),
            patch(
                "rhesis.backend.tasks.telemetry.enrich.TraceEnricher",
                return_value=mock_enricher,
            ),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.evaluate_turn_trace_metrics",
            ) as mock_eval_task,
        ):
            mock_eval_task.delay.side_effect = RuntimeError("scheduling failed")
            result = enrich_trace_async.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert result["status"] == "success"
        assert result["enriched_fields"] == ["field1"]
