"""
Tests for trace linking service.

This module tests the TraceLinkingService class including:
- Linking traces after test result creation
- Linking traces after span ingestion
- Timing scenarios (fast, medium, long tests)
- Edge cases (idempotency, missing data, non-test traces)
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import TestExecutionContext
from rhesis.backend.app.models import TestResult, Trace
from rhesis.backend.app.services.telemetry.linking_service import TraceLinkingService

fake = Faker()


@pytest.mark.unit
class TestTraceLinkingService:
    """Test the TraceLinkingService class"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def linking_service(self, mock_db):
        """Create TraceLinkingService instance with mock database"""
        return TraceLinkingService(mock_db)

    @pytest.fixture
    def test_context(self):
        """Generate test execution context"""
        return {
            "test_run_id": str(uuid4()),
            "test_id": str(uuid4()),
            "test_configuration_id": str(uuid4()),
            "test_result_id": str(uuid4()),
            "organization_id": str(uuid4()),
        }

    def test_init(self, mock_db):
        """Test TraceLinkingService initialization"""
        service = TraceLinkingService(mock_db)
        assert service.db == mock_db

    @patch("rhesis.backend.app.services.telemetry.linking_service.crud")
    def test_link_traces_for_test_result(self, mock_crud, linking_service, test_context):
        """Test linking traces after test result creation"""
        # Mock CRUD response
        mock_crud.update_traces_with_test_result_id.return_value = 5

        result = linking_service.link_traces_for_test_result(
            test_run_id=test_context["test_run_id"],
            test_id=test_context["test_id"],
            test_configuration_id=test_context["test_configuration_id"],
            test_result_id=test_context["test_result_id"],
            organization_id=test_context["organization_id"],
        )

        assert result == 5
        mock_crud.update_traces_with_test_result_id.assert_called_once_with(
            db=linking_service.db,
            test_run_id=test_context["test_run_id"],
            test_id=test_context["test_id"],
            test_configuration_id=test_context["test_configuration_id"],
            test_result_id=test_context["test_result_id"],
            organization_id=test_context["organization_id"],
        )

    def test_link_traces_for_incoming_batch_empty_spans(self, linking_service):
        """Test linking with empty span list"""
        result = linking_service.link_traces_for_incoming_batch(
            spans=[],
            organization_id=str(uuid4()),
        )

        assert result == 0

    def test_link_traces_for_incoming_batch_non_test_traces(self, linking_service, mock_db):
        """Test linking with non-test traces (no test context)"""
        # Create mock span without test context
        mock_span = Mock(spec=Trace)
        mock_span.test_run_id = None
        mock_span.test_id = None
        mock_span.attributes = {}

        result = linking_service.link_traces_for_incoming_batch(
            spans=[mock_span],
            organization_id=str(uuid4()),
        )

        assert result == 0

    def test_link_traces_for_incoming_batch_missing_config_id(self, linking_service, test_context):
        """Test linking with missing test_configuration_id in attributes"""
        # Create mock span with partial test context
        mock_span = Mock(spec=Trace)
        mock_span.test_run_id = uuid4()
        mock_span.test_id = uuid4()
        mock_span.attributes = {}  # Missing test_configuration_id

        result = linking_service.link_traces_for_incoming_batch(
            spans=[mock_span],
            organization_id=test_context["organization_id"],
        )

        assert result == 0

    @patch("rhesis.backend.app.services.telemetry.linking_service.crud")
    def test_link_traces_for_incoming_batch_no_test_result(
        self, mock_crud, linking_service, mock_db, test_context
    ):
        """Test linking when test result doesn't exist yet (test still running)"""
        # Create mock span with test context
        test_run_uuid = uuid4()
        test_id_uuid = uuid4()
        test_config_id = str(uuid4())

        mock_span = Mock(spec=Trace)
        mock_span.test_run_id = test_run_uuid
        mock_span.test_id = test_id_uuid
        mock_span.attributes = {
            TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID: test_config_id
        }

        # Mock query to return no test result
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = linking_service.link_traces_for_incoming_batch(
            spans=[mock_span],
            organization_id=test_context["organization_id"],
        )

        assert result == 0
        # Should not call update since no test result found
        mock_crud.update_traces_with_test_result_id.assert_not_called()

    @patch("rhesis.backend.app.services.telemetry.linking_service.crud")
    def test_link_traces_for_incoming_batch_success(
        self, mock_crud, linking_service, mock_db, test_context
    ):
        """Test successful linking after span ingestion"""
        # Create mock span with test context
        test_run_uuid = uuid4()
        test_id_uuid = uuid4()
        test_config_id = str(uuid4())
        test_result_id = uuid4()

        mock_span = Mock(spec=Trace)
        mock_span.test_run_id = test_run_uuid
        mock_span.test_id = test_id_uuid
        mock_span.attributes = {
            TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID: test_config_id
        }

        # Mock test result found
        mock_test_result = Mock(spec=TestResult)
        mock_test_result.id = test_result_id

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_test_result
        mock_db.query.return_value = mock_query

        # Mock CRUD response
        mock_crud.update_traces_with_test_result_id.return_value = 3

        result = linking_service.link_traces_for_incoming_batch(
            spans=[mock_span],
            organization_id=test_context["organization_id"],
        )

        assert result == 3
        mock_crud.update_traces_with_test_result_id.assert_called_once()

    @patch("rhesis.backend.app.services.telemetry.linking_service.crud")
    def test_link_idempotent_multiple_calls(self, mock_crud, linking_service, test_context):
        """Test that linking is idempotent (can be called multiple times safely)"""
        # First call links 5 traces
        mock_crud.update_traces_with_test_result_id.return_value = 5

        result1 = linking_service.link_traces_for_test_result(
            test_run_id=test_context["test_run_id"],
            test_id=test_context["test_id"],
            test_configuration_id=test_context["test_configuration_id"],
            test_result_id=test_context["test_result_id"],
            organization_id=test_context["organization_id"],
        )

        # Second call finds 0 traces (already linked)
        mock_crud.update_traces_with_test_result_id.return_value = 0

        result2 = linking_service.link_traces_for_test_result(
            test_run_id=test_context["test_run_id"],
            test_id=test_context["test_id"],
            test_configuration_id=test_context["test_configuration_id"],
            test_result_id=test_context["test_result_id"],
            organization_id=test_context["organization_id"],
        )

        assert result1 == 5
        assert result2 == 0
        assert mock_crud.update_traces_with_test_result_id.call_count == 2


@pytest.mark.unit
class TestTraceLinkingTimingScenarios:
    """Test timing scenarios for trace linking"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def linking_service(self, mock_db):
        """Create TraceLinkingService instance with mock database"""
        return TraceLinkingService(mock_db)

    @pytest.fixture
    def test_context(self):
        """Generate test execution context"""
        return {
            "test_run_id": str(uuid4()),
            "test_id": str(uuid4()),
            "test_configuration_id": str(uuid4()),
            "test_result_id": str(uuid4()),
            "organization_id": str(uuid4()),
        }

    @patch("rhesis.backend.app.services.telemetry.linking_service.crud")
    def test_fast_test_all_spans_arrive_after_result(
        self, mock_crud, linking_service, mock_db, test_context
    ):
        """
        Test scenario: Fast test (< 5s)
        - Test completes before first batch
        - All spans arrive after test_result creation
        - Linking via telemetry endpoint should succeed
        """
        # Simulate test result already exists
        test_result_id = uuid4()
        mock_test_result = Mock(spec=TestResult)
        mock_test_result.id = test_result_id

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_test_result
        mock_db.query.return_value = mock_query

        # Create mock spans that arrive after result
        mock_span = Mock(spec=Trace)
        mock_span.test_run_id = uuid4()
        mock_span.test_id = uuid4()
        mock_span.attributes = {
            TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID: test_context[
                "test_configuration_id"
            ]
        }

        # Mock successful linking
        mock_crud.update_traces_with_test_result_id.return_value = 10

        # Link via incoming batch (telemetry endpoint)
        result = linking_service.link_traces_for_incoming_batch(
            spans=[mock_span],
            organization_id=test_context["organization_id"],
        )

        assert result == 10
        mock_crud.update_traces_with_test_result_id.assert_called_once()

    @patch("rhesis.backend.app.services.telemetry.linking_service.crud")
    def test_medium_test_spans_split_across_result(
        self, mock_crud, linking_service, mock_db, test_context
    ):
        """
        Test scenario: Medium test (5-10s)
        - First batch arrives before test_result (T=5s)
        - Test completes and creates result (T=8s)
        - Second batch arrives after test_result (T=10s)
        - Both linking paths should be called
        """
        # Simulate first batch arrives, no result yet
        mock_span1 = Mock(spec=Trace)
        mock_span1.test_run_id = uuid4()
        mock_span1.test_id = uuid4()
        mock_span1.attributes = {
            TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID: test_context[
                "test_configuration_id"
            ]
        }

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None  # No result yet
        mock_db.query.return_value = mock_query

        result1 = linking_service.link_traces_for_incoming_batch(
            spans=[mock_span1],
            organization_id=test_context["organization_id"],
        )

        assert result1 == 0  # No linking, result doesn't exist

        # Simulate test result creation and linking
        mock_crud.update_traces_with_test_result_id.return_value = 5

        result2 = linking_service.link_traces_for_test_result(
            test_run_id=test_context["test_run_id"],
            test_id=test_context["test_id"],
            test_configuration_id=test_context["test_configuration_id"],
            test_result_id=test_context["test_result_id"],
            organization_id=test_context["organization_id"],
        )

        assert result2 == 5  # Links first batch

        # Simulate second batch arrives, result exists now
        test_result_id = uuid4()
        mock_test_result = Mock(spec=TestResult)
        mock_test_result.id = test_result_id

        mock_query.filter.return_value.first.return_value = mock_test_result
        mock_crud.update_traces_with_test_result_id.return_value = 3

        result3 = linking_service.link_traces_for_incoming_batch(
            spans=[mock_span1],  # Reuse same mock
            organization_id=test_context["organization_id"],
        )

        assert result3 == 3  # Links second batch

    @patch("rhesis.backend.app.services.telemetry.linking_service.crud")
    def test_long_test_multiple_batches(self, mock_crud, linking_service, test_context):
        """
        Test scenario: Long test (> 10s)
        - Multiple batches arrive before result (T=5s, T=10s)
        - Test completes (T=12s) and links all early batches
        - Final batch arrives (T=15s) and gets linked via telemetry
        """
        # Simulate test result creation linking multiple early batches
        mock_crud.update_traces_with_test_result_id.return_value = 15

        result = linking_service.link_traces_for_test_result(
            test_run_id=test_context["test_run_id"],
            test_id=test_context["test_id"],
            test_configuration_id=test_context["test_configuration_id"],
            test_result_id=test_context["test_result_id"],
            organization_id=test_context["organization_id"],
        )

        assert result == 15  # Links batches 1 and 2
        mock_crud.update_traces_with_test_result_id.assert_called_once()


@pytest.mark.unit
class TestTraceLinkingIntegration:
    """Test integration scenarios between both linking paths"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def linking_service(self, mock_db):
        """Create TraceLinkingService instance with mock database"""
        return TraceLinkingService(mock_db)

    @pytest.fixture
    def test_context(self):
        """Generate test execution context"""
        return {
            "test_run_id": str(uuid4()),
            "test_id": str(uuid4()),
            "test_configuration_id": str(uuid4()),
            "test_result_id": str(uuid4()),
            "organization_id": str(uuid4()),
        }

    @patch("rhesis.backend.app.services.telemetry.linking_service.crud")
    def test_hybrid_both_paths_called(self, mock_crud, linking_service, mock_db, test_context):
        """
        Test that both linking paths can be called for the same test
        and the operation is idempotent
        """
        # First call via test result creation
        mock_crud.update_traces_with_test_result_id.return_value = 8

        result1 = linking_service.link_traces_for_test_result(
            test_run_id=test_context["test_run_id"],
            test_id=test_context["test_id"],
            test_configuration_id=test_context["test_configuration_id"],
            test_result_id=test_context["test_result_id"],
            organization_id=test_context["organization_id"],
        )

        assert result1 == 8

        # Second call via trace ingestion (should find 0 new traces)
        test_result_id = uuid4()
        mock_test_result = Mock(spec=TestResult)
        mock_test_result.id = test_result_id

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_test_result
        mock_db.query.return_value = mock_query

        mock_crud.update_traces_with_test_result_id.return_value = 0  # Already linked

        mock_span = Mock(spec=Trace)
        mock_span.test_run_id = uuid4()
        mock_span.test_id = uuid4()
        mock_span.attributes = {
            TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID: test_context[
                "test_configuration_id"
            ]
        }

        result2 = linking_service.link_traces_for_incoming_batch(
            spans=[mock_span],
            organization_id=test_context["organization_id"],
        )

        assert result2 == 0  # Idempotent, no duplicates
        assert mock_crud.update_traces_with_test_result_id.call_count == 2

    def test_find_test_result_invalid_uuid(self, linking_service):
        """Test _find_test_result with invalid UUID strings"""
        result = linking_service._find_test_result(
            test_run_id="invalid-uuid",
            test_id="also-invalid",
            test_configuration_id="not-a-uuid",
            organization_id="nope",
        )

        assert result is None
