"""Tests for GET /annotations — flattened review list."""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.models.status import Status
from rhesis.backend.app.models.test_result import TestResult
from tests.backend.routes.fixtures.data_factories import TraceDataFactory


def _ensure_pass_fail_statuses(test_db, test_organization, test_type_lookup, db_user):
    pass_status = (
        test_db.query(Status)
        .filter(
            Status.name == "Pass",
            Status.organization_id == test_organization.id,
        )
        .first()
    )
    fail_status = (
        test_db.query(Status)
        .filter(
            Status.name == "Fail",
            Status.organization_id == test_organization.id,
        )
        .first()
    )
    if pass_status and fail_status:
        return pass_status, fail_status

    if not pass_status:
        pass_status = Status(
            name="Pass",
            description="Passed evaluation",
            entity_type_id=test_type_lookup.id,
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(pass_status)
    if not fail_status:
        fail_status = Status(
            name="Fail",
            description="Failed evaluation",
            entity_type_id=test_type_lookup.id,
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(fail_status)
    test_db.commit()
    test_db.refresh(pass_status)
    test_db.refresh(fail_status)
    return pass_status, fail_status


def _review_payload(status_id, user_id, user_name="Test User", target_type="test_result"):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "review_id": str(uuid.uuid4()),
        "status": {"status_id": str(status_id), "name": "Pass"},
        "user": {"user_id": str(user_id), "name": user_name},
        "comments": "Looks good after human review.",
        "created_at": now,
        "updated_at": now,
        "target": {"type": target_type, "reference": None},
    }


@pytest.mark.integration
class TestListAnnotations:
    def test_list_empty(self, authenticated_client: TestClient):
        response = authenticated_client.get("/annotations/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        assert response.headers.get("X-Total-Count") == "0"

    def test_list_test_result_and_trace_reviews(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )

        # Seed a test result with a review
        review = _review_payload(pass_status.id, authenticated_user.id)
        test_result = TestResult(
            organization_id=test_organization.id,
            user_id=authenticated_user.id,
            project_id=db_project.id,
            test_reviews={
                "metadata": {"total_reviews": 1},
                "reviews": [review],
            },
        )
        test_db.add(test_result)
        test_db.commit()
        test_db.refresh(test_result)

        # Seed a trace with a review via ingest + direct JSONB update
        span_data = TraceDataFactory.sample_data(project_id=str(db_project.id))
        ingest = authenticated_client.post(
            "/telemetry/traces",
            json={"spans": [span_data]},
        )
        assert ingest.status_code == status.HTTP_200_OK

        detail = authenticated_client.get(
            f"/telemetry/traces/{span_data['trace_id']}?project_id={db_project.id}"
        )
        assert detail.status_code == status.HTTP_200_OK
        root = detail.json()["root_spans"][0]
        trace_db_id = root["id"]

        from sqlalchemy.orm.attributes import flag_modified

        from rhesis.backend.app.models.trace import Trace

        trace = test_db.query(Trace).filter(Trace.id == uuid.UUID(trace_db_id)).first()
        assert trace is not None
        trace_review = _review_payload(pass_status.id, authenticated_user.id, target_type="trace")
        trace.trace_reviews = {
            "metadata": {"total_reviews": 1},
            "reviews": [trace_review],
        }
        flag_modified(trace, "trace_reviews")
        test_db.commit()

        response = authenticated_client.get("/annotations/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 2
        assert int(response.headers.get("X-Total-Count", "0")) >= 2

        sources = {item["source"] for item in data}
        assert "test_result" in sources
        assert "trace" in sources

        tr_item = next(i for i in data if i["review_id"] == review["review_id"])
        assert tr_item["test_result_id"] == str(test_result.id)
        assert tr_item["status"]["name"] == "Pass"

        filter_tr = authenticated_client.get("/annotations/?source=test_result")
        assert filter_tr.status_code == status.HTTP_200_OK
        assert all(i["source"] == "test_result" for i in filter_tr.json())

        filter_trace = authenticated_client.get("/annotations/?source=trace")
        assert filter_trace.status_code == status.HTTP_200_OK
        assert all(i["source"] == "trace" for i in filter_trace.json())

    def test_list_includes_resolved_flag(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        review = _review_payload(pass_status.id, authenticated_user.id)
        review["resolved"] = True
        review["resolved_at"] = review["updated_at"]
        test_result = TestResult(
            organization_id=test_organization.id,
            user_id=authenticated_user.id,
            project_id=db_project.id,
            test_reviews={
                "metadata": {"total_reviews": 1},
                "reviews": [review],
            },
        )
        test_db.add(test_result)
        test_db.commit()

        response = authenticated_client.get("/annotations/?source=test_result")
        assert response.status_code == status.HTTP_200_OK
        item = next(i for i in response.json() if i["review_id"] == review["review_id"])
        assert item["resolved"] is True

    def test_search_and_filters(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        pass_status, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        open_review = _review_payload(pass_status.id, authenticated_user.id)
        open_review["comments"] = "unique-open-annotation-marker"
        resolved_review = _review_payload(fail_status.id, authenticated_user.id)
        resolved_review["comments"] = "unique-resolved-annotation-marker"
        resolved_review["resolved"] = True
        resolved_review["status"] = {
            "status_id": str(fail_status.id),
            "name": "Fail",
        }

        test_result = TestResult(
            organization_id=test_organization.id,
            user_id=authenticated_user.id,
            project_id=db_project.id,
            test_reviews={
                "metadata": {"total_reviews": 2},
                "reviews": [open_review, resolved_review],
            },
        )
        test_db.add(test_result)
        test_db.commit()

        search = authenticated_client.get("/annotations/?search=unique-open-annotation-marker")
        assert search.status_code == status.HTTP_200_OK
        search_ids = {i["review_id"] for i in search.json()}
        assert open_review["review_id"] in search_ids
        assert resolved_review["review_id"] not in search_ids

        resolved = authenticated_client.get("/annotations/?resolved=true")
        assert resolved.status_code == status.HTTP_200_OK
        resolved_ids = {i["review_id"] for i in resolved.json()}
        assert resolved_review["review_id"] in resolved_ids
        assert open_review["review_id"] not in resolved_ids

        failed = authenticated_client.get("/annotations/?rating=Fail")
        assert failed.status_code == status.HTTP_200_OK
        fail_ids = {i["review_id"] for i in failed.json()}
        assert resolved_review["review_id"] in fail_ids
        assert open_review["review_id"] not in fail_ids
