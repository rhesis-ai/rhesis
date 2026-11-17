"""Reports: draft with live numbers, publish frozen, copy, export, and the section seam.

Run with: cd apps/backend && uv run pytest ../../tests/backend/routes/test_report.py -v
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.services.report.sections import (
    ReportSection,
    get_report_sections,
    register_report_section,
    reset_report_sections,
)


class _Builder:
    """Requirements, tests, runs and results for one endpoint."""

    def __init__(self, db: Session, org_id, user_id, status_id, test_configuration):
        self.db = db
        self.org_id = org_id
        self.user_id = user_id
        self.status_id = status_id
        self.config = test_configuration
        self._runs = 0

    def _add(self, obj):
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def requirement(self, name: str, parent=None) -> models.Requirement:
        return self._add(
            models.Requirement(
                name=f"{name} {uuid.uuid4().hex[:6]}",
                organization_id=self.org_id,
                user_id=self.user_id,
                parent_id=parent.id if parent else None,
            )
        )

    def test(self, requirement=None) -> models.Test:
        return self._add(
            models.Test(
                organization_id=self.org_id,
                user_id=self.user_id,
                status_id=self.status_id,
                requirement_id=requirement.id if requirement else None,
            )
        )

    def run(self, config=None, version=None) -> models.TestRun:
        attributes = {"version_info": version} if version else {}
        # One transaction stamps every row with the same now(); space the runs out.
        self._runs += 1
        return self._add(
            models.TestRun(
                name=f"Run {uuid.uuid4().hex[:6]}",
                organization_id=self.org_id,
                user_id=self.user_id,
                status_id=self.status_id,
                test_configuration_id=(config or self.config).id,
                attributes=attributes,
                created_at=datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(hours=self._runs),
            )
        )

    def result(self, run, test, verdict="pass", execution="ok") -> models.TestResult:
        return self._add(
            models.TestResult(
                organization_id=self.org_id,
                user_id=self.user_id,
                test_run_id=run.id,
                test_id=test.id,
                test_configuration_id=run.test_configuration_id,
                execution=execution,
                verdict=verdict if execution == "ok" else None,
            )
        )

    def commit(self):
        self.db.commit()


@pytest.fixture
def build(test_db, test_org_id, authenticated_user_id, db_status, db_test_configuration):
    return _Builder(
        test_db, test_org_id, authenticated_user_id, db_status.id, db_test_configuration
    )


def _create(client: TestClient, endpoint_id, runs=(), requirements=(), **body) -> dict:
    payload = {
        "title": body.pop("title", "Release 2.4"),
        "endpoint_id": str(endpoint_id),
        "test_run_ids": [str(r.id) for r in runs],
        "requirement_ids": [str(r.id) for r in requirements],
        **body,
    }
    response = client.post("/reports/", json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _detail(client: TestClient, report_id) -> dict:
    response = client.get(f"/reports/{report_id}")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _rows_by_name(detail: dict) -> dict:
    return {row["name"]: row for row in detail["metrics"]["requirements"]}


@pytest.mark.integration
class TestReportDraft:
    def test_draft_shows_live_tree_and_totals(
        self, authenticated_client, build, db_endpoint, section_registry
    ):
        parent = build.requirement("Compliance")
        advice = build.requirement("No advice", parent=parent)
        handoff = build.requirement("Handoff")
        untested = build.requirement("Plain language")
        idle = build.requirement("Language")
        idle_test = build.test(idle)  # has a test, but not in the run
        run = build.run()
        for verdict in ("pass", "pass", "fail"):
            build.result(run, build.test(advice), verdict)
        build.result(run, build.test(handoff), "fail")
        build.result(run, build.test(handoff), execution="error")
        build.commit()
        assert idle_test.id

        report = _create(
            authenticated_client,
            db_endpoint.id,
            runs=[run],
            requirements=[parent, advice, handoff, untested, idle],
        )
        assert report["status"] == "draft"

        detail = _detail(authenticated_client, report["id"])
        totals = detail["metrics"]["totals"]
        assert (totals["results"], totals["passed"], totals["failed"], totals["errored"]) == (
            5,
            2,
            2,
            1,
        )
        assert totals["pass_rate"] == 50.0

        rows = _rows_by_name(detail)
        assert rows[parent.name]["level"] == 0
        assert rows[advice.name]["level"] == 1
        assert rows[parent.name]["tests"] == 3  # adds up its child
        assert rows[advice.name]["pass_rate"] == pytest.approx(66.67)
        assert rows[handoff.name]["pass_rate"] == 0.0
        assert rows[untested.name]["coverage"] == "no_tests"
        assert rows[idle.name]["coverage"] == "not_in_runs"
        names = [row["name"] for row in detail["metrics"]["requirements"]]
        assert names.index(advice.name) == names.index(parent.name) + 1
        assert detail["sections"] == {}

    def test_latest_result_counts(self, authenticated_client, build, db_endpoint):
        requirement = build.requirement("Flaky")
        test = build.test(requirement)
        first, second = build.run(), build.run()
        build.result(first, test, "fail")
        build.result(second, test, "pass")
        build.commit()

        report = _create(
            authenticated_client, db_endpoint.id, runs=[first, second], requirements=[requirement]
        )
        totals = _detail(authenticated_client, report["id"])["metrics"]["totals"]
        assert (totals["results"], totals["passed"], totals["failed"]) == (1, 1, 0)

    def test_versions_differ_is_flagged(self, authenticated_client, build, db_endpoint):
        test = build.test()
        old, new = build.run(version={"prompt": "v2.3"}), build.run(version={"prompt": "v2.4"})
        build.result(old, test)
        build.result(new, build.test())
        build.commit()

        report = _create(authenticated_client, db_endpoint.id, runs=[old, new])
        metrics = _detail(authenticated_client, report["id"])["metrics"]
        assert metrics["versions_differ"] is True
        assert {r["version_info"]["prompt"] for r in metrics["runs"]} == {"v2.3", "v2.4"}

    def test_runs_of_another_endpoint_are_refused(
        self, authenticated_client, build, test_db, db_endpoint, db_test_configuration
    ):
        other_endpoint = models.Endpoint(
            name=f"Other {uuid.uuid4().hex[:6]}",
            connection_type=db_endpoint.connection_type,
            environment=db_endpoint.environment,
            project_id=db_endpoint.project_id,
            organization_id=db_endpoint.organization_id,
            user_id=db_endpoint.user_id,
        )
        test_db.add(other_endpoint)
        test_db.flush()
        other_config = models.TestConfiguration(
            endpoint_id=other_endpoint.id,
            organization_id=db_test_configuration.organization_id,
            user_id=db_test_configuration.user_id,
        )
        test_db.add(other_config)
        test_db.flush()
        run = build.run(config=other_config)
        build.commit()

        response = authenticated_client.post(
            "/reports/",
            json={
                "title": "Mixed",
                "endpoint_id": str(db_endpoint.id),
                "test_run_ids": [str(run.id)],
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "different endpoint" in response.json()["detail"]

    def test_update_keeps_the_author(self, authenticated_client, build, db_endpoint):
        report = _create(authenticated_client, db_endpoint.id)
        response = authenticated_client.put(
            f"/reports/{report['id']}",
            json={"summary": "Better overall.", "recommendation": "ready_with_risks"},
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["summary"] == "Better overall."
        assert body["recommendation"] == "ready_with_risks"
        assert body["user_id"] == report["user_id"]


@pytest.mark.integration
class TestReportPublish:
    def test_publish_freezes_numbers(self, authenticated_client, build, test_db, db_endpoint):
        requirement = build.requirement("Card number")
        run = build.run()
        build.result(run, build.test(requirement), "pass")
        build.commit()
        report = _create(
            authenticated_client, db_endpoint.id, runs=[run], requirements=[requirement]
        )

        response = authenticated_client.post(f"/reports/{report['id']}/publish")
        assert response.status_code == status.HTTP_200_OK, response.text
        published = response.json()
        assert published["status"] == "published"
        assert published["snapshot_hash"].startswith("sha256:")
        assert "report:update" not in published["permitted_actions"]
        assert "report:delete" not in published["permitted_actions"]
        frozen = (
            test_db.query(models.ReportResult)
            .filter(models.ReportResult.report_id == uuid.UUID(report["id"]))
            .count()
        )
        assert frozen == 1

        # A later failure in the same run doesn't change the published report.
        build.result(run, build.test(requirement), "fail")
        build.commit()
        totals = _detail(authenticated_client, report["id"])["metrics"]["totals"]
        assert (totals["results"], totals["passed"], totals["failed"]) == (1, 1, 0)

    def test_published_report_cannot_change(self, authenticated_client, build, db_endpoint):
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        assert authenticated_client.post(f"/reports/{report['id']}/publish").status_code == 200

        put = authenticated_client.put(f"/reports/{report['id']}", json={"title": "Changed"})
        assert put.status_code == status.HTTP_409_CONFLICT
        delete = authenticated_client.delete(f"/reports/{report['id']}")
        assert delete.status_code == status.HTTP_409_CONFLICT
        again = authenticated_client.post(f"/reports/{report['id']}/publish")
        assert again.status_code == status.HTTP_409_CONFLICT

    def test_publish_needs_a_run(self, authenticated_client, db_endpoint):
        report = _create(authenticated_client, db_endpoint.id)
        response = authenticated_client.post(f"/reports/{report['id']}/publish")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_copy_starts_a_new_draft(self, authenticated_client, build, db_endpoint):
        requirement = build.requirement("Copy me")
        run = build.run()
        build.result(run, build.test(requirement))
        build.commit()
        report = _create(
            authenticated_client,
            db_endpoint.id,
            runs=[run],
            requirements=[requirement],
            summary="Original",
        )
        authenticated_client.post(f"/reports/{report['id']}/publish")

        response = authenticated_client.post(f"/reports/{report['id']}/copy")
        assert response.status_code == status.HTTP_200_OK, response.text
        copy = response.json()
        assert copy["status"] == "draft"
        assert copy["summary"] == "Original"
        detail = _detail(authenticated_client, copy["id"])
        assert detail["test_run_ids"] == [str(run.id)]
        assert detail["requirement_ids"] == [str(requirement.id)]

    def test_export_is_recorded(self, authenticated_client, db_endpoint):
        report = _create(authenticated_client, db_endpoint.id)
        response = authenticated_client.post(f"/reports/{report['id']}/export")
        assert response.status_code == status.HTTP_200_OK, response.text

    def test_draft_can_be_deleted(self, authenticated_client, db_endpoint):
        report = _create(authenticated_client, db_endpoint.id)
        assert authenticated_client.delete(f"/reports/{report['id']}").status_code == 200
        # Soft-deleted rows answer 410 Gone, as everywhere else.
        assert authenticated_client.get(f"/reports/{report['id']}").status_code == 410


@pytest.fixture
def section_registry():
    """An empty registry for the test; whatever EE registered comes back after."""
    saved = get_report_sections()
    reset_report_sections()
    yield
    reset_report_sections()
    for section in saved:
        register_report_section(section)


@pytest.mark.integration
class TestReportSections:
    """The seam EE fills. Core runs only sections whose feature the org has."""

    def test_available_section_is_built_live_and_frozen(
        self, authenticated_client, build, db_endpoint, section_registry
    ):
        if not FeatureRegistry.is_registered(FeatureName.AUDIT_LOG):
            FeatureRegistry.register(Feature(name=FeatureName.AUDIT_LOG))
        calls = []

        def build_count(db, context):
            calls.append(context.report.status)
            return {"counted": len(context.counted)}

        register_report_section(ReportSection("probe", FeatureName.AUDIT_LOG, build_count))
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])

        assert _detail(authenticated_client, report["id"])["sections"] == {"probe": {"counted": 1}}
        authenticated_client.post(f"/reports/{report['id']}/publish")
        assert _detail(authenticated_client, report["id"])["sections"] == {"probe": {"counted": 1}}
        assert calls == ["draft", "draft"]  # preview, publish; never after

    def test_unavailable_feature_leaves_section_out(
        self, authenticated_client, db_endpoint, section_registry, monkeypatch
    ):
        register_report_section(
            ReportSection("hidden", FeatureName.AUDIT_LOG, lambda db, context: {"x": 1})
        )
        monkeypatch.setattr(FeatureRegistry, "is_available", classmethod(lambda cls, n, o: False))
        report = _create(authenticated_client, db_endpoint.id)
        assert _detail(authenticated_client, report["id"])["sections"] == {}


SUMMARY_MODEL = "rhesis.backend.app.services.report.summary.resolve_model"


@pytest.mark.integration
class TestReportSummaryDraft:
    def test_draft_uses_the_numbers_and_is_not_saved(
        self, authenticated_client, build, db_endpoint
    ):
        requirement = build.requirement("Handoff")
        run = build.run()
        build.result(run, build.test(requirement), "fail")
        build.commit()
        report = _create(
            authenticated_client, db_endpoint.id, runs=[run], requirements=[requirement]
        )
        model = MagicMock()
        model.generate.return_value = {
            "summary": "One test, it failed.",
            "recommendation": "not_ready",
        }

        with patch(SUMMARY_MODEL, return_value=model):
            response = authenticated_client.post(f"/reports/{report['id']}/summary")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == {"summary": "One test, it failed.", "recommendation": "not_ready"}
        prompt = model.generate.call_args.args[0]
        assert requirement.name in prompt
        assert "1 failed" in prompt
        assert _detail(authenticated_client, report["id"])["summary"] is None

    def test_model_failure_is_a_502(self, authenticated_client, db_endpoint):
        report = _create(authenticated_client, db_endpoint.id)
        model = MagicMock()
        model.generate.return_value = "not json"
        with patch(SUMMARY_MODEL, return_value=model):
            response = authenticated_client.post(f"/reports/{report['id']}/summary")
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    def test_published_report_gets_no_draft(self, authenticated_client, build, db_endpoint):
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        authenticated_client.post(f"/reports/{report['id']}/publish")
        response = authenticated_client.post(f"/reports/{report['id']}/summary")
        assert response.status_code == status.HTTP_409_CONFLICT
