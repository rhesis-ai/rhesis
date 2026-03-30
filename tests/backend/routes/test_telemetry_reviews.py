"""
Tests for trace review endpoints in rhesis.backend.app.routers.telemetry

Covers POST/PUT/DELETE /telemetry/traces/{trace_db_id}/reviews
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tests.backend.routes.fixtures.data_factories import TraceDataFactory


def _create_pass_fail_statuses(test_db, test_organization, test_type_lookup, db_user):
    """Create Pass and Fail statuses required for reviews."""
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
    test_db.add(pass_status)
    test_db.add(fail_status)
    test_db.commit()
    test_db.refresh(pass_status)
    test_db.refresh(fail_status)
    return pass_status, fail_status


@pytest.fixture
def pass_fail_statuses(test_db, test_organization, test_type_lookup, db_user):
    return _create_pass_fail_statuses(test_db, test_organization, test_type_lookup, db_user)


def _ingest_trace(client: TestClient, project_id: str) -> dict:
    """Ingest a single trace span and return its database ID."""
    span_data = TraceDataFactory.sample_data(project_id=project_id)
    trace_batch = {"spans": [span_data]}
    response = client.post("/telemetry/traces", json=trace_batch)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    return {
        "trace_id": span_data["trace_id"],
        "span_id": span_data["span_id"],
        "db_id": data.get("trace_db_id"),
    }


def _get_trace_db_id(client: TestClient, project_id: str, trace_id: str) -> str:
    """Find the database UUID for an ingested trace via the detail endpoint.

    TraceSummary does not expose the database id, so we fetch the full trace
    detail and extract root_spans[0].id which is the Trace model's primary key.
    """
    response = client.get(f"/telemetry/traces/{trace_id}?project_id={project_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    root_spans = data.get("root_spans", [])
    assert root_spans, f"No root spans found for trace {trace_id}"
    db_id = root_spans[0].get("id")
    assert db_id, f"Root span missing 'id' field for trace {trace_id}"
    return db_id


@pytest.mark.integration
class TestAddTraceReview:
    """Test POST /telemetry/traces/{trace_db_id}/reviews"""

    def test_add_review_trace_target(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        review_payload = {
            "status_id": str(pass_status.id),
            "comments": "Trace looks correct",
            "target": {"type": "trace", "reference": None},
        }

        response = authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews", json=review_payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "review_id" in data
        assert data["status"]["name"] == "Pass"
        assert data["comments"] == "Trace looks correct"
        assert data["target"]["type"] == "trace"
        assert "created_at" in data
        assert "updated_at" in data
        assert "user" in data

    def test_add_review_metric_target(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        _, fail_status = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        review_payload = {
            "status_id": str(fail_status.id),
            "comments": "Metric override",
            "target": {"type": "metric", "reference": "faithfulness"},
        }

        response = authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews", json=review_payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["target"]["type"] == "metric"
        assert data["target"]["reference"] == "faithfulness"
        assert data["status"]["name"] == "Fail"

    def test_add_multiple_reviews(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, fail_status = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        first = authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "First review",
                "target": {"type": "trace", "reference": None},
            },
        )
        assert first.status_code == status.HTTP_200_OK

        second = authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": str(fail_status.id),
                "comments": "Second review",
                "target": {"type": "trace", "reference": None},
            },
        )
        assert second.status_code == status.HTTP_200_OK
        assert first.json()["review_id"] != second.json()["review_id"]

    def test_add_review_nonexistent_trace(
        self, authenticated_client: TestClient, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        fake_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/telemetry/traces/{fake_id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Should fail",
                "target": {"type": "trace", "reference": None},
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_review_invalid_status_id(
        self, authenticated_client: TestClient, db_project
    ):
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )
        fake_status_id = str(uuid.uuid4())

        response = authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": fake_status_id,
                "comments": "Bad status",
                "target": {"type": "trace", "reference": None},
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_review_persists_in_trace_detail(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Persistent review",
                "target": {"type": "trace", "reference": None},
            },
        )

        detail = authenticated_client.get(
            f"/telemetry/traces/{ingested['trace_id']}?project_id={db_project.id}"
        )
        assert detail.status_code == status.HTTP_200_OK
        detail_data = detail.json()
        assert detail_data.get("trace_reviews") is not None
        reviews = detail_data["trace_reviews"].get("reviews", [])
        assert len(reviews) >= 1
        assert reviews[-1]["comments"] == "Persistent review"

    def test_add_review_unauthenticated(self, client, db_project, pass_fail_statuses):
        pass_status, _ = pass_fail_statuses
        response = client.post(
            f"/telemetry/traces/{uuid.uuid4()}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "No auth",
                "target": {"type": "trace", "reference": None},
            },
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


@pytest.mark.integration
class TestUpdateTraceReview:
    """Test PUT /telemetry/traces/{trace_db_id}/reviews/{review_id}"""

    def _create_review(self, client, trace_db_id, status_id, comments="Review"):
        resp = client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": str(status_id),
                "comments": comments,
                "target": {"type": "trace", "reference": None},
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()

    def test_update_review_comments(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )
        review = self._create_review(
            authenticated_client, trace_db_id, pass_status.id
        )

        response = authenticated_client.put(
            f"/telemetry/traces/{trace_db_id}/reviews/{review['review_id']}",
            json={"comments": "Updated comments"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["comments"] == "Updated comments"
        assert data["review_id"] == review["review_id"]

    def test_update_review_status(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, fail_status = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )
        review = self._create_review(
            authenticated_client, trace_db_id, pass_status.id
        )

        response = authenticated_client.put(
            f"/telemetry/traces/{trace_db_id}/reviews/{review['review_id']}",
            json={"status_id": str(fail_status.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"]["name"] == "Fail"

    def test_update_review_target(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )
        review = self._create_review(
            authenticated_client, trace_db_id, pass_status.id
        )

        response = authenticated_client.put(
            f"/telemetry/traces/{trace_db_id}/reviews/{review['review_id']}",
            json={"target": {"type": "metric", "reference": "accuracy"}},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["target"]["type"] == "metric"
        assert response.json()["target"]["reference"] == "accuracy"

    def test_update_nonexistent_review(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )
        self._create_review(authenticated_client, trace_db_id, pass_status.id)

        response = authenticated_client.put(
            f"/telemetry/traces/{trace_db_id}/reviews/nonexistent-id",
            json={"comments": "Will not work"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_review_on_nonexistent_trace(
        self, authenticated_client: TestClient, pass_fail_statuses
    ):
        fake_id = str(uuid.uuid4())
        response = authenticated_client.put(
            f"/telemetry/traces/{fake_id}/reviews/some-review-id",
            json={"comments": "Nope"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestDeleteTraceReview:
    """Test DELETE /telemetry/traces/{trace_db_id}/reviews/{review_id}"""

    def _create_review(self, client, trace_db_id, status_id, comments="Review"):
        resp = client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": str(status_id),
                "comments": comments,
                "target": {"type": "trace", "reference": None},
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()

    def test_delete_review(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )
        review = self._create_review(
            authenticated_client, trace_db_id, pass_status.id
        )

        response = authenticated_client.delete(
            f"/telemetry/traces/{trace_db_id}/reviews/{review['review_id']}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Review deleted successfully"
        assert data["review_id"] == review["review_id"]

    def test_delete_review_clears_from_trace(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )
        review = self._create_review(
            authenticated_client, trace_db_id, pass_status.id
        )

        authenticated_client.delete(
            f"/telemetry/traces/{trace_db_id}/reviews/{review['review_id']}"
        )

        detail = authenticated_client.get(
            f"/telemetry/traces/{ingested['trace_id']}?project_id={db_project.id}"
        )
        assert detail.status_code == status.HTTP_200_OK
        reviews_data = detail.json().get("trace_reviews", {})
        remaining = reviews_data.get("reviews", [])
        review_ids = [r["review_id"] for r in remaining]
        assert review["review_id"] not in review_ids

    def test_delete_nonexistent_review(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )
        self._create_review(authenticated_client, trace_db_id, pass_status.id)

        response = authenticated_client.delete(
            f"/telemetry/traces/{trace_db_id}/reviews/does-not-exist"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_from_trace_with_no_reviews(
        self, authenticated_client: TestClient, db_project
    ):
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        response = authenticated_client.delete(
            f"/telemetry/traces/{trace_db_id}/reviews/any-id"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_on_nonexistent_trace(self, authenticated_client: TestClient):
        fake_id = str(uuid.uuid4())
        response = authenticated_client.delete(
            f"/telemetry/traces/{fake_id}/reviews/some-review-id"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_one_of_multiple_reviews(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, fail_status = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        review1 = self._create_review(
            authenticated_client, trace_db_id, pass_status.id, "Keep this"
        )
        review2 = self._create_review(
            authenticated_client, trace_db_id, fail_status.id, "Delete this"
        )

        authenticated_client.delete(
            f"/telemetry/traces/{trace_db_id}/reviews/{review2['review_id']}"
        )

        detail = authenticated_client.get(
            f"/telemetry/traces/{ingested['trace_id']}?project_id={db_project.id}"
        )
        reviews_data = detail.json().get("trace_reviews", {})
        remaining = reviews_data.get("reviews", [])
        assert len(remaining) >= 1
        remaining_ids = [r["review_id"] for r in remaining]
        assert review1["review_id"] in remaining_ids
        assert review2["review_id"] not in remaining_ids


@pytest.mark.integration
class TestTraceReviewMetadata:
    """Test that review metadata is correctly updated on trace reviews."""

    def test_metadata_updated_on_add(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Meta test",
                "target": {"type": "trace", "reference": None},
            },
        )

        detail = authenticated_client.get(
            f"/telemetry/traces/{ingested['trace_id']}?project_id={db_project.id}"
        )
        metadata = detail.json()["trace_reviews"]["metadata"]
        assert metadata["total_reviews"] == 1
        assert "last_updated_at" in metadata
        assert "last_updated_by" in metadata
        assert metadata["latest_status"]["name"] == "Pass"

    def test_metadata_total_reviews_increments(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, fail_status = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        for i, sid in enumerate([pass_status.id, fail_status.id, pass_status.id]):
            authenticated_client.post(
                f"/telemetry/traces/{trace_db_id}/reviews",
                json={
                    "status_id": str(sid),
                    "comments": f"Review #{i+1}",
                    "target": {"type": "trace", "reference": None},
                },
            )

        detail = authenticated_client.get(
            f"/telemetry/traces/{ingested['trace_id']}?project_id={db_project.id}"
        )
        metadata = detail.json()["trace_reviews"]["metadata"]
        assert metadata["total_reviews"] == 3

    def test_metadata_zeroed_after_all_deleted(
        self, authenticated_client: TestClient, db_project, pass_fail_statuses
    ):
        pass_status, _ = pass_fail_statuses
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        review = authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": str(pass_status.id),
                "comments": "Will be deleted",
                "target": {"type": "trace", "reference": None},
            },
        ).json()

        authenticated_client.delete(
            f"/telemetry/traces/{trace_db_id}/reviews/{review['review_id']}"
        )

        detail = authenticated_client.get(
            f"/telemetry/traces/{ingested['trace_id']}?project_id={db_project.id}"
        )
        metadata = detail.json()["trace_reviews"]["metadata"]
        assert metadata["total_reviews"] == 0
        assert metadata["latest_status"] is None
        assert "All reviews removed" in metadata["summary"]
