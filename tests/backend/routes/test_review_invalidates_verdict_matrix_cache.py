"""The three review write endpoints bust VerdictMatrixCache for their run.

Seeds a cache entry directly (bypassing get_verdict_matrix) so each test only
has to prove the endpoint's invalidate() call fires -- correctness of what
gets cached is covered by tests/backend/services/test_verdict_matrix.py's
TestVerdictMatrixCaching.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app import models
from rhesis.backend.app.services.verdict_matrix_cache import get_verdict_matrix_cache


def _create_pass_status(test_db, test_organization, test_type_lookup, db_user):
    pass_status = models.Status(
        name="Pass",
        description="Passed evaluation",
        entity_type_id=test_type_lookup.id,
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    test_db.add(pass_status)
    test_db.commit()
    test_db.refresh(pass_status)
    return pass_status


def _make_test_result(test_db, test_organization, db_user, db_test_configuration, db_test_run):
    result = models.TestResult(
        test_run_id=db_test_run.id,
        test_configuration_id=db_test_configuration.id,
        organization_id=test_organization.id,
        user_id=db_user.id,
        execution="ok",
        verdict="fail",
        test_metrics={"metrics": {"Accuracy": {"is_successful": False}}},
    )
    test_db.add(result)
    test_db.commit()
    test_db.refresh(result)
    return result


def _seed_cache(test_run_id) -> None:
    cache = get_verdict_matrix_cache()
    cache.set(str(test_run_id), None, '{"seeded": true}')
    cache.set(str(test_run_id), "none", '{"seeded": true}')


def _cache_is_empty(test_run_id) -> bool:
    cache = get_verdict_matrix_cache()
    return (
        cache.get(str(test_run_id), None) is None and cache.get(str(test_run_id), "none") is None
    )


@pytest.mark.integration
class TestReviewWritesInvalidateVerdictMatrixCache:
    def test_add_review_invalidates(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        test_type_lookup,
        db_test_configuration,
        db_test_run,
    ):
        pass_status = _create_pass_status(test_db, test_organization, test_type_lookup, db_user)
        result = _make_test_result(
            test_db, test_organization, db_user, db_test_configuration, db_test_run
        )
        _seed_cache(db_test_run.id)
        assert not _cache_is_empty(db_test_run.id)

        response = authenticated_client.post(
            f"/test_results/{result.id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Reviewed",
                "target": {"type": "test_result", "reference": None},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert _cache_is_empty(db_test_run.id)

    def test_update_review_invalidates(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        test_type_lookup,
        db_test_configuration,
        db_test_run,
    ):
        pass_status = _create_pass_status(test_db, test_organization, test_type_lookup, db_user)
        result = _make_test_result(
            test_db, test_organization, db_user, db_test_configuration, db_test_run
        )
        created = authenticated_client.post(
            f"/test_results/{result.id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Reviewed",
                "target": {"type": "test_result", "reference": None},
            },
        ).json()

        _seed_cache(db_test_run.id)
        assert not _cache_is_empty(db_test_run.id)

        response = authenticated_client.put(
            f"/test_results/{result.id}/reviews/{created['review_id']}",
            json={"comments": "Updated comment"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert _cache_is_empty(db_test_run.id)

    def test_delete_review_invalidates(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        test_type_lookup,
        db_test_configuration,
        db_test_run,
    ):
        pass_status = _create_pass_status(test_db, test_organization, test_type_lookup, db_user)
        result = _make_test_result(
            test_db, test_organization, db_user, db_test_configuration, db_test_run
        )
        created = authenticated_client.post(
            f"/test_results/{result.id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Reviewed",
                "target": {"type": "test_result", "reference": None},
            },
        ).json()

        _seed_cache(db_test_run.id)
        assert not _cache_is_empty(db_test_run.id)

        response = authenticated_client.delete(
            f"/test_results/{result.id}/reviews/{created['review_id']}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert _cache_is_empty(db_test_run.id)
