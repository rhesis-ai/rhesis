"""
Tests for telemetry enrichment service

This module tests the EnrichmentService class including:
- Async/sync enrichment fallback logic
- Error handling and edge cases
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.telemetry.enrichment import EnrichmentService


@pytest.mark.unit
class TestEnrichmentService:
    """Test the EnrichmentService class"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def enrichment_service(self, mock_db):
        """Create EnrichmentService instance with mock database"""
        return EnrichmentService(mock_db)

    def test_init(self, mock_db):
        """Test EnrichmentService initialization"""
        service = EnrichmentService(mock_db)
        assert service.db == mock_db

    @patch("celery.chain")
    def test_enrich_traces_async_success(self, mock_chain, enrichment_service):
        """Test successful async enrichment"""
        mock_workflow = Mock()
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_workflow.apply_async.return_value = mock_result
        mock_chain.return_value = mock_workflow

        trace_ids = {"trace1", "trace2"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 2
        assert sync_count == 0
        assert mock_chain.call_count == 2
        assert mock_workflow.apply_async.call_count == 2

    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    @patch("celery.chain")
    def test_enrich_traces_sync_fallback_on_broker_error(
        self, mock_chain, mock_enricher_class, enrichment_service
    ):
        """Test sync fallback when broker is unreachable.

        Metric evaluation is intentionally skipped in the sync fallback
        (it requires Celery workers for LLM calls).
        """
        import redis.exceptions

        mock_chain.side_effect = redis.exceptions.ConnectionError("Redis down")

        mock_enricher = Mock()
        mock_enricher.enrich_trace.return_value = {"costs": {"total_cost_usd": 0.01}}
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1", "trace2"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 0
        assert sync_count == 2
        assert mock_enricher.enrich_trace.call_count == 2

    @patch("celery.chain")
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    def test_enrich_traces_async_fallback_to_sync(
        self, mock_enricher_class, mock_chain, enrichment_service
    ):
        """Test fallback to sync when async fails with non-broker error.

        Metric evaluation is skipped in the sync fallback path.
        """
        mock_chain.side_effect = Exception("Celery error")

        mock_enricher = Mock()
        mock_enricher.enrich_trace.return_value = {"costs": {"total_cost_usd": 0.01}}
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 0
        assert sync_count == 1
        mock_enricher.enrich_trace.assert_called_once_with("trace1", project_id, organization_id)

    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    @patch("celery.chain")
    def test_enrich_traces_sync_failure(self, mock_chain, mock_enricher_class, enrichment_service):
        """Test handling of sync enrichment failure"""
        import redis.exceptions

        mock_chain.side_effect = redis.exceptions.ConnectionError("Redis down")

        mock_enricher = Mock()
        mock_enricher.enrich_trace.side_effect = Exception("Database error")
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 0
        assert sync_count == 1

    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    @patch("celery.chain")
    def test_enrich_traces_sync_no_data(self, mock_chain, mock_enricher_class, enrichment_service):
        """Test handling when sync enrichment returns no data"""
        import redis.exceptions

        mock_chain.side_effect = redis.exceptions.ConnectionError("Redis down")

        mock_enricher = Mock()
        mock_enricher.enrich_trace.return_value = None
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 0
        assert sync_count == 1

    def test_enrich_traces_empty_set(self, enrichment_service):
        """Test enrichment with empty trace set"""
        trace_ids = set()
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 0
        assert sync_count == 0

    @patch("celery.chain")
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    def test_enrich_traces_mixed_success_failure(
        self, mock_enricher_class, mock_chain, enrichment_service
    ):
        """Test mixed async success and failure scenarios.

        When async fails for one trace, it falls back to sync enrichment
        (without metric evaluation).
        """
        mock_workflow = Mock()
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_workflow.apply_async.return_value = mock_result
        mock_chain.side_effect = [mock_workflow, Exception("Task error")]

        mock_enricher = Mock()
        mock_enricher.enrich_trace.return_value = {"costs": {"total_cost_usd": 0.01}}
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1", "trace2"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 1
        assert sync_count == 1
        mock_enricher.enrich_trace.assert_called_once()

    @patch("rhesis.backend.app.services.telemetry.enrichment.service.logger")
    @patch("celery.chain")
    def test_enrich_traces_logging(self, mock_chain, mock_logger, enrichment_service):
        """Test that appropriate logging occurs during enrichment"""
        mock_workflow = Mock()
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_workflow.apply_async.return_value = mock_result
        mock_chain.return_value = mock_workflow

        trace_ids = {"trace1"}
        project_id = "project-123"
        organization_id = "org-123"

        enrichment_service.enrich_traces(trace_ids, project_id, organization_id)

        mock_logger.debug.assert_called_with(
            "Enqueued async pipeline (enrich -> evaluate) for trace trace1 (task: task-123)"
        )

    @patch("rhesis.backend.app.services.telemetry.enrichment.service.logger")
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    @patch("celery.chain")
    def test_enrich_traces_sync_logging(
        self, mock_chain, mock_enricher_class, mock_logger, enrichment_service
    ):
        """Test logging during sync enrichment"""
        import redis.exceptions

        mock_chain.side_effect = redis.exceptions.ConnectionError("Redis down")

        mock_enricher = Mock()
        mock_enricher.enrich_trace.return_value = {"costs": {"total_cost_usd": 0.01}}
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1"}
        project_id = "project-123"
        organization_id = "org-123"

        enrichment_service.enrich_traces(trace_ids, project_id, organization_id)

        mock_logger.info.assert_any_call("Completed sync enrichment for trace trace1")


@pytest.mark.unit
class TestBuildEnrichmentChainRootSpanId:
    """build_enrichment_chain threads root_span_id to the evaluate task."""

    @patch("celery.chain")
    def test_root_span_id_passed_to_evaluate(self, mock_chain):
        from rhesis.backend.app.services.telemetry.enrichment import (
            build_enrichment_chain,
        )

        build_enrichment_chain("t1", "p1", "o1", root_span_id="span-db-1")

        args = mock_chain.call_args
        evaluate_sig = args[0][1]
        assert evaluate_sig.kwargs.get("root_span_id") == "span-db-1"

    @patch("celery.chain")
    def test_root_span_id_none_omits_kwarg(self, mock_chain):
        from rhesis.backend.app.services.telemetry.enrichment import (
            build_enrichment_chain,
        )

        build_enrichment_chain("t1", "p1", "o1", root_span_id=None)

        args = mock_chain.call_args
        evaluate_sig = args[0][1]
        assert evaluate_sig.kwargs.get("root_span_id") is None


@pytest.mark.unit
class TestCreateAndEnrichSpansPerRootSpan:
    """create_and_enrich_spans dispatches one chain per root span."""

    MODULE = "rhesis.backend.app.services.telemetry.enrichment.service"

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        return EnrichmentService(mock_db)

    def _mock_stored_spans(self, specs):
        """Build mock stored span objects.

        specs: list of (trace_id, span_id_str, parent_span_id_or_None)
        """
        spans = []
        for trace_id, db_id, parent in specs:
            s = Mock()
            s.trace_id = trace_id
            s.id = db_id
            s.parent_span_id = parent
            spans.append(s)
        return spans

    def test_dispatches_per_root_span(self, service):
        """Each root span dispatches its own chain with root_span_id."""
        stored = self._mock_stored_spans(
            [
                ("T1", "root-1", None),
                ("T1", "child-1", "root-1"),
                ("T1", "root-2", None),
            ]
        )
        mock_workflow = Mock()
        mock_result = Mock(id="task-x")
        mock_workflow.apply_async.return_value = mock_result

        with (
            patch(
                f"{self.MODULE}.build_enrichment_chain",
                return_value=mock_workflow,
            ) as mock_build,
            patch("rhesis.backend.app.crud.create_trace_spans", return_value=stored),
        ):
            spans_out, async_c, sync_c = service.create_and_enrich_spans(
                [],
                "org-1",
                "proj-1",
            )

        assert async_c == 2
        assert sync_c == 0
        calls = mock_build.call_args_list
        root_ids = {c.kwargs["root_span_id"] for c in calls}
        assert root_ids == {"root-1", "root-2"}

    def test_child_only_traces_get_enrichment_without_root_span_id(self, service):
        """Trace IDs with only child spans still get enrichment (no root_span_id)."""
        stored = self._mock_stored_spans(
            [
                ("T1", "root-1", None),
                ("T2", "child-only", "some-parent"),
            ]
        )
        mock_workflow = Mock()
        mock_result = Mock(id="task-x")
        mock_workflow.apply_async.return_value = mock_result

        with (
            patch(
                f"{self.MODULE}.build_enrichment_chain",
                return_value=mock_workflow,
            ) as mock_build,
            patch("rhesis.backend.app.crud.create_trace_spans", return_value=stored),
        ):
            spans_out, async_c, sync_c = service.create_and_enrich_spans(
                [],
                "org-1",
                "proj-1",
            )

        assert async_c == 2
        calls = mock_build.call_args_list
        assert len(calls) == 2
        root_call = [c for c in calls if c.kwargs.get("root_span_id") == "root-1"]
        assert len(root_call) == 1
        child_call = [c for c in calls if c.kwargs.get("root_span_id") is None]
        assert len(child_call) == 1

    def test_empty_batch(self, service):
        """Empty batch returns early."""
        with (
            patch(
                f"{self.MODULE}.build_enrichment_chain",
            ) as mock_build,
            patch("rhesis.backend.app.crud.create_trace_spans", return_value=[]),
        ):
            spans_out, async_c, sync_c = service.create_and_enrich_spans(
                [],
                "org-1",
                "proj-1",
            )

        assert spans_out == []
        assert async_c == 0
        assert sync_c == 0
        mock_build.assert_not_called()


@pytest.mark.integration
class TestEnrichmentServiceIntegration:
    """Integration tests for EnrichmentService"""

    def test_enrichment_service_with_real_db(self, test_db):
        """Test EnrichmentService with real database session"""
        service = EnrichmentService(test_db)
        assert service.db == test_db
