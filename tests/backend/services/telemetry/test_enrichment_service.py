"""
Tests for telemetry enrichment service

This module tests the EnrichmentService class including:
- Worker availability checking
- Async/sync enrichment fallback logic
- Error handling and edge cases
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.telemetry.enrichment import EnrichmentService
from rhesis.backend.app.services.telemetry.enrichment import service as enrichment_service_module


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

    @patch("rhesis.backend.worker.app")
    def test_check_workers_available_success(self, mock_celery_app, enrichment_service):
        """Test worker availability check when workers are available"""
        # Clear module-level cache so the mock is used (cache can hold False from other tests)
        enrichment_service_module._worker_cache["available"] = None
        enrichment_service_module._worker_cache["checked_at"] = 0.0

        # Mock successful worker inspection
        mock_inspect = Mock()
        mock_inspect.ping.return_value = {
            "worker1": "pong"
        }  # Non-empty dict means workers available
        mock_celery_app.control.inspect.return_value = mock_inspect

        result = enrichment_service._check_workers_available()

        assert result is True
        mock_celery_app.control.inspect.assert_called_once_with(timeout=3.0)
        mock_inspect.ping.assert_called_once()

    @patch("rhesis.backend.worker.app")
    def test_check_workers_available_no_active_workers(self, mock_celery_app, enrichment_service):
        """Test worker availability check when no active workers"""
        enrichment_service_module._worker_cache["available"] = None
        enrichment_service_module._worker_cache["checked_at"] = 0.0

        # Mock no workers responding to ping
        mock_inspect = Mock()
        mock_inspect.ping.return_value = None
        mock_celery_app.control.inspect.return_value = mock_inspect

        result = enrichment_service._check_workers_available()

        assert result is False

    @patch("rhesis.backend.worker.app")
    def test_check_workers_available_empty_response(self, mock_celery_app, enrichment_service):
        """Test worker availability check when ping returns empty dict"""
        enrichment_service_module._worker_cache["available"] = None
        enrichment_service_module._worker_cache["checked_at"] = 0.0

        # Mock empty response (no workers)
        mock_inspect = Mock()
        mock_inspect.ping.return_value = {}
        mock_celery_app.control.inspect.return_value = mock_inspect

        result = enrichment_service._check_workers_available()

        assert result is False

    @patch("rhesis.backend.worker.app")
    def test_check_workers_available_exception(self, mock_celery_app, enrichment_service):
        """Test worker availability check when exception occurs"""
        enrichment_service_module._worker_cache["available"] = None
        enrichment_service_module._worker_cache["checked_at"] = 0.0

        # Mock exception during inspection
        mock_celery_app.control.inspect.side_effect = Exception("Connection error")

        result = enrichment_service._check_workers_available()

        assert result is False

    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    @patch("rhesis.backend.tasks.telemetry.enrich.enrich_trace_async")
    def test_enrich_traces_async_success(
        self, mock_async_task, mock_check_workers, enrichment_service
    ):
        """Test successful async enrichment"""
        # Mock workers available
        mock_check_workers.return_value = True

        # Mock successful async task
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_async_task.delay.return_value = mock_result

        trace_ids = {"trace1", "trace2"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 2
        assert sync_count == 0
        assert mock_async_task.delay.call_count == 2

    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    def test_enrich_traces_sync_fallback(
        self, mock_enricher_class, mock_check_workers, enrichment_service
    ):
        """Test sync fallback when no workers available"""
        # Mock no workers available
        mock_check_workers.return_value = False

        # Mock successful sync enrichment
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

    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    @patch("rhesis.backend.tasks.telemetry.enrich.enrich_trace_async")
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    def test_enrich_traces_async_fallback_to_sync(
        self, mock_enricher_class, mock_async_task, mock_check_workers, enrichment_service
    ):
        """Test fallback to sync when async fails"""
        # Mock workers available initially
        mock_check_workers.return_value = True

        # Mock async task failure
        mock_async_task.delay.side_effect = Exception("Celery error")

        # Mock successful sync enrichment
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

    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    def test_enrich_traces_sync_failure(
        self, mock_enricher_class, mock_check_workers, enrichment_service
    ):
        """Test handling of sync enrichment failure"""
        # Mock no workers available
        mock_check_workers.return_value = False

        # Mock sync enrichment failure
        mock_enricher = Mock()
        mock_enricher.enrich_trace.side_effect = Exception("Database error")
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        # Should still count as attempted sync enrichment
        assert async_count == 0
        assert sync_count == 1

    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    def test_enrich_traces_sync_no_data(
        self, mock_enricher_class, mock_check_workers, enrichment_service
    ):
        """Test handling when sync enrichment returns no data"""
        # Mock no workers available
        mock_check_workers.return_value = False

        # Mock sync enrichment returning None
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

    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    @patch("rhesis.backend.tasks.telemetry.enrich.enrich_trace_async")
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    def test_enrich_traces_mixed_success_failure(
        self, mock_enricher_class, mock_async_task, mock_check_workers, enrichment_service
    ):
        """Test mixed async success and failure scenarios"""
        # Mock workers available
        mock_check_workers.return_value = True

        # Mock async task: first succeeds, second fails
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_async_task.delay.side_effect = [mock_result, Exception("Task error")]

        # Mock successful sync enrichment for fallback
        mock_enricher = Mock()
        mock_enricher.enrich_trace.return_value = {"costs": {"total_cost_usd": 0.01}}
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1", "trace2"}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        assert async_count == 1  # First trace succeeded async
        assert sync_count == 1  # Second trace fell back to sync

    @patch("rhesis.backend.app.services.telemetry.enrichment.service.logger")
    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    @patch("rhesis.backend.tasks.telemetry.enrich.enrich_trace_async")
    def test_enrich_traces_logging(
        self, mock_async_task, mock_check_workers, mock_logger, enrichment_service
    ):
        """Test that appropriate logging occurs during enrichment"""
        # Mock workers available
        mock_check_workers.return_value = True

        # Mock successful async task
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_async_task.delay.return_value = mock_result

        trace_ids = {"trace1"}
        project_id = "project-123"
        organization_id = "org-123"

        enrichment_service.enrich_traces(trace_ids, project_id, organization_id)

        # Check that debug logging occurred
        mock_logger.debug.assert_called_with(
            "Enqueued async enrichment for trace trace1 (task: task-123)"
        )

    @patch("rhesis.backend.app.services.telemetry.enrichment.service.logger")
    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    @patch("rhesis.backend.app.services.telemetry.enrichment.service.TraceEnricher")
    def test_enrich_traces_sync_logging(
        self, mock_enricher_class, mock_check_workers, mock_logger, enrichment_service
    ):
        """Test logging during sync enrichment"""
        # Mock no workers available
        mock_check_workers.return_value = False

        # Mock successful sync enrichment
        mock_enricher = Mock()
        mock_enricher.enrich_trace.return_value = {"costs": {"total_cost_usd": 0.01}}
        mock_enricher_class.return_value = mock_enricher

        trace_ids = {"trace1"}
        project_id = "project-123"
        organization_id = "org-123"

        enrichment_service.enrich_traces(trace_ids, project_id, organization_id)

        # Check that info logging occurred
        mock_logger.info.assert_any_call(
            "No Celery workers available, using sync enrichment for trace trace1"
        )
        mock_logger.info.assert_any_call("Completed sync enrichment for trace trace1")

    @patch("rhesis.backend.tasks.telemetry.enrich.enrich_trace_async")
    @patch(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService._check_workers_available"
    )
    def test_enrich_traces_checks_workers_once(
        self, mock_check_workers, mock_async_task, enrichment_service
    ):
        """
        Test that worker availability is checked once per batch, not per trace.

        This verifies the performance optimization that prevents N×3 second timeouts
        when processing N traces without available workers.
        """
        # Mock workers available
        mock_check_workers.return_value = True

        # Mock successful async task
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_async_task.delay.return_value = mock_result

        # Process 10 traces
        trace_ids = {f"trace{i}" for i in range(10)}
        project_id = "project-123"
        organization_id = "org-123"

        async_count, sync_count = enrichment_service.enrich_traces(
            trace_ids, project_id, organization_id
        )

        # Verify results
        assert async_count == 10
        assert sync_count == 0

        # CRITICAL: Worker check should only be called once, not 10 times
        # This prevents 10×3=30 seconds of timeout delays when workers are unavailable
        assert mock_check_workers.call_count == 1


@pytest.mark.integration
class TestEnrichmentServiceIntegration:
    """Integration tests for EnrichmentService"""

    def test_enrichment_service_with_real_db(self, test_db):
        """Test EnrichmentService with real database session"""
        service = EnrichmentService(test_db)
        assert service.db == test_db

    @patch("rhesis.backend.worker.app")
    def test_worker_check_integration(self, mock_celery_app, test_db):
        """Test worker availability check with real service instance"""
        enrichment_service_module._worker_cache["available"] = None
        enrichment_service_module._worker_cache["checked_at"] = 0.0

        service = EnrichmentService(test_db)

        # Mock no workers available
        mock_inspect = Mock()
        mock_inspect.ping.return_value = None
        mock_celery_app.control.inspect.return_value = mock_inspect

        result = service._check_workers_available()
        assert result is False
