"""Integration tests for POST /preflight-checks.

The handler is ``async def`` and holds an ``OffLoopSession``: it resolves the
requested test sets in a worker thread and then hands the session to the
orchestrator, which only touches it off the loop too. These tests pin the
behaviour that has to survive that -- the 404 for an unknown test set, the sync
200, and the async 202 with its applicable-check list.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus
from rhesis.backend.app.services.preflight import (
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_TEST_SET_NOT_EMPTY,
    LABELS,
)

ORCHESTRATOR = "rhesis.backend.app.routers.preflight.run_preflight_checks_multi"


@pytest.fixture
def preflight_test_sets(test_db: Session, test_org_id, authenticated_user_id):
    """Two test sets, so the composite-key (multi) path is exercised."""
    created = []
    for i in range(2):
        ts = models.TestSet(
            name=f"Preflight Set {i} {uuid.uuid4().hex[:8]}",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(ts)
        created.append(ts)
    test_db.commit()
    for ts in created:
        test_db.refresh(ts)
    return created


@pytest.mark.integration
class TestRunPreflight:
    def test_unknown_test_set_returns_404(self, authenticated_client: TestClient):
        missing = str(uuid.uuid4())
        response = authenticated_client.post(
            "/preflight-checks",
            json={"test_set_ids": [missing], "endpoint_id": str(uuid.uuid4())},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert missing in response.json()["detail"]

    @patch(ORCHESTRATOR, new_callable=AsyncMock)
    def test_sync_mode_returns_summary(
        self,
        mock_run: AsyncMock,
        authenticated_client: TestClient,
        preflight_test_sets,
    ):
        mock_run.return_value = [
            PreflightCheckResult(
                check_id=CHECK_EVALUATION_MODEL,
                label=LABELS[CHECK_EVALUATION_MODEL],
                status=PreflightCheckStatus.PASSED,
            ),
            PreflightCheckResult(
                check_id=CHECK_TEST_SET_NOT_EMPTY,
                label=LABELS[CHECK_TEST_SET_NOT_EMPTY],
                status=PreflightCheckStatus.FAILED,
            ),
        ]

        response = authenticated_client.post(
            "/preflight-checks",
            json={
                "test_set_ids": [str(preflight_test_sets[0].id)],
                "endpoint_id": str(uuid.uuid4()),
                "mode": "sync",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["summary"] == "failed"
        assert data["passed"] == 1
        assert data["failed"] == 1
        assert len(data["checks"]) == 2

        # The orchestrator still gets plain (id, name, multi-turn) tuples in request order.
        call_kw = mock_run.call_args[1]
        assert call_kw["test_sets"] == [
            (preflight_test_sets[0].id, preflight_test_sets[0].name, False)
        ]
        assert call_kw["publish"] is False

    @patch(ORCHESTRATOR, new_callable=AsyncMock)
    def test_async_mode_returns_202_with_applicable_checks(
        self,
        mock_run: AsyncMock,
        authenticated_client: TestClient,
        preflight_test_sets,
    ):
        mock_run.return_value = []
        ids = [str(ts.id) for ts in preflight_test_sets]

        response = authenticated_client.post(
            "/preflight-checks",
            json={"test_set_ids": ids, "endpoint_id": str(uuid.uuid4())},
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["correlation_id"]

        connectivity = [c for c in data["checks"] if c["check_id"] == CHECK_ENDPOINT_CONNECTIVITY]
        assert len(connectivity) == 1
        assert connectivity[0]["applicable"] is True

        # Per-test-set checks carry a composite key per test set when there are several.
        not_empty = [c for c in data["checks"] if c["check_id"] == CHECK_TEST_SET_NOT_EMPTY]
        assert {c["test_set_id"] for c in not_empty} == set(ids)
        assert all(
            c["composite_key"] == f"{CHECK_TEST_SET_NOT_EMPTY}:{c['test_set_id']}"
            for c in not_empty
        )

    @patch(ORCHESTRATOR, new_callable=AsyncMock)
    def test_reuse_marks_connectivity_not_applicable(
        self,
        mock_run: AsyncMock,
        authenticated_client: TestClient,
        preflight_test_sets,
    ):
        mock_run.return_value = []

        response = authenticated_client.post(
            "/preflight-checks",
            json={
                "test_set_ids": [str(preflight_test_sets[0].id)],
                "endpoint_id": str(uuid.uuid4()),
                "scoring_target": "reuse",
            },
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        connectivity = [
            c for c in response.json()["checks"] if c["check_id"] == CHECK_ENDPOINT_CONNECTIVITY
        ]
        assert connectivity[0]["applicable"] is False
