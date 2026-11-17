"""EE report sections (by impact, people, stats) and the report audit trail.

Run with: cd apps/backend && uv run pytest ../../tests/backend/ee/reports -v
"""

import uuid

import pytest
from fastapi import status

from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
from rhesis.backend.ee.reports import register_reports
from tests.backend.routes.test_report import _Builder, _create, _detail

pytestmark = [pytest.mark.ee, pytest.mark.integration]


@pytest.fixture(autouse=True)
def _reports_registered():
    register_reports()


@pytest.fixture
def build(test_db, test_org_id, authenticated_user_id, db_status, db_test_configuration):
    return _Builder(
        test_db, test_org_id, authenticated_user_id, db_status.id, db_test_configuration
    )


def _impact(test_db, name, org_id, user_id):
    lookup = get_or_create_type_lookup(
        db=test_db,
        type_name="RequirementImpact",
        type_value=name,
        organization_id=org_id,
        user_id=user_id,
        commit=False,
    )
    test_db.flush()
    return lookup


def _deny(monkeypatch, feature):
    original = FeatureRegistry.is_available.__func__

    def is_available(cls, name, org):
        return name != feature and original(cls, name, org)

    monkeypatch.setattr(FeatureRegistry, "is_available", classmethod(is_available))


class TestByImpact:
    def test_rows_in_seeded_order_only_tested_impacts(
        self, authenticated_client, build, test_db, db_endpoint, test_org_id, authenticated_user_id
    ):
        legal = _impact(test_db, "Legal & compliance", test_org_id, authenticated_user_id)
        safety = _impact(test_db, "Safety", test_org_id, authenticated_user_id)
        reputation = _impact(test_db, "Reputation", test_org_id, authenticated_user_id)
        advice = build.requirement("Advice")
        advice.impact_id = legal.id
        handoff = build.requirement("Handoff")
        handoff.impact_id = reputation.id
        unrun = build.requirement("Never run")
        unrun.impact_id = safety.id
        plain = build.requirement("No impact")
        run = build.run()
        build.result(run, build.test(advice), "pass")
        build.result(run, build.test(advice), "fail")
        build.result(run, build.test(handoff), "fail")
        build.result(run, build.test(plain), "pass")
        build.commit()

        report = _create(
            authenticated_client,
            db_endpoint.id,
            runs=[run],
            requirements=[advice, handoff, unrun, plain],
        )
        section = _detail(authenticated_client, report["id"])["sections"]["by_impact"]

        assert [row["name"] for row in section["impacts"]] == [
            "Legal & compliance",
            "Reputation",
            "Not set",
        ]
        legal_row = section["impacts"][0]
        assert (legal_row["passed"], legal_row["failed"], legal_row["pass_rate"]) == (1, 1, 50.0)
        assert section["requirements"][str(unrun.id)] == "Safety"
        assert section["requirements"][str(plain.id)] == "Not set"

    def test_left_out_without_the_feature(
        self, authenticated_client, build, db_endpoint, monkeypatch
    ):
        _deny(monkeypatch, FeatureName.ADVANCED_REPORTS)
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        sections = _detail(authenticated_client, report["id"])["sections"]
        assert not {"by_impact", "people", "stats"} & set(sections)


class TestPeopleAndStats:
    def test_people_and_response_times(self, authenticated_client, build, test_db, db_endpoint):
        run = build.run()
        for ms in (100.0, 200.0, 900.0):
            result = build.result(run, build.test())
            result.test_metrics = {"execution_time": ms, "metrics": {}}
        build.result(run, build.test(), execution="error")
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        sections = _detail(authenticated_client, report["id"])["sections"]

        people = sections["people"]
        assert people["author"]["id"] == report["user_id"]
        assert [p["id"] for p in people["ran_tests"]] == [str(build.user_id)]
        assert people["verdicts_changed"] == 0

        stats = sections["stats"]
        assert (stats["results_judged"], stats["results_errored"]) == (3, 1)
        assert stats["response_time_ms"] == {"mean": 400.0, "p95": 900.0, "measured": 3}

    def test_sections_freeze_at_publish(self, authenticated_client, build, db_endpoint):
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        authenticated_client.post(f"/reports/{report['id']}/publish")

        build.result(run, build.test(), execution="error")
        build.commit()
        stats = _detail(authenticated_client, report["id"])["sections"]["stats"]
        assert (stats["results_judged"], stats["results_errored"]) == (1, 0)


class TestAuditTrail:
    def test_publish_and_export_show_up(self, authenticated_client, build, db_endpoint):
        run = build.run()
        build.result(run, build.test())
        build.commit()
        report = _create(authenticated_client, db_endpoint.id, runs=[run])
        authenticated_client.post(f"/reports/{report['id']}/publish")
        authenticated_client.post(f"/reports/{report['id']}/export")

        response = authenticated_client.get(f"/reports/{report['id']}/audit-trail")
        assert response.status_code == status.HTTP_200_OK, response.text
        actions = [entry["action"] for entry in response.json()]
        assert "report.published" in actions
        assert "report.exported" in actions

    def test_unknown_report_is_404(self, authenticated_client):
        response = authenticated_client.get(f"/reports/{uuid.uuid4()}/audit-trail")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_hidden_without_the_audit_log(self, authenticated_client, db_endpoint, monkeypatch):
        report = _create(authenticated_client, db_endpoint.id)
        _deny(monkeypatch, FeatureName.AUDIT_LOG)
        response = authenticated_client.get(f"/reports/{report['id']}/audit-trail")
        assert response.status_code == status.HTTP_404_NOT_FOUND
