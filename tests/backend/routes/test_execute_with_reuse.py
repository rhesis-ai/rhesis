"""
Integration tests for test set execution with output reuse (re-scoring)
and the last-run lookup endpoint.

These tests verify:
- execute endpoint accepts reference_test_run_id and stores it in config
- last-run endpoint returns the most recent run for a test set + endpoint
- validation rejects invalid reference run IDs
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.services.test_set import (
    _validate_reference_test_run,
    execute_test_set_on_endpoint,
    get_last_completed_test_run,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_type_lookup(db, type_name, type_value, org_id, user_id):
    """Create or find a TypeLookup."""
    existing = (
        db.query(models.TypeLookup)
        .filter(
            models.TypeLookup.type_name == type_name,
            models.TypeLookup.type_value == type_value,
            models.TypeLookup.organization_id == org_id,
        )
        .first()
    )
    if existing:
        return existing
    tl = models.TypeLookup(
        type_name=type_name,
        type_value=type_value,
        organization_id=org_id,
        user_id=user_id,
    )
    db.add(tl)
    db.flush()
    return tl


def _get_or_create_status(db, name, org_id, user_id):
    """Get or create a Status record."""
    status = (
        db.query(models.Status)
        .filter(
            models.Status.name == name,
            models.Status.organization_id == org_id,
        )
        .first()
    )
    if status:
        return status
    status = models.Status(
        name=name,
        organization_id=org_id,
        user_id=user_id,
    )
    db.add(status)
    db.flush()
    return status


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_test_set(test_db, test_org_id, authenticated_user_id):
    """Create a test set with a test set type."""
    ts_type = _create_type_lookup(
        test_db,
        "TestSetType",
        "Single-Turn",
        test_org_id,
        authenticated_user_id,
    )
    test_set = models.TestSet(
        name=f"Reuse Test Set {uuid.uuid4().hex[:8]}",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        test_set_type_id=ts_type.id,
    )
    test_db.add(test_set)
    test_db.flush()
    return test_set


@pytest.fixture
def db_project(test_db, test_org_id, authenticated_user_id):
    """Create a project."""
    project = models.Project(
        name=f"Reuse Project {uuid.uuid4().hex[:8]}",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(project)
    test_db.flush()
    return project


@pytest.fixture
def db_endpoint(test_db, test_org_id, authenticated_user_id, db_project):
    """Create an endpoint."""
    endpoint = models.Endpoint(
        name=f"Reuse Endpoint {uuid.uuid4().hex[:8]}",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        project_id=db_project.id,
        connection_type="rest",
        url="https://example.com/api",
    )
    test_db.add(endpoint)
    test_db.flush()
    return endpoint


@pytest.fixture
def db_test_config(
    test_db,
    test_org_id,
    authenticated_user_id,
    db_test_set,
    db_endpoint,
):
    """Create a test configuration."""
    config = models.TestConfiguration(
        test_set_id=db_test_set.id,
        endpoint_id=db_endpoint.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(config)
    test_db.flush()
    return config


@pytest.fixture
def db_test_run(
    test_db,
    test_org_id,
    authenticated_user_id,
    db_test_config,
):
    """Create a completed test run."""
    completed_status = _get_or_create_status(
        test_db, "Completed", test_org_id, authenticated_user_id
    )
    run = models.TestRun(
        test_configuration_id=db_test_config.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        status_id=completed_status.id,
        name=f"Reference Run {uuid.uuid4().hex[:8]}",
    )
    test_db.add(run)
    test_db.flush()
    return run


@pytest.fixture
def db_test_results(test_db, test_org_id, authenticated_user_id, db_test_run):
    """Create test results for the test run."""
    passed_status = _get_or_create_status(test_db, "Passed", test_org_id, authenticated_user_id)
    failed_status = _get_or_create_status(test_db, "Failed", test_org_id, authenticated_user_id)

    results = []
    for i in range(3):
        result = models.TestResult(
            test_run_id=db_test_run.id,
            test_id=None,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=passed_status.id if i < 2 else failed_status.id,
            test_output={"output": f"response {i}"},
            test_metrics={
                "execution_time": 100,
                "metrics": {},
            },
        )
        test_db.add(result)
        results.append(result)
    test_db.flush()
    return results


# ---------------------------------------------------------------------------
# Tests: _validate_reference_test_run
# ---------------------------------------------------------------------------


class TestValidateReferenceTestRun:
    """Tests for the reference test run validation logic."""

    def test_valid_reference_run(
        self,
        test_db,
        db_test_set,
        db_test_run,
        db_test_config,
    ):
        """Validation passes when reference run exists and matches
        the same test set and organization."""
        # Create a mock user with matching org
        user = MagicMock()
        user.organization_id = db_test_run.organization_id
        user.id = db_test_run.user_id

        # Should not raise
        _validate_reference_test_run(test_db, db_test_run.id, db_test_set, user)

    def test_nonexistent_reference_run(self, test_db, db_test_set):
        """Validation raises ValueError for a non-existent run ID."""
        user = MagicMock()
        user.organization_id = db_test_set.organization_id
        user.id = db_test_set.user_id

        with pytest.raises(ValueError, match="Reference test run not found"):
            _validate_reference_test_run(test_db, uuid.uuid4(), db_test_set, user)

    def test_reference_run_wrong_test_set(
        self,
        test_db,
        test_org_id,
        authenticated_user_id,
        db_test_run,
        db_endpoint,
    ):
        """Validation raises ValueError when the reference run belongs
        to a different test set."""
        # Create a second test set
        ts_type = _create_type_lookup(
            test_db,
            "TestSetType",
            "Single-Turn",
            test_org_id,
            authenticated_user_id,
        )
        other_test_set = models.TestSet(
            name=f"Other Test Set {uuid.uuid4().hex[:8]}",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            test_set_type_id=ts_type.id,
        )
        test_db.add(other_test_set)
        test_db.flush()

        user = MagicMock()
        user.organization_id = test_org_id
        user.id = authenticated_user_id

        with pytest.raises(ValueError, match="different test set"):
            _validate_reference_test_run(test_db, db_test_run.id, other_test_set, user)


# ---------------------------------------------------------------------------
# Tests: get_last_completed_test_run
# ---------------------------------------------------------------------------


class TestGetLastCompletedTestRun:
    """Tests for the last-run lookup service."""

    def test_returns_latest_run(
        self,
        test_db,
        test_org_id,
        authenticated_user_id,
        db_test_set,
        db_endpoint,
        db_test_run,
        db_test_results,
    ):
        """Returns summary of the latest test run."""
        result = get_last_completed_test_run(
            db=test_db,
            test_set_identifier=str(db_test_set.id),
            endpoint_id=db_endpoint.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result is not None
        assert result["id"] == str(db_test_run.id)
        assert result["nano_id"] == db_test_run.nano_id
        assert result["name"] == db_test_run.name
        assert result["test_count"] == 3
        # 2 passed out of 3 = 66.7%
        assert result["pass_rate"] == 66.7

    def test_returns_none_when_no_runs(
        self,
        test_db,
        test_org_id,
        authenticated_user_id,
        db_test_set,
        db_endpoint,
    ):
        """Returns None when no test runs exist for the combo."""
        result = get_last_completed_test_run(
            db=test_db,
            test_set_identifier=str(db_test_set.id),
            endpoint_id=db_endpoint.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result is None

    def test_returns_none_for_unknown_test_set(
        self,
        test_db,
        test_org_id,
        authenticated_user_id,
        db_endpoint,
    ):
        """Returns None when the test set does not exist."""
        result = get_last_completed_test_run(
            db=test_db,
            test_set_identifier=str(uuid.uuid4()),
            endpoint_id=db_endpoint.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result is None


# ---------------------------------------------------------------------------
# Tests: last-run endpoint via TestClient
# ---------------------------------------------------------------------------


class TestLastRunEndpoint:
    """Integration tests for GET /test_sets/{id}/last-run/{endpoint_id}."""

    def test_last_run_exists(
        self,
        authenticated_client,
        db_test_set,
        db_endpoint,
        db_test_run,
        db_test_results,
    ):
        """Endpoint returns 200 with run summary."""
        response = authenticated_client.get(
            f"/test_sets/{db_test_set.id}/last-run/{db_endpoint.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(db_test_run.id)
        assert data["nano_id"] == db_test_run.nano_id
        assert data["name"] == db_test_run.name
        assert data["test_count"] == 3
        assert data["pass_rate"] == 66.7

    def test_last_run_not_found(
        self,
        authenticated_client,
        db_test_set,
        db_endpoint,
    ):
        """Endpoint returns 404 when no runs exist."""
        response = authenticated_client.get(
            f"/test_sets/{db_test_set.id}/last-run/{db_endpoint.id}"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: execute with reference_test_run_id via service
# ---------------------------------------------------------------------------


class TestExecuteWithReuse:
    """Tests for execute_test_set_on_endpoint with reference_test_run_id."""

    @patch("rhesis.backend.app.services.test_set._submit_test_configuration_for_execution")
    def test_execute_stores_reference_in_config(
        self,
        mock_submit,
        test_db,
        test_org_id,
        authenticated_user_id,
        db_test_set,
        db_endpoint,
        db_test_run,
    ):
        """When reference_test_run_id is provided, it is stored in the
        test configuration attributes along with is_rescore=True."""
        # Mock the task launcher to return a fake result
        mock_task_result = MagicMock()
        mock_task_result.id = str(uuid.uuid4())
        mock_submit.return_value = mock_task_result

        # Build a mock user
        user = MagicMock()
        user.id = uuid.UUID(authenticated_user_id)
        user.organization_id = uuid.UUID(test_org_id)

        result = execute_test_set_on_endpoint(
            db=test_db,
            test_set_identifier=str(db_test_set.id),
            endpoint_id=db_endpoint.id,
            current_user=user,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            reference_test_run_id=db_test_run.id,
        )

        assert result["status"] == "submitted"

        # Verify the test configuration was created with the reference
        test_config_id = result["test_configuration_id"]
        config = (
            test_db.query(models.TestConfiguration)
            .filter(models.TestConfiguration.id == uuid.UUID(test_config_id))
            .first()
        )
        assert config is not None
        assert config.attributes is not None
        assert config.attributes.get("reference_test_run_id") == str(db_test_run.id)
        assert config.attributes.get("is_rescore") is True

    @patch("rhesis.backend.app.services.test_set._submit_test_configuration_for_execution")
    def test_execute_without_reference(
        self,
        mock_submit,
        test_db,
        test_org_id,
        authenticated_user_id,
        db_test_set,
        db_endpoint,
    ):
        """Normal execution without reference_test_run_id does not set
        is_rescore."""
        mock_task_result = MagicMock()
        mock_task_result.id = str(uuid.uuid4())
        mock_submit.return_value = mock_task_result

        user = MagicMock()
        user.id = uuid.UUID(authenticated_user_id)
        user.organization_id = uuid.UUID(test_org_id)

        result = execute_test_set_on_endpoint(
            db=test_db,
            test_set_identifier=str(db_test_set.id),
            endpoint_id=db_endpoint.id,
            current_user=user,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result["status"] == "submitted"

        test_config_id = result["test_configuration_id"]
        config = (
            test_db.query(models.TestConfiguration)
            .filter(models.TestConfiguration.id == uuid.UUID(test_config_id))
            .first()
        )
        assert config is not None
        # No rescore attributes
        attrs = config.attributes or {}
        assert "reference_test_run_id" not in attrs
        assert "is_rescore" not in attrs

    def test_execute_with_invalid_reference_run(
        self,
        test_db,
        test_org_id,
        authenticated_user_id,
        db_test_set,
        db_endpoint,
    ):
        """Execution with a non-existent reference_test_run_id raises
        ValueError."""
        user = MagicMock()
        user.id = uuid.UUID(authenticated_user_id)
        user.organization_id = uuid.UUID(test_org_id)

        with pytest.raises(ValueError, match="Reference test run not found"):
            execute_test_set_on_endpoint(
                db=test_db,
                test_set_identifier=str(db_test_set.id),
                endpoint_id=db_endpoint.id,
                current_user=user,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                reference_test_run_id=uuid.uuid4(),
            )
