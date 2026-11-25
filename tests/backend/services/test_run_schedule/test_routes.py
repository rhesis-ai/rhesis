"""The /test_run_schedules API: shapes, statuses, permissions and the runs list Source filter."""

import contextlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from rhesis.backend.app import models
from rhesis.backend.app.auth.rbac import (
    AuthorizationProvider,
    get_authorization_provider,
    set_authorization_provider,
)
from rhesis.backend.app.utils.crud_utils import get_or_create_status

BASE = "/test_run_schedules"


@pytest.fixture
def body(schedule_test_set, schedule_endpoint):
    return {
        "test_set_id": str(schedule_test_set.id),
        "endpoint_id": str(schedule_endpoint.id),
        "schedule": {"name": "Daily", "cron": "0 9 * * *", "timezone": "UTC"},
    }


@pytest.fixture
def created(authenticated_client, body):
    response = authenticated_client.post(f"{BASE}/", json=body)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()[0]


class _Denying(AuthorizationProvider):
    """The real provider, minus the capabilities in ``denied``."""

    def __init__(self, inner, denied):
        self.inner, self.denied = inner, {str(d) for d in denied}

    def is_authorized(self, principal, permission, *, project_id, db):
        if str(permission) in self.denied:
            return False
        return self.inner.is_authorized(principal, permission, project_id=project_id, db=db)


@contextlib.contextmanager
def _denied(*capabilities):
    from rhesis.backend.app.services.permission_cache import get_permission_cache

    # Decisions made while creating the fixture are cached and would answer first.
    get_permission_cache().clear_all()
    previous = get_authorization_provider()
    set_authorization_provider(_Denying(previous, capabilities))
    try:
        yield
    finally:
        set_authorization_provider(previous)


class TestCreateAndRead:
    def test_create_returns_the_schedule_in_plain_words(self, created):
        assert created["status"] == "Scheduled"
        assert created["repeats"] == "Every day at 09:00"
        assert created["overdue"] is False
        assert created["test_set"]["name"] == "Weekday regression set"
        assert created["endpoint"]["connection_type"] == "rest"
        assert "test_run:update" in created["permitted_actions"]

    def test_validation_errors_are_readable(self, authenticated_client, body):
        body["schedule"]["cron"] = "* * * * *"
        response = authenticated_client.post(f"{BASE}/", json=body)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_and_filter_by_test_set(self, authenticated_client, created, schedule_test_set):
        listed = authenticated_client.get(
            f"{BASE}/", params={"test_set_id": str(schedule_test_set.id)}
        ).json()
        assert [item["id"] for item in listed] == [created["id"]]
        paused = authenticated_client.get(f"{BASE}/", params={"status": "Paused"}).json()
        assert paused == []

    def test_detail_has_upcoming_usage_and_settings(self, authenticated_client, created):
        detail = authenticated_client.get(f"{BASE}/{created['id']}").json()
        assert len(detail["upcoming"]) == 5
        assert detail["usage"]["run_count"] == 0
        assert detail["usage"]["expected_month_usd"] is None
        assert detail["run_settings"]["execution_mode"] == "Parallel"
        assert detail["recent_runs"] == []

    def test_unknown_schedule_is_404(self, authenticated_client):
        response = authenticated_client.get(f"{BASE}/00000000-0000-4000-8000-000000000000")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_overdue_only_after_the_margin(self, authenticated_client, test_db, created):
        config = test_db.get(models.TestConfiguration, created["id"])

        def _set_next(minutes_ago):
            schedule = dict(config.attributes["schedule"])
            at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            schedule["next_run_at"] = at.isoformat()
            config.attributes = {**config.attributes, "schedule": schedule}
            test_db.commit()
            return authenticated_client.get(f"{BASE}/{created['id']}").json()["overdue"]

        assert _set_next(1) is False
        assert _set_next(3) is True


class TestPreviewAndWindow:
    def test_preview(self, authenticated_client):
        response = authenticated_client.post(
            f"{BASE}/preview", json={"cron": "0 9 * * 1-5", "timezone": "Europe/Berlin"}
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["repeats"] == "Every weekday at 09:00"
        assert len(response.json()["next"]) == 3

    def test_preview_explains_the_minimum(self, authenticated_client):
        response = authenticated_client.post(f"{BASE}/preview", json={"cron": "*/5 * * * *"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()["detail"] == "Schedules can run at most once every 60 minutes."

    def test_occurrences_window(self, authenticated_client, created, body):
        body["schedule"] = {"name": "Hourly", "cron": "0 * * * *"}
        authenticated_client.post(f"{BASE}/", json=body)
        now = datetime.now(timezone.utc)
        response = authenticated_client.get(
            f"{BASE}/occurrences",
            params={"from": now.isoformat(), "to": (now + timedelta(days=7)).isoformat()},
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert len(data["items"]) == 7
        assert {item["name"] for item in data["items"]} == {"Daily"}
        assert [h["name"] for h in data["hourly"]] == ["Hourly"]

    def test_occurrences_window_is_capped(self, authenticated_client):
        now = datetime.now(timezone.utc)
        response = authenticated_client.get(
            f"{BASE}/occurrences",
            params={"from": now.isoformat(), "to": (now + timedelta(days=60)).isoformat()},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_occurrences_need_an_offset(self, authenticated_client):
        response = authenticated_client.get(
            f"{BASE}/occurrences",
            params={"from": "2030-01-01T00:00:00", "to": "2030-01-10T00:00:00"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_occurrences_stop_at_max_runs(self, authenticated_client, body):
        body["schedule"] = {"name": "Three times", "cron": "0 9 * * *", "max_runs": 3}
        authenticated_client.post(f"{BASE}/", json=body)
        now = datetime.now(timezone.utc)
        response = authenticated_client.get(
            f"{BASE}/occurrences",
            params={"from": now.isoformat(), "to": (now + timedelta(days=14)).isoformat()},
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        names = [item["name"] for item in response.json()["items"]]
        assert names.count("Three times") == 3

    def test_patch_with_an_unknown_endpoint_is_422(self, authenticated_client, created):
        response = authenticated_client.patch(
            f"{BASE}/{created['id']}", json={"endpoint_id": str(uuid.uuid4())}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestChanges:
    def test_patch_pause_resume_skip_delete(self, authenticated_client, created):
        url = f"{BASE}/{created['id']}"
        assert authenticated_client.patch(url, json={"name": "Renamed"}).json()["name"] == "Renamed"
        assert authenticated_client.post(f"{url}/pause").json()["status"] == "Paused"
        assert authenticated_client.post(f"{url}/resume").json()["status"] == "Scheduled"
        skipped = authenticated_client.post(f"{url}/skip_next").json()
        assert skipped["next_run_at"] != created["next_run_at"]
        assert authenticated_client.delete(url).status_code == status.HTTP_200_OK
        assert authenticated_client.get(url).status_code == status.HTTP_404_NOT_FOUND

    def test_edit_and_delete_one_occurrence(self, authenticated_client, created):
        url = f"{BASE}/{created['id']}/occurrences/{created['next_run_at']}"
        moved = datetime.fromisoformat(created["next_run_at"]) + timedelta(hours=2)
        response = authenticated_client.patch(
            url, params={"scope": "one"}, json={"move_to": moved.isoformat()}
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert datetime.fromisoformat(response.json()["next_run_at"]) == moved

        refused = authenticated_client.patch(
            url, params={"scope": "one"}, json={"name": "Not for one run"}
        )
        assert refused.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        deleted = authenticated_client.delete(url, params={"scope": "one"})
        assert deleted.status_code == status.HTTP_200_OK, deleted.text

    def test_a_stale_occurrence_is_a_conflict(self, authenticated_client, created):
        response = authenticated_client.delete(
            f"{BASE}/{created['id']}/occurrences/2020-01-01T09:00:00+00:00"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_resume_after_creator_lost_access_is_refused(
        self, authenticated_client, test_db, created
    ):
        from rhesis.backend.app.services.test_run_schedule import service

        config = service.load_schedule(test_db, created["id"])
        service.pause(test_db, config, reason=service.CREATOR_ACCESS)
        test_db.commit()
        response = authenticated_client.post(f"{BASE}/{created['id']}/resume")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Take it over" in response.json()["detail"]

    def test_take_over(self, authenticated_client, test_db, created):
        from rhesis.backend.app.services.test_run_schedule import service

        config = service.load_schedule(test_db, created["id"])
        service.pause(test_db, config, reason=service.CREATOR_ACCESS)
        test_db.commit()
        with patch("rhesis.backend.jobs.execution.run.plan_run_for_user"):
            response = authenticated_client.post(f"{BASE}/{created['id']}/take_over")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["status"] == "Scheduled"

    def test_run_now_and_the_runs_source_filter(self, authenticated_client, created):
        with (
            patch("rhesis.backend.jobs.execution.run.plan_run_for_user", return_value=None),
            patch("rhesis.backend.jobs.launch_job", return_value=MagicMock(id="task-1")),
        ):
            response = authenticated_client.post(f"{BASE}/{created['id']}/run_now")
        assert response.status_code == status.HTTP_200_OK, response.text

        manual = authenticated_client.get("/test_runs/", params={"trigger": "manual"})
        from_schedule = authenticated_client.get("/test_runs/", params={"trigger": "schedule"})
        run_id = response.json()["test_run_id"]
        assert run_id in [r["id"] for r in manual.json()]
        assert from_schedule.json() == []
        assert from_schedule.headers["X-Total-Count"] == "0"
        run = next(r for r in manual.json() if r["id"] == run_id)
        assert run["test_configuration"]["attributes"]["schedule"]["name"] == "Daily"


class TestPermissions:
    @pytest.mark.parametrize(
        ("method", "suffix", "capability"),
        [
            ("patch", "", "test_run:update"),
            ("post", "/pause", "test_run:update"),
            ("post", "/take_over", "test_run:update"),
            ("delete", "", "test_run:delete"),
            ("post", "/run_now", "test_run:execute"),
            ("get", "", "test_run:read"),
        ],
    )
    def test_each_route_needs_its_capability(
        self, authenticated_client, created, method, suffix, capability
    ):
        with _denied(capability):
            kwargs = {"json": {"name": "x"}} if method == "patch" else {}
            response = getattr(authenticated_client, method)(
                f"{BASE}/{created['id']}{suffix}", **kwargs
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_needs_execute(self, authenticated_client, body):
        with _denied("test_run:execute"):
            response = authenticated_client.post(f"{BASE}/", json=body)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_take_over_also_needs_execute(self, authenticated_client, created):
        with _denied("test_run:execute"):
            response = authenticated_client.post(f"{BASE}/{created['id']}/take_over")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_permitted_actions_follow_the_caller(self, authenticated_client, created):
        with _denied("test_run:update"):
            item = authenticated_client.get(f"{BASE}/{created['id']}").json()
        assert "test_run:update" not in item["permitted_actions"]


def test_usage_and_recent_runs(authenticated_client, test_db, created):
    config = test_db.get(models.TestConfiguration, created["id"])
    completed = get_or_create_status(
        test_db, "Completed", "TestRun", organization_id=str(config.organization_id), commit=False
    )
    for _ in range(3):
        test_db.add(
            models.TestRun(
                test_configuration_id=config.id,
                organization_id=config.organization_id,
                user_id=config.user_id,
                project_id=config.project_id,
                status_id=completed.id,
                name="bright-otter",
                attributes={"trigger": "schedule"},
            )
        )
    test_db.commit()
    detail = authenticated_client.get(f"{BASE}/{created['id']}").json()
    assert detail["usage"]["run_count"] == 3
    assert detail["usage"]["expected_month_usd"] == 0
    assert [r["name"] for r in detail["recent_runs"]] == ["bright-otter"] * 3
    assert detail["last_run"]["status"] == "Completed"
