"""The jobs API the Jobs screen reads.

Covers list/detail/activity/cancel plus the tenant boundary on each. The
cross-org cases matter more than usual here: a job row names what an
organization is doing and when, which is exactly the sort of thing that must
not leak.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/routes/test_jobs_api.py -v
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.enums import JobStatus
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _make_job(
    db: Session,
    org,
    user,
    *,
    status: JobStatus = JobStatus.RUNNING,
    job_type: str = "generate_and_save_test_set",
    celery_task_id: str | None = None,
) -> models.Job:
    job = models.Job(
        organization_id=org.id,
        user_id=user.id,
        celery_task_id=celery_task_id or str(uuid.uuid4()),
        job_type=job_type,
        name="Generate and Save Test Set",
        status=status.value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _make_entry(db: Session, org, job, *, sequence: int, message: str, level: str = "info"):
    entry = models.ActivityLog(
        organization_id=org.id,
        job_id=job.id,
        sequence=sequence,
        level=level,
        message=message,
        source=job.job_type,
    )
    db.add(entry)
    db.commit()
    return entry


class TestListJobs:
    def test_returns_own_jobs_with_count_header(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Jobs API Org", "list@jobs-api.com", "List User"
        )
        _make_job(test_db, org, user)

        response = client.get("/jobs/", headers=_auth(token))

        assert response.status_code == 200
        assert response.headers.get("X-Total-Count") is not None
        body = response.json()
        assert len(body) == 1
        assert body[0]["job_type"] == "generate_and_save_test_set"

    def test_does_not_leak_other_organizations_jobs(self, client: TestClient, test_db: Session):
        org_a, user_a, _ = create_test_organization_and_user(
            test_db, "Jobs API Org A", "lista@jobs-api.com", "User A"
        )
        _make_job(test_db, org_a, user_a)
        _, _, token_b = create_test_organization_and_user(
            test_db, "Jobs API Org B", "listb@jobs-api.com", "User B"
        )

        response = client.get("/jobs/", headers=_auth(token_b))

        assert response.status_code == 200
        assert response.json() == []

    def test_serves_derived_state_flags(self, client: TestClient, test_db: Session):
        """is_terminal/cancellable are computed server-side so the client does
        not keep its own copy of which statuses are final."""
        org, user, token = create_test_organization_and_user(
            test_db, "Jobs API Org Flags", "flags@jobs-api.com", "Flags User"
        )
        _make_job(test_db, org, user, status=JobStatus.COMPLETED)

        body = client.get("/jobs/", headers=_auth(token)).json()

        assert body[0]["is_terminal"] is True
        assert body[0]["cancellable"] is False


class TestJobDetail:
    def test_returns_the_job(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Jobs API Org Detail", "detail@jobs-api.com", "Detail User"
        )
        job = _make_job(test_db, org, user)

        response = client.get(f"/jobs/detail/{job.id}", headers=_auth(token))

        assert response.status_code == 200
        assert response.json()["id"] == str(job.id)
        assert response.json()["cancellable"] is True

    def test_other_organization_gets_404(self, client: TestClient, test_db: Session):
        org_a, user_a, _ = create_test_organization_and_user(
            test_db, "Jobs API Org DA", "da@jobs-api.com", "User A"
        )
        job = _make_job(test_db, org_a, user_a)
        _, _, token_b = create_test_organization_and_user(
            test_db, "Jobs API Org DB", "db@jobs-api.com", "User B"
        )

        response = client.get(f"/jobs/detail/{job.id}", headers=_auth(token_b))

        assert response.status_code == 404


class TestJobActivity:
    def test_returns_entries_in_sequence_order(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Jobs API Org Act", "act@jobs-api.com", "Act User"
        )
        job = _make_job(test_db, org, user)
        # Inserted out of order on purpose: ordering must come from sequence,
        # not from insertion or created_at, which ties under fast writes.
        _make_entry(test_db, org, job, sequence=2, message="second")
        _make_entry(test_db, org, job, sequence=1, message="first")

        body = client.get(f"/jobs/detail/{job.id}/activity", headers=_auth(token)).json()

        assert [e["message"] for e in body["entries"]] == ["first", "second"]
        assert body["next_after_sequence"] == 2

    def test_cursor_returns_only_later_entries(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Jobs API Org Cursor", "cursor@jobs-api.com", "Cursor User"
        )
        job = _make_job(test_db, org, user)
        _make_entry(test_db, org, job, sequence=1, message="first")
        _make_entry(test_db, org, job, sequence=2, message="second")

        body = client.get(
            f"/jobs/detail/{job.id}/activity?after_sequence=1", headers=_auth(token)
        ).json()

        assert [e["message"] for e in body["entries"]] == ["second"]

    def test_empty_page_keeps_the_cursor(self, client: TestClient, test_db: Session):
        """A poll that finds nothing new must not rewind to the start."""
        org, user, token = create_test_organization_and_user(
            test_db, "Jobs API Org Empty", "empty@jobs-api.com", "Empty User"
        )
        job = _make_job(test_db, org, user)
        _make_entry(test_db, org, job, sequence=1, message="first")

        body = client.get(
            f"/jobs/detail/{job.id}/activity?after_sequence=1", headers=_auth(token)
        ).json()

        assert body["entries"] == []
        assert body["next_after_sequence"] == 1

    def test_other_organization_cannot_read_activity(self, client: TestClient, test_db: Session):
        org_a, user_a, _ = create_test_organization_and_user(
            test_db, "Jobs API Org AA", "aa@jobs-api.com", "User A"
        )
        job = _make_job(test_db, org_a, user_a)
        _make_entry(test_db, org_a, job, sequence=1, message="secret")
        _, _, token_b = create_test_organization_and_user(
            test_db, "Jobs API Org AB", "ab@jobs-api.com", "User B"
        )

        response = client.get(f"/jobs/detail/{job.id}/activity", headers=_auth(token_b))

        assert response.status_code == 404


class TestCancelJob:
    def test_moves_a_running_job_to_cancelling(self, client: TestClient, test_db: Session):
        """Not 'cancelled': the job has been asked, not stopped."""
        org, user, token = create_test_organization_and_user(
            test_db, "Jobs API Org Cancel", "cancel@jobs-api.com", "Cancel User"
        )
        job = _make_job(test_db, org, user, status=JobStatus.RUNNING)

        response = client.post(f"/jobs/detail/{job.id}/cancel", headers=_auth(token))

        assert response.status_code == 200
        assert response.json()["status"] == JobStatus.CANCELLING.value

    @pytest.mark.parametrize(
        "status", [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
    )
    def test_terminal_job_cannot_be_cancelled(
        self, client: TestClient, test_db: Session, status
    ):
        org, user, token = create_test_organization_and_user(
            test_db,
            f"Jobs API Org Term {status.value}",
            f"term-{status.value}@jobs-api.com",
            "Term User",
        )
        job = _make_job(test_db, org, user, status=status)

        response = client.post(f"/jobs/detail/{job.id}/cancel", headers=_auth(token))

        assert response.status_code == 409

    def test_other_organization_cannot_cancel(self, client: TestClient, test_db: Session):
        org_a, user_a, _ = create_test_organization_and_user(
            test_db, "Jobs API Org CA", "ca@jobs-api.com", "User A"
        )
        job = _make_job(test_db, org_a, user_a)
        _, _, token_b = create_test_organization_and_user(
            test_db, "Jobs API Org CB", "cb@jobs-api.com", "User B"
        )

        response = client.post(f"/jobs/detail/{job.id}/cancel", headers=_auth(token_b))

        assert response.status_code == 404
        test_db.refresh(job)
        assert job.status == JobStatus.RUNNING.value


class TestCeleryIdLookup:
    def test_owner_can_read_status_for_any_job_type(self, client: TestClient, test_db: Session):
        """The indexed lookup covers types the old TestRun-based stopgap could not."""
        org, user, token = create_test_organization_and_user(
            test_db, "Jobs API Org Garak", "garak@jobs-api.com", "Garak User"
        )
        celery_task_id = str(uuid.uuid4())
        _make_job(
            test_db,
            org,
            user,
            job_type="import_garak_probes",
            celery_task_id=celery_task_id,
        )

        response = client.get(f"/jobs/by-celery-id/{celery_task_id}", headers=_auth(token))

        assert response.status_code == 200
        assert response.json()["task_id"] == celery_task_id

    def test_other_organization_gets_404(self, client: TestClient, test_db: Session):
        org_a, user_a, _ = create_test_organization_and_user(
            test_db, "Jobs API Org KA", "ka@jobs-api.com", "User A"
        )
        celery_task_id = str(uuid.uuid4())
        _make_job(test_db, org_a, user_a, celery_task_id=celery_task_id)
        _, _, token_b = create_test_organization_and_user(
            test_db, "Jobs API Org KB", "kb@jobs-api.com", "User B"
        )

        response = client.get(f"/jobs/by-celery-id/{celery_task_id}", headers=_auth(token_b))

        assert response.status_code == 404

    def test_deprecated_alias_still_enforces_the_check(self, client: TestClient, test_db: Session):
        """Both halves matter.

        Asserting only the cross-org 404 would also pass if the alias denied
        everyone, which is how this endpoint behaved on an earlier attempt.
        """
        org_a, user_a, token_a = create_test_organization_and_user(
            test_db, "Jobs API Org LA", "la@jobs-api.com", "User A"
        )
        celery_task_id = str(uuid.uuid4())
        _make_job(test_db, org_a, user_a, celery_task_id=celery_task_id)
        _, _, token_b = create_test_organization_and_user(
            test_db, "Jobs API Org LB", "lb@jobs-api.com", "User B"
        )

        assert client.get(f"/jobs/{celery_task_id}", headers=_auth(token_a)).status_code == 200
        assert client.get(f"/jobs/{celery_task_id}", headers=_auth(token_b)).status_code == 404

    def test_unknown_celery_id_is_404(self, client: TestClient, test_db: Session):
        _, _, token = create_test_organization_and_user(
            test_db, "Jobs API Org Unknown", "unknown@jobs-api.com", "Unknown User"
        )

        response = client.get(f"/jobs/by-celery-id/{uuid.uuid4()}", headers=_auth(token))

        assert response.status_code == 404

    def test_by_celery_id_is_not_shadowed_by_the_alias(self, client: TestClient, test_db: Session):
        """Pins declaration order of the two GET routes.

        ``/jobs/{task_id}`` would match ``by-celery-id`` as a path segment and
        reject it as a malformed UUID (422). It does not only because the more
        specific route is declared first, which nothing else would catch if
        someone reordered them.
        """
        _, _, token = create_test_organization_and_user(
            test_db, "Jobs API Org Order", "order@jobs-api.com", "Order User"
        )

        response = client.get(f"/jobs/by-celery-id/{uuid.uuid4()}", headers=_auth(token))

        assert response.status_code == 404

    def test_alias_is_marked_deprecated_in_openapi(self, client: TestClient):
        schema = client.get("/openapi.json").json()
        assert schema["paths"]["/jobs/{task_id}"]["get"].get("deprecated") is True
