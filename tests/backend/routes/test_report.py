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
    get_report_pdf_notes,
    get_report_sections,
    register_report_pdf_note,
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

    def tag(self, run, name: str) -> None:
        tag = self._add(models.Tag(name=name, organization_id=self.org_id, user_id=self.user_id))
        self._add(
            models.TaggedItem(
                tag_id=tag.id,
                entity_id=run.id,
                entity_type="TestRun",
                organization_id=self.org_id,
                user_id=self.user_id,
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

    def test_rule_all_averages_repeated_runs(self, authenticated_client, build, db_endpoint):
        requirement = build.requirement("Repeated")
        test = build.test(requirement)
        runs = [build.run() for _ in range(4)]
        for run, verdict in zip(runs, ("pass", "fail", "pass", "pass"), strict=True):
            build.result(run, test, verdict)
        build.commit()
        report = _create(
            authenticated_client,
            db_endpoint.id,
            runs=runs,
            requirements=[requirement],
            result_rule="all",
        )
        metrics = _detail(authenticated_client, report["id"])["metrics"]
        assert metrics["result_rule"] == "all"
        assert (metrics["totals"]["results"], metrics["totals"]["pass_rate"]) == (4, 75.0)
        # Each run keeps its own pass rate, whatever the rule.
        assert sorted(r["pass_rate"] for r in metrics["runs"]) == [0.0, 100.0, 100.0, 100.0]
        assert metrics["totals"]["inconsistent"] == 1

        # Switching the draft to "worst" makes the one failure decide.
        response = authenticated_client.put(
            f"/reports/{report['id']}", json={"result_rule": "worst"}
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        totals = _detail(authenticated_client, report["id"])["metrics"]["totals"]
        assert (totals["results"], totals["failed"], totals["pass_rate"]) == (1, 1, 0.0)

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
        # Each run carries its status and test set for the page and the PDF.
        assert all(r["status"] for r in metrics["runs"])
        assert all("test_set" in r for r in metrics["runs"])

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
class TestReportFindings:
    """What a decision needs beyond the totals: caveats, key failures, comparison."""

    def test_warnings_flag_untested_low_sample_and_changed_verdicts(
        self, authenticated_client, build, test_db, db_endpoint
    ):
        tested = build.requirement("Tested")
        untested = build.requirement("Untested")
        run = build.run()
        result = build.result(run, build.test(tested), "pass")
        result.original_status_id = build.status_id  # a reviewer overrode the judge
        build.commit()
        report = _create(
            authenticated_client, db_endpoint.id, runs=[run], requirements=[tested, untested]
        )

        metrics = _detail(authenticated_client, report["id"])["metrics"]

        kinds = {w["kind"] for w in metrics["warnings"]}
        assert {"untested", "low_sample", "verdicts_changed"} <= kinds
        assert _rows_by_name({"metrics": metrics})[tested.name]["low_sample"] is True

    def test_metrics_by_requirement_with_their_kind(self, authenticated_client, build, db_endpoint):
        requirement = build.requirement("Judged")
        run = build.run()
        for verdict, ok in (("pass", True), ("fail", False)):
            result = build.result(run, build.test(requirement), verdict)
            result.test_metrics = {
                "metrics": {
                    "Tone judge": {"is_successful": ok},
                    "Format check": {"is_successful": True},
                }
            }
        build.commit()
        report = _create(
            authenticated_client, db_endpoint.id, runs=[run], requirements=[requirement]
        )

        groups = _detail(authenticated_client, report["id"])["metrics"]["metric_results"]

        assert [g["name"] for g in groups] == [requirement.name]
        by_name = {m["name"]: m for m in groups[0]["metrics"]}
        assert (by_name["Tone judge"]["passed"], by_name["Tone judge"]["failed"]) == (1, 1)
        assert by_name["Format check"]["pass_rate"] == 100.0
        # No metric records for these names: they default to LLM judges.
        assert {m["kind"] for m in groups[0]["metrics"]} == {"llm"}
        # Weakest metric first.
        assert groups[0]["metrics"][0]["name"] == "Tone judge"

    def test_comparison_with_the_previous_published_report(
        self, authenticated_client, build, db_endpoint
    ):
        requirement = build.requirement("Compared")
        steady, regressed = build.test(requirement), build.test(requirement)
        first = build.run()
        build.result(first, steady, "pass")
        build.result(first, regressed, "pass")
        build.commit()
        previous = _create(
            authenticated_client, db_endpoint.id, runs=[first], requirements=[requirement]
        )
        authenticated_client.post(f"/reports/{previous['id']}/publish")

        second = build.run()
        build.result(second, steady, "pass")
        build.result(second, regressed, "fail")
        build.commit()
        report = _create(
            authenticated_client,
            db_endpoint.id,
            runs=[second],
            requirements=[requirement],
            baseline_report_id=previous["id"],
        )

        metrics = _detail(authenticated_client, report["id"])["metrics"]
        comparison = metrics["comparison"]
        assert comparison["baseline"]["id"] == previous["id"]
        assert comparison["pass_rate_delta"] == -50.0
        assert (comparison["newly_failing"], comparison["fixed"]) == (1, 0)
        assert comparison["newly_failing_requirements"] == [requirement.name]
        assert _rows_by_name({"metrics": metrics})[requirement.name]["pass_rate_delta"] == -50.0

    def test_no_comparison_unless_one_is_picked(self, authenticated_client, build, db_endpoint):
        run = build.run()
        build.result(run, build.test())
        build.commit()
        earlier = _create(authenticated_client, db_endpoint.id, runs=[run])
        authenticated_client.post(f"/reports/{earlier['id']}/publish")

        report = _create(authenticated_client, db_endpoint.id, runs=[run])

        metrics = _detail(authenticated_client, report["id"])["metrics"]
        assert metrics["comparison"] is None
        assert all(row["pass_rate_delta"] is None for row in metrics["requirements"])

    def test_a_draft_cannot_be_the_comparison(self, authenticated_client, db_endpoint):
        draft = _create(authenticated_client, db_endpoint.id)
        response = authenticated_client.post(
            "/reports/",
            json={
                "title": "Next",
                "endpoint_id": str(db_endpoint.id),
                "baseline_report_id": draft["id"],
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_copy_of_a_published_report_compares_with_it(
        self, authenticated_client, build, db_endpoint
    ):
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        authenticated_client.post(f"/reports/{report['id']}/publish")

        copy = authenticated_client.post(f"/reports/{report['id']}/copy").json()

        assert copy["baseline_report_id"] == report["id"]


@pytest.mark.integration
class TestRunsByTag:
    def test_tagged_runs_join_a_draft_and_freeze_at_publish(
        self, authenticated_client, build, db_endpoint
    ):
        tagged, untagged, later = build.run(), build.run(), build.run()
        for run in (tagged, untagged, later):
            build.result(run, build.test())
        build.tag(tagged, "2.5")
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, run_tag="2.5")

        detail = _detail(authenticated_client, report["id"])
        assert detail["tagged_run_ids"] == [str(tagged.id)]
        assert [r["id"] for r in detail["metrics"]["runs"]] == [str(tagged.id)]

        authenticated_client.post(f"/reports/{report['id']}/publish")
        build.tag(later, "2.5")  # tagged after publishing: must not join
        build.commit()

        detail = _detail(authenticated_client, report["id"])
        assert detail["test_run_ids"] == [str(tagged.id)]
        assert detail["tagged_run_ids"] == []
        assert len(detail["metrics"]["runs"]) == 1

    def test_tag_and_picked_runs_are_refused(self, authenticated_client, build, db_endpoint):
        run = build.run()
        build.commit()
        response = authenticated_client.post(
            "/reports/",
            json={
                "title": "Both",
                "endpoint_id": str(db_endpoint.id),
                "test_run_ids": [str(run.id)],
                "requirement_ids": [],
                "run_tag": "2.5",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text

    def test_switching_to_a_tag_drops_picked_runs(self, authenticated_client, build, db_endpoint):
        picked, tagged = build.run(), build.run()
        for run in (picked, tagged):
            build.result(run, build.test())
        build.tag(tagged, "2.5")
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[picked])

        put = authenticated_client.put(f"/reports/{report['id']}", json={"run_tag": "2.5"})
        assert put.status_code == status.HTTP_200_OK, put.text
        detail = _detail(authenticated_client, report["id"])
        assert detail["test_run_ids"] == []
        assert [r["id"] for r in detail["metrics"]["runs"]] == [str(tagged.id)]

        # And back: picking runs by hand needs the tag cleared in the same call.
        body = {"test_run_ids": [str(picked.id)]}
        refused = authenticated_client.put(f"/reports/{report['id']}", json=body)
        assert refused.status_code == status.HTTP_400_BAD_REQUEST
        put = authenticated_client.put(f"/reports/{report['id']}", json={**body, "run_tag": None})
        assert put.status_code == status.HTTP_200_OK, put.text
        assert _detail(authenticated_client, report["id"])["tagged_run_ids"] == []

    def test_a_tag_alone_is_enough(self, authenticated_client, build, db_endpoint):
        run = build.run()
        build.result(run, build.test(), "fail")
        build.tag(run, "Release-2.5")
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, run_tag="release-2.5")

        totals = _detail(authenticated_client, report["id"])["metrics"]["totals"]
        assert (totals["results"], totals["failed"]) == (1, 1)


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

    def test_pdf_of_a_draft(self, authenticated_client, build, db_endpoint):
        requirement = build.requirement("PDF requirement")
        run = build.run()
        build.result(run, build.test(requirement), "fail")
        build.commit()
        report = _create(
            authenticated_client,
            db_endpoint.id,
            runs=[run],
            requirements=[requirement],
            title="Release 2.4 <draft>",
            summary="One failure & one note.",
        )

        response = authenticated_client.get(f"/reports/{report['id']}/pdf")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert 'filename="Release-2.4-_draft_.pdf"' in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")

    def test_pdf_of_a_published_report(self, authenticated_client, build, db_endpoint):
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        authenticated_client.post(f"/reports/{report['id']}/publish")

        response = authenticated_client.get(f"/reports/{report['id']}/pdf")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.content.startswith(b"%PDF")

    def test_draft_can_be_deleted(self, authenticated_client, db_endpoint):
        report = _create(authenticated_client, db_endpoint.id)
        assert authenticated_client.delete(f"/reports/{report['id']}").status_code == 200
        # Soft-deleted rows answer 410 Gone, as everywhere else.
        assert authenticated_client.get(f"/reports/{report['id']}").status_code == 410


@pytest.fixture
def section_registry():
    """An empty registry for the test; whatever EE registered comes back after."""
    saved, saved_notes = get_report_sections(), get_report_pdf_notes()
    reset_report_sections()
    yield
    reset_report_sections()
    for section in saved:
        register_report_section(section)
    for note in saved_notes:
        register_report_pdf_note(note)


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

    def test_section_and_note_print_in_the_pdf(
        self, authenticated_client, build, db_endpoint, section_registry
    ):
        from reportlab.platypus import Paragraph

        if not FeatureRegistry.is_registered(FeatureName.AUDIT_LOG):
            FeatureRegistry.register(Feature(name=FeatureName.AUDIT_LOG))
        printed, noted = [], []

        def render(data):
            printed.append(data)
            return [Paragraph("Probe section")]

        register_report_section(
            ReportSection(
                "probe", FeatureName.AUDIT_LOG, lambda db, ctx: {"n": 1}, render_pdf=render
            )
        )
        register_report_pdf_note(lambda db, report: noted.append(report.id) or "A note")
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        authenticated_client.post(f"/reports/{report['id']}/publish")

        response = authenticated_client.get(f"/reports/{report['id']}/pdf")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert printed == [{"n": 1}]  # the frozen output, not a rebuild
        assert noted == [uuid.UUID(report["id"])]

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

    def test_plain_report_gets_no_recommendation(self, authenticated_client, db_endpoint):
        report = _create(authenticated_client, db_endpoint.id, is_release=False)
        model = MagicMock()
        model.generate.return_value = {"summary": "Fine.", "recommendation": "ready"}

        with patch(SUMMARY_MODEL, return_value=model):
            response = authenticated_client.post(f"/reports/{report['id']}/summary")

        assert response.json() == {"summary": "Fine.", "recommendation": None}
        prompt = model.generate.call_args.args[0]
        assert "ship" not in prompt
        assert "recommendation" not in prompt

    def test_turning_release_off_drops_the_recommendation(self, authenticated_client, db_endpoint):
        report = _create(authenticated_client, db_endpoint.id, recommendation="ready")
        assert report["is_release"] is True

        put = authenticated_client.put(f"/reports/{report['id']}", json={"is_release": False})
        assert put.status_code == status.HTTP_200_OK, put.text
        assert (put.json()["is_release"], put.json()["recommendation"]) == (False, None)

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
