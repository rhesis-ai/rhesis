"""Tests for trace CRUD operations."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from rhesis.backend.app import crud, models
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate
from rhesis.sdk.telemetry.schemas import SpanKind, StatusCode


class TestUpdateTracesWithTestResultId:
    """Test update_traces_with_test_result_id function."""

    @pytest.fixture
    def test_project(self, test_db, test_org_id, authenticated_user_id):
        """Create a test project for traces."""
        project = models.Project(
            name="Test Project",
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)
        return project

    @pytest.fixture
    def test_endpoint(self, test_db, test_org_id, authenticated_user_id, test_project):
        """Create a test endpoint."""
        endpoint = models.Endpoint(
            name="Test Endpoint",
            connection_type="REST",
            url="https://api.example.com",
            endpoint_path="/test",
            project_id=test_project.id,
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_db.add(endpoint)
        test_db.commit()
        test_db.refresh(endpoint)
        return endpoint

    @pytest.fixture
    def test_configuration(self, test_db, test_org_id, authenticated_user_id, test_endpoint):
        """Create a test configuration."""
        test_config = models.TestConfiguration(
            endpoint_id=test_endpoint.id,
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_db.add(test_config)
        test_db.commit()
        test_db.refresh(test_config)
        return test_config

    @pytest.fixture
    def test_run(self, test_db, test_org_id, authenticated_user_id, test_configuration):
        """Create a test run for traces."""
        test_run = models.TestRun(
            test_configuration_id=test_configuration.id,
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_db.add(test_run)
        test_db.commit()
        test_db.refresh(test_run)
        return test_run

    @pytest.fixture
    def test_entity(self, test_db, test_org_id, authenticated_user_id):
        """Create a test entity for traces."""
        # Create prompt first (required for test)
        prompt = models.Prompt(
            content="Test prompt",
            language_code="en",
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_db.add(prompt)
        test_db.flush()

        # Create test
        test = models.Test(
            prompt_id=prompt.id,
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_db.add(test)
        test_db.commit()
        test_db.refresh(test)
        return test

    @pytest.fixture
    def test_result(
        self, test_db, test_org_id, authenticated_user_id, test_run, test_entity, test_configuration
    ):
        """Create a test result for FK constraints."""
        test_result = models.TestResult(
            test_id=test_entity.id,
            test_run_id=test_run.id,
            test_configuration_id=test_configuration.id,
            prompt_id=test_entity.prompt_id,
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_db.add(test_result)
        test_db.commit()
        test_db.refresh(test_result)
        return test_result

    def test_update_traces_success(
        self,
        test_db,
        test_org_id,
        test_project,
        test_run,
        test_entity,
        test_configuration,
        test_result,
    ):
        """Test updating traces with test_result_id."""
        # Create trace using CRUD (respects FK constraints)
        span = OTELSpanCreate(
            trace_id="a" * 32,
            span_id="b" * 16,
            project_id=str(test_project.id),
            environment="test",
            span_name="function.test",
            span_kind=SpanKind.INTERNAL,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            status_code=StatusCode.OK,
            attributes={
                "rhesis.test.run_id": str(test_run.id),
                "rhesis.test.id": str(test_entity.id),
                "rhesis.test.configuration_id": str(test_configuration.id),
            },
        )

        stored_spans = crud.create_trace_spans(test_db, [span], str(test_org_id))
        assert len(stored_spans) == 1
        assert stored_spans[0].test_result_id is None

        # Update traces with test_result_id
        updated_count = crud.update_traces_with_test_result_id(
            test_db,
            test_run_id=str(test_run.id),
            test_id=str(test_entity.id),
            test_configuration_id=str(test_configuration.id),
            test_result_id=str(test_result.id),
            organization_id=str(test_org_id),
        )

        assert updated_count == 1

        # Verify update
        test_db.refresh(stored_spans[0])
        assert stored_spans[0].test_result_id == test_result.id

    def test_update_traces_idempotent(
        self,
        test_db,
        test_org_id,
        test_project,
        test_run,
        test_entity,
        test_configuration,
        test_result,
    ):
        """Test that update is idempotent."""
        # Create and store trace
        span = OTELSpanCreate(
            trace_id="c" * 32,
            span_id="d" * 16,
            project_id=str(test_project.id),
            environment="test",
            span_name="function.test",
            span_kind=SpanKind.INTERNAL,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            status_code=StatusCode.OK,
            attributes={
                "rhesis.test.run_id": str(test_run.id),
                "rhesis.test.id": str(test_entity.id),
                "rhesis.test.configuration_id": str(test_configuration.id),
            },
        )

        stored_spans = crud.create_trace_spans(test_db, [span], str(test_org_id))
        assert len(stored_spans) == 1

        # Update once
        updated_count = crud.update_traces_with_test_result_id(
            test_db,
            test_run_id=str(test_run.id),
            test_id=str(test_entity.id),
            test_configuration_id=str(test_configuration.id),
            test_result_id=str(test_result.id),
            organization_id=str(test_org_id),
        )
        assert updated_count == 1

        # Update again
        updated_count = crud.update_traces_with_test_result_id(
            test_db,
            test_run_id=str(test_run.id),
            test_id=str(test_entity.id),
            test_configuration_id=str(test_configuration.id),
            test_result_id=str(test_result.id),
            organization_id=str(test_org_id),
        )

        # Should return 0 (already updated)
        assert updated_count == 0

        # Verify test_result_id is still correct
        test_db.refresh(stored_spans[0])
        assert stored_spans[0].test_result_id == test_result.id

    def test_update_traces_no_matches(self, test_db, test_org_id):
        """Test update with no matching traces."""
        updated_count = crud.update_traces_with_test_result_id(
            test_db,
            test_run_id=str(uuid4()),
            test_id=str(uuid4()),
            test_configuration_id=str(uuid4()),
            test_result_id=str(uuid4()),
            organization_id=str(test_org_id),
        )

        assert updated_count == 0

    def test_update_multiple_spans_same_trace(
        self,
        test_db,
        test_org_id,
        test_project,
        test_run,
        test_entity,
        test_configuration,
        test_result,
    ):
        """Test updating multiple spans from same test execution."""
        # Create multiple spans with same test context
        spans = [
            OTELSpanCreate(
                trace_id="e" * 32,
                span_id=f"f{i:015d}",
                project_id=str(test_project.id),
                environment="test",
                span_name=f"function.test_{i}",
                span_kind=SpanKind.INTERNAL,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                status_code=StatusCode.OK,
                attributes={
                    "rhesis.test.run_id": str(test_run.id),
                    "rhesis.test.id": str(test_entity.id),
                    "rhesis.test.configuration_id": str(test_configuration.id),
                },
            )
            for i in range(3)
        ]

        stored_spans = crud.create_trace_spans(test_db, spans, str(test_org_id))
        assert len(stored_spans) == 3

        # Verify all have NULL test_result_id
        for span in stored_spans:
            assert span.test_result_id is None

        # Update all spans
        updated_count = crud.update_traces_with_test_result_id(
            test_db,
            test_run_id=str(test_run.id),
            test_id=str(test_entity.id),
            test_configuration_id=str(test_configuration.id),
            test_result_id=str(test_result.id),
            organization_id=str(test_org_id),
        )

        assert updated_count == 3

        # Verify all updated
        for span in stored_spans:
            test_db.refresh(span)
            assert span.test_result_id == test_result.id

    def test_update_traces_only_updates_null(
        self,
        test_db,
        test_org_id,
        test_project,
        test_run,
        test_entity,
        test_configuration,
        authenticated_user_id,
    ):
        """Test that update only affects spans with NULL test_result_id."""
        # Create TWO test results
        test_result_1 = models.TestResult(
            test_id=test_entity.id,
            test_run_id=test_run.id,
            test_configuration_id=test_configuration.id,
            prompt_id=test_entity.prompt_id,
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_result_2 = models.TestResult(
            test_id=test_entity.id,
            test_run_id=test_run.id,
            test_configuration_id=test_configuration.id,
            prompt_id=test_entity.prompt_id,
            organization_id=UUID(test_org_id),
            user_id=UUID(authenticated_user_id),
        )
        test_db.add_all([test_result_1, test_result_2])
        test_db.commit()
        test_db.refresh(test_result_1)
        test_db.refresh(test_result_2)

        # Create 3 spans
        spans = []
        for i in range(3):
            spans.append(
                OTELSpanCreate(
                    trace_id="0" * 31 + str(i),  # Valid hex string
                    span_id=f"{i:016x}",  # Valid 16-char hex string
                    project_id=str(test_project.id),
                    environment="test",
                    span_name=f"function.test_{i}",
                    span_kind=SpanKind.INTERNAL,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    status_code=StatusCode.OK,
                    attributes={
                        "rhesis.test.run_id": str(test_run.id),
                        "rhesis.test.id": str(test_entity.id),
                        "rhesis.test.configuration_id": str(test_configuration.id),
                    },
                )
            )

        stored_spans = crud.create_trace_spans(test_db, spans, str(test_org_id))
        assert len(stored_spans) == 3

        # Manually set test_result_id for first span (simulating it already being set)
        stored_spans[0].test_result_id = test_result_1.id
        test_db.commit()
        test_db.refresh(stored_spans[0])

        # Update with different test_result_id
        updated_count = crud.update_traces_with_test_result_id(
            test_db,
            test_run_id=str(test_run.id),
            test_id=str(test_entity.id),
            test_configuration_id=str(test_configuration.id),
            test_result_id=str(test_result_2.id),
            organization_id=str(test_org_id),
        )

        # Should only update 2 spans (the ones with NULL test_result_id)
        assert updated_count == 2

        # Verify first span still has original test_result_id
        test_db.refresh(stored_spans[0])
        assert stored_spans[0].test_result_id == test_result_1.id

        # Verify other spans have new test_result_id
        for span in stored_spans[1:]:
            test_db.refresh(span)
            assert span.test_result_id == test_result_2.id

    def test_update_traces_filters_by_context(
        self, test_db, test_org_id, test_project, test_entity, test_configuration
    ):
        """Test that update only affects spans matching full test context."""
        # Create TWO test runs
        test_run_1 = models.TestRun(
            test_configuration_id=test_configuration.id,
            organization_id=UUID(test_org_id),
            user_id=test_entity.user_id,
        )
        test_run_2 = models.TestRun(
            test_configuration_id=test_configuration.id,
            organization_id=UUID(test_org_id),
            user_id=test_entity.user_id,
        )
        test_db.add_all([test_run_1, test_run_2])
        test_db.commit()
        test_db.refresh(test_run_1)
        test_db.refresh(test_run_2)

        # Create test result for test_run_1
        test_result_1 = models.TestResult(
            test_id=test_entity.id,
            test_run_id=test_run_1.id,
            test_configuration_id=test_configuration.id,
            prompt_id=test_entity.prompt_id,
            organization_id=UUID(test_org_id),
            user_id=test_entity.user_id,
        )
        test_db.add(test_result_1)
        test_db.commit()
        test_db.refresh(test_result_1)

        # Create span for test_run_1
        span1 = OTELSpanCreate(
            trace_id="1" * 32,  # Valid hex string
            span_id="a" * 16,  # Valid hex string
            project_id=str(test_project.id),
            environment="test",
            span_name="function.test_1",
            span_kind=SpanKind.INTERNAL,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            status_code=StatusCode.OK,
            attributes={
                "rhesis.test.run_id": str(test_run_1.id),
                "rhesis.test.id": str(test_entity.id),
                "rhesis.test.configuration_id": str(test_configuration.id),
            },
        )

        # Create span for test_run_2
        span2 = OTELSpanCreate(
            trace_id="2" * 32,  # Valid hex string
            span_id="b" * 16,  # Valid hex string
            project_id=str(test_project.id),
            environment="test",
            span_name="function.test_2",
            span_kind=SpanKind.INTERNAL,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            status_code=StatusCode.OK,
            attributes={
                "rhesis.test.run_id": str(test_run_2.id),
                "rhesis.test.id": str(test_entity.id),
                "rhesis.test.configuration_id": str(test_configuration.id),
            },
        )

        stored_spans = crud.create_trace_spans(test_db, [span1, span2], str(test_org_id))
        assert len(stored_spans) == 2

        # Update only test_run_1
        updated_count = crud.update_traces_with_test_result_id(
            test_db,
            test_run_id=str(test_run_1.id),
            test_id=str(test_entity.id),
            test_configuration_id=str(test_configuration.id),
            test_result_id=str(test_result_1.id),
            organization_id=str(test_org_id),
        )

        # Should only update 1 span
        assert updated_count == 1

        # Verify first span updated
        test_db.refresh(stored_spans[0])
        assert stored_spans[0].test_result_id == test_result_1.id

        # Verify second span not updated
        test_db.refresh(stored_spans[1])
        assert stored_spans[1].test_result_id is None
