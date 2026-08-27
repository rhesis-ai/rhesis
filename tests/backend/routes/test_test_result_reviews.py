"""
Tests for test-result-level review endpoints in rhesis.backend.app.routers.test_result

Covers POST/PUT/DELETE /test_results/{id}/reviews for REVIEW_TARGET_TEST_RESULT
(reference=None) -- the first route-level coverage of this endpoint. See
app/services/review_override.py for the outcome-write logic being exercised.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app import models


def _create_pass_fail_statuses(test_db, test_organization, test_type_lookup, db_user):
    from rhesis.backend.app.models.status import Status

    pass_status = Status(
        name="Pass",
        description="Passed evaluation",
        entity_type_id=test_type_lookup.id,
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    fail_status = Status(
        name="Fail",
        description="Failed evaluation",
        entity_type_id=test_type_lookup.id,
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    test_db.add_all([pass_status, fail_status])
    test_db.commit()
    test_db.refresh(pass_status)
    test_db.refresh(fail_status)
    return pass_status, fail_status


@pytest.fixture
def pass_fail_statuses(test_db, test_organization, test_type_lookup, db_user):
    return _create_pass_fail_statuses(test_db, test_organization, test_type_lookup, db_user)


def _make_test_result(
    test_db, test_organization, db_user, db_test_configuration, db_test_run, *, metrics=None
):
    result = models.TestResult(
        test_run_id=db_test_run.id,
        test_configuration_id=db_test_configuration.id,
        organization_id=test_organization.id,
        user_id=db_user.id,
        execution="ok" if metrics else "error",
        verdict="fail" if metrics else None,
        test_metrics={"metrics": metrics} if metrics is not None else None,
    )
    test_db.add(result)
    test_db.commit()
    test_db.refresh(result)
    return result


@pytest.mark.integration
class TestAddTestResultReview:
    """Test POST /test_results/{id}/reviews, target type 'test_result'."""

    def test_review_flips_execution_and_verdict(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_test_configuration,
        db_test_run,
        pass_fail_statuses,
    ):
        pass_status, _ = pass_fail_statuses
        result = _make_test_result(
            test_db,
            test_organization,
            db_user,
            db_test_configuration,
            db_test_run,
            metrics={"Accuracy": {"is_successful": False}},
        )

        response = authenticated_client.post(
            f"/test_results/{result.id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Actually correct on review",
                "target": {"type": "test_result", "reference": None},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"]["name"] == "Pass"
        assert body["target"]["type"] == "test_result"

        test_db.refresh(result)
        assert result.execution == "ok"
        assert result.verdict == "pass"

    def test_review_on_result_with_no_evaluable_content_stays_error(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_test_configuration,
        db_test_run,
        pass_fail_statuses,
    ):
        """A human can still leave a review, but the persisted outcome must
        not become 'ok' from a result that never produced anything to
        evaluate -- see review_override._has_evaluable_content.
        """
        pass_status, _ = pass_fail_statuses
        result = _make_test_result(
            test_db, test_organization, db_user, db_test_configuration, db_test_run, metrics=None
        )

        response = authenticated_client.post(
            f"/test_results/{result.id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Marking pass anyway",
                "target": {"type": "test_result", "reference": None},
            },
        )

        assert response.status_code == status.HTTP_200_OK

        test_db.refresh(result)
        assert result.execution == "error"
        assert result.verdict is None


@pytest.mark.integration
class TestDeleteTestResultReview:
    def test_deleting_the_only_review_reverts_to_automated_verdict(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_test_configuration,
        db_test_run,
        pass_fail_statuses,
    ):
        pass_status, _ = pass_fail_statuses
        result = _make_test_result(
            test_db,
            test_organization,
            db_user,
            db_test_configuration,
            db_test_run,
            metrics={"Accuracy": {"is_successful": False}},
        )

        create_response = authenticated_client.post(
            f"/test_results/{result.id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Overriding to pass",
                "target": {"type": "test_result", "reference": None},
            },
        )
        review_id = create_response.json()["review_id"]

        test_db.refresh(result)
        assert result.verdict == "pass"  # override applied

        delete_response = authenticated_client.delete(
            f"/test_results/{result.id}/reviews/{review_id}"
        )
        assert delete_response.status_code == status.HTTP_200_OK

        test_db.refresh(result)
        # Reverts to the automated verdict computed from test_metrics, which
        # never changed -- the review only ever touched execution/verdict.
        assert result.execution == "ok"
        assert result.verdict == "fail"
