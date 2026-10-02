"""
Tests for ``test_counts`` on the requirement read endpoints.

The requirement cards show how many tests link to each requirement, split by
single-/multi-turn. The count must match what the requirement's Linked tests
tab lists, so hidden tests (soft-deleted, Explorer, metric-owned) stay out.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models


@pytest.fixture
def count_scenario(test_db: Session, test_organization, db_user, db_status) -> dict:
    """A requirement with 2 multi-turn, 1 single-turn, 1 untyped and 3 hidden tests."""
    token = uuid.uuid4().hex[:8]
    org_id, user_id = test_organization.id, db_user.id

    def _row(model, **kwargs):
        row = model(organization_id=org_id, user_id=user_id, **kwargs)
        test_db.add(row)
        return row

    requirement = _row(models.Requirement, name=f"ZZCountReq-{token}")
    empty_requirement = _row(models.Requirement, name=f"ZZCountReqEmpty-{token}")
    multi_turn = _row(models.TypeLookup, type_name="TestType", type_value="Multi-Turn")
    single_turn = _row(models.TypeLookup, type_name="TestType", type_value="Single-Turn")
    metric = _row(
        models.Metric,
        name=f"ZZCountMetric-{token}",
        metric_scope=["Single-Turn"],
        evaluation_prompt="Judge it.",
        score_type="numeric",
    )
    test_db.flush()

    def _test(**kwargs):
        return _row(models.Test, status_id=db_status.id, requirement_id=requirement.id, **kwargs)

    _test(test_type_id=multi_turn.id)
    _test(test_type_id=multi_turn.id)
    _test(test_type_id=single_turn.id)
    _test()
    _test(test_type_id=multi_turn.id, deleted_at=datetime.now(timezone.utc))
    _test(test_type_id=multi_turn.id, explorer_row=True)
    _test(test_type_id=single_turn.id, metric_id=metric.id)
    test_db.flush()

    return {"requirement_id": requirement.id, "empty_requirement_id": empty_requirement.id}


EXPECTED = {"total": 4, "single_turn": 2, "multi_turn": 2}
EMPTY = {"total": 0, "single_turn": 0, "multi_turn": 0}


class TestRequirementTestCounts:
    def test_single_read_counts_visible_tests_by_type(
        self, authenticated_client: TestClient, count_scenario
    ):
        """Untyped tests count as single-turn; hidden tests don't count."""
        response = authenticated_client.get(f"/requirements/{count_scenario['requirement_id']}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["test_counts"] == EXPECTED

    def test_list_reports_counts_per_requirement(
        self, authenticated_client: TestClient, count_scenario
    ):
        response = authenticated_client.get(
            "/requirements/",
            params={"$filter": "startswith(name, 'ZZCountReq')", "limit": 100},
        )

        assert response.status_code == status.HTTP_200_OK
        by_id = {r["id"]: r["test_counts"] for r in response.json()}
        assert by_id[str(count_scenario["requirement_id"])] == EXPECTED
        assert by_id[str(count_scenario["empty_requirement_id"])] == EMPTY
