"""
Integration tests for trace linking with timing simulations.

This module tests the complete trace linking flow including:
- Simulating BatchSpanProcessor delays (5s batching)
- Concurrent span arrival and test result creation
- End-to-end test execution with trace linking
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.constants import TestExecutionContext
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate
from rhesis.backend.app.services.telemetry.enrichment import EnrichmentService
from rhesis.backend.app.services.telemetry.linking_service import TraceLinkingService
from rhesis.sdk.telemetry.schemas import SpanKind, StatusCode

fake = Faker()


@pytest.mark.integration
class TestTraceLinkingTiming:
    """Integration tests for trace linking timing scenarios"""

    def create_test_span(
        self,
        trace_id: str,
        test_run_id: str,
        test_id: str,
        test_configuration_id: str,
        project_id: str,
    ) -> OTELSpanCreate:
        """Create a test span with test execution context"""
        now = datetime.now(timezone.utc)
        span_id = fake.hexify(text="^" * 16, upper=False)

        return OTELSpanCreate(
            trace_id=trace_id,
            span_id=span_id,
            project_id=project_id,
            environment="test",
            span_name="ai.llm.invoke",
            span_kind=SpanKind.INTERNAL,
            start_time=now,
            end_time=now,
            status_code=StatusCode.OK,
            attributes={
                TestExecutionContext.SpanAttributes.TEST_RUN_ID: test_run_id,
                TestExecutionContext.SpanAttributes.TEST_ID: test_id,
                TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID: test_configuration_id,
            },
        )

    def create_test_result(
        self,
        db: Session,
        test_run,
        test,
        test_configuration,
        organization_id: str,
    ) -> models.TestResult:
        """Create a test result in the database"""
        from rhesis.backend.app import schemas
        from rhesis.backend.app.utils.crud_utils import get_or_create_status
        from rhesis.backend.tasks.enums import ResultStatus

        # Create status
        status = get_or_create_status(
            db, ResultStatus.PASS.value, "TestResult", organization_id=organization_id
        )

        # Create test result
        test_result_data = schemas.TestResultCreate(
            test_configuration_id=test_configuration.id,
            test_run_id=test_run.id,
            test_id=test.id,
            status_id=status.id,
            organization_id=organization_id,
            test_metrics={"execution_time": 1.0, "metrics": {}},
            test_output={},
        )

        return crud.create_test_result(db, test_result_data, organization_id=organization_id)

    @pytest.mark.asyncio
    async def test_batch_processor_delay_simulation(
        self, test_db, test_organization, db_project, db_test, db_test_run, db_test_configuration
    ):
        """
        Simulate BatchSpanProcessor 5-second delay.

        Scenario:
        - T=0: Test starts
        - T=2: Test completes, result created
        - T=5: First batch of spans arrives (simulated delay)
        - Verify: Spans get linked via telemetry endpoint
        """
        # Setup test context (use unique trace_id for each test)
        trace_id = uuid4().hex

        # T=2: Create test result (test completed)
        test_result = self.create_test_result(
            db=test_db,
            test_run=db_test_run,
            test=db_test,
            test_configuration=db_test_configuration,
            organization_id=str(test_organization.id),
        )

        # Try linking immediately (should find 0 traces)
        linking_service = TraceLinkingService(test_db)
        count1 = linking_service.link_traces_for_test_result(
            test_run_id=str(db_test_run.id),
            test_id=str(db_test.id),
            test_configuration_id=str(db_test_configuration.id),
            test_result_id=str(test_result.id),
            organization_id=str(test_organization.id),
        )

        assert count1 == 0  # No traces yet

        # Simulate 5-second delay (BatchSpanProcessor)
        await asyncio.sleep(0.1)  # Simulated delay (shortened for tests)

        # T=5: Spans arrive
        spans = [
            self.create_test_span(
                trace_id=trace_id,
                test_run_id=str(db_test_run.id),
                test_id=str(db_test.id),
                test_configuration_id=str(db_test_configuration.id),
                project_id=str(db_project.id),
            )
            for _ in range(3)
        ]

        # Store spans
        stored_spans = crud.create_trace_spans(test_db, spans, str(test_organization.id))

        # Link via telemetry endpoint path
        count2 = linking_service.link_traces_for_incoming_batch(
            spans=stored_spans,
            organization_id=str(test_organization.id),
        )

        assert count2 == 3  # All spans linked

        # Verify traces have test_result_id
        for span in stored_spans:
            test_db.refresh(span)
            assert span.test_result_id == test_result.id

    @pytest.mark.asyncio
    async def test_concurrent_span_arrival_and_result_creation(
        self, test_db, test_organization, db_project, db_test, db_test_run, db_test_configuration
    ):
        """
        Test concurrent span arrival and result creation.

        Scenario:
        - Spans arrive while test is still running
        - Test completes and creates result
        - Both linking paths are exercised
        """
        # Setup test context (use unique trace_id for each test)
        trace_id = uuid4().hex

        # Create first batch of spans (early arrival)
        early_spans = [
            self.create_test_span(
                trace_id=trace_id,
                test_run_id=str(db_test_run.id),
                test_id=str(db_test.id),
                test_configuration_id=str(db_test_configuration.id),
                project_id=str(db_project.id),
            )
            for _ in range(2)
        ]

        stored_early = crud.create_trace_spans(test_db, early_spans, str(test_organization.id))

        # Try linking early spans (no result yet)
        linking_service = TraceLinkingService(test_db)
        count1 = linking_service.link_traces_for_incoming_batch(
            spans=stored_early,
            organization_id=str(test_organization.id),
        )

        assert count1 == 0  # No result yet

        # Test completes and creates result
        test_result = self.create_test_result(
            db=test_db,
            test_run=db_test_run,
            test=db_test,
            test_configuration=db_test_configuration,
            organization_id=str(test_organization.id),
        )

        # Link early spans via result creation path
        count2 = linking_service.link_traces_for_test_result(
            test_run_id=str(db_test_run.id),
            test_id=str(db_test.id),
            test_configuration_id=str(db_test_configuration.id),
            test_result_id=str(test_result.id),
            organization_id=str(test_organization.id),
        )
        test_db.commit()  # Commit the transaction

        assert count2 == 2  # Early spans linked

        # Late spans arrive
        late_spans = [
            self.create_test_span(
                trace_id=trace_id,
                test_run_id=str(db_test_run.id),
                test_id=str(db_test.id),
                test_configuration_id=str(db_test_configuration.id),
                project_id=str(db_project.id),
            )
            for _ in range(3)
        ]

        stored_late = crud.create_trace_spans(test_db, late_spans, str(test_organization.id))

        # Link late spans via telemetry path
        count3 = linking_service.link_traces_for_incoming_batch(
            spans=stored_late,
            organization_id=str(test_organization.id),
        )
        test_db.commit()  # Commit the transaction

        assert count3 == 3  # Late spans linked

        # Verify all traces linked
        test_db.expire_all()  # Expire session cache to reload from database
        all_traces = test_db.query(models.Trace).filter(models.Trace.trace_id == trace_id).all()

        assert len(all_traces) == 5
        for trace in all_traces:
            assert trace.test_result_id == test_result.id

    @pytest.mark.asyncio
    async def test_end_to_end_with_enrichment(
        self, test_db, test_organization, db_project, db_test, db_test_run, db_test_configuration
    ):
        """
        Test complete flow: span ingestion → enrichment → linking.

        This tests the real flow through the telemetry endpoint.
        """
        # Setup test context (use unique trace_id for each test)
        trace_id = uuid4().hex

        # Create test result first
        test_result = self.create_test_result(
            db=test_db,
            test_run=db_test_run,
            test=db_test,
            test_configuration=db_test_configuration,
            organization_id=str(test_organization.id),
        )

        # Create spans
        spans = [
            self.create_test_span(
                trace_id=trace_id,
                test_run_id=str(db_test_run.id),
                test_id=str(db_test.id),
                test_configuration_id=str(db_test_configuration.id),
                project_id=str(db_project.id),
            )
            for _ in range(5)
        ]

        # Use EnrichmentService (simulates telemetry endpoint flow)
        enrichment_service = EnrichmentService(test_db)

        # Mock worker check to force sync enrichment
        with patch.object(enrichment_service, "_check_workers_available", return_value=False):
            stored_spans, async_count, sync_count = enrichment_service.create_and_enrich_spans(
                spans=spans,
                organization_id=str(test_organization.id),
                project_id=str(db_project.id),
            )

        assert len(stored_spans) == 5
        assert sync_count == 1  # Sync enrichment used

        # Link traces
        linking_service = TraceLinkingService(test_db)
        linked_count = linking_service.link_traces_for_incoming_batch(
            spans=stored_spans,
            organization_id=str(test_organization.id),
        )
        test_db.commit()  # Commit the transaction

        assert linked_count == 5

        # Verify all traces linked and enriched
        test_db.expire_all()  # Expire session cache to reload from database
        all_traces = test_db.query(models.Trace).filter(models.Trace.trace_id == trace_id).all()

        assert len(all_traces) == 5
        for trace in all_traces:
            assert trace.test_result_id == test_result.id
            # Enrichment should have been triggered
            assert trace.enriched_data is not None or trace.processed_at is not None

    def test_idempotent_linking_multiple_batches(
        self, test_db, test_organization, db_project, db_test, db_test_run, db_test_configuration
    ):
        """
        Test that linking is idempotent across multiple batch arrivals.

        Scenario:
        - Multiple batches of the same test arrive
        - Each batch triggers linking
        - No duplicate linking occurs
        """
        # Setup test context (use unique trace_id for each test)
        trace_id = uuid4().hex

        # Create test result
        test_result = self.create_test_result(
            db=test_db,
            test_run=db_test_run,
            test=db_test,
            test_configuration=db_test_configuration,
            organization_id=str(test_organization.id),
        )

        linking_service = TraceLinkingService(test_db)

        # Batch 1 arrives
        batch1 = [
            self.create_test_span(
                trace_id=trace_id,
                test_run_id=str(db_test_run.id),
                test_id=str(db_test.id),
                test_configuration_id=str(db_test_configuration.id),
                project_id=str(db_project.id),
            )
            for _ in range(3)
        ]

        stored1 = crud.create_trace_spans(test_db, batch1, str(test_organization.id))
        count1 = linking_service.link_traces_for_incoming_batch(
            spans=stored1, organization_id=str(test_organization.id)
        )
        test_db.commit()  # Commit the transaction

        assert count1 == 3

        # Batch 2 arrives
        batch2 = [
            self.create_test_span(
                trace_id=trace_id,
                test_run_id=str(db_test_run.id),
                test_id=str(db_test.id),
                test_configuration_id=str(db_test_configuration.id),
                project_id=str(db_project.id),
            )
            for _ in range(2)
        ]

        stored2 = crud.create_trace_spans(test_db, batch2, str(test_organization.id))
        count2 = linking_service.link_traces_for_incoming_batch(
            spans=stored2, organization_id=str(test_organization.id)
        )
        test_db.commit()  # Commit the transaction

        assert count2 == 2  # Only new spans linked

        # Verify total
        test_db.expire_all()  # Expire session cache to reload from database
        all_traces = test_db.query(models.Trace).filter(models.Trace.trace_id == trace_id).all()

        assert len(all_traces) == 5
        for trace in all_traces:
            assert trace.test_result_id == test_result.id

    def test_non_test_traces_not_linked(self, test_db, test_organization, db_project):
        """
        Test that non-test traces (without test context) are not linked.
        """
        # Create regular trace without test context
        trace_id = fake.hexify(text="^" * 32, upper=False)
        now = datetime.now(timezone.utc)

        regular_span = OTELSpanCreate(
            trace_id=trace_id,
            span_id=fake.hexify(text="^" * 16, upper=False),
            project_id=str(db_project.id),
            environment="production",
            span_name="ai.llm.invoke",
            span_kind=SpanKind.INTERNAL,
            start_time=now,
            end_time=now,
            status_code=StatusCode.OK,
            attributes={},  # No test context
        )

        stored = crud.create_trace_spans(test_db, [regular_span], str(test_organization.id))

        # Try linking
        linking_service = TraceLinkingService(test_db)
        count = linking_service.link_traces_for_incoming_batch(
            spans=stored, organization_id=str(test_organization.id)
        )

        assert count == 0  # Not a test trace, should skip

        # Verify trace has no test_result_id
        test_db.refresh(stored[0])
        assert stored[0].test_result_id is None
