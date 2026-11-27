"""Tests for GET /telemetry/attributes, the attribute catalogue for span targets."""

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from rhesis.telemetry import AIAttributes

from rhesis.backend.app import dependencies
from rhesis.backend.app.constants import SpanType
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.services.telemetry import span_attributes
from tests.backend.fixtures.rls import scope_to_org, scope_to_project
from tests.backend.routes.fixtures.data_factories import TraceDataFactory

TOOL = AIAttributes.OPERATION_TOOL_INVOKE
LLM = AIAttributes.OPERATION_LLM_INVOKE
OP = AIAttributes.OPERATION_TYPE
TOOL_NAME = AIAttributes.TOOL_NAME


def _span(project_id: str, attributes: dict, age: timedelta = timedelta()) -> dict:
    span = TraceDataFactory.minimal_data(project_id=project_id)
    start = datetime.now(timezone.utc) - age
    span.update(
        attributes=attributes,
        start_time=start.isoformat(),
        end_time=(start + timedelta(seconds=1)).isoformat(),
    )
    return span


def ingest(client: TestClient, project_id: str, spans: list, headers: dict | None = None) -> None:
    response = client.post("/telemetry/traces", json={"spans": spans}, headers=headers or {})
    assert response.status_code == status.HTTP_200_OK, response.text


def tool_span(project_id: str, tool: str, **attributes) -> dict:
    return _span(project_id, {OP: TOOL, TOOL_NAME: tool, **attributes})


def catalogue(client: TestClient, project_id: str, **params) -> dict:
    response = client.get("/telemetry/attributes", params={"project_id": project_id, **params})
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def attribute(data: dict, kind: str, key: str) -> dict:
    return next(a for a in data["kinds"][kind]["attributes"] if a["key"] == key)


@pytest.mark.integration
class TestAttributeCatalogue:
    def test_coverage_type_and_top_values(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        tools = ["issue_refund"] * 3 + ["cancel_order"] * 2 + ["lookup"]
        spans = [tool_span(project_id, name) for name in tools]
        spans[0]["attributes"]["app.tier"] = "gold"
        spans[1]["attributes"]["app.tier"] = "gold"
        spans[2]["attributes"]["app.retries"] = 2
        spans[3]["attributes"]["app.retries"] = "x"
        ingest(authenticated_client, project_id, spans)

        data = catalogue(authenticated_client, project_id)

        assert data["sampled_spans"] == 6
        assert datetime.fromisoformat(data["since"]) < datetime.now(timezone.utc)
        kind = data["kinds"][TOOL]
        assert kind["spans"] == 6
        assert [a["key"] for a in kind["attributes"]][:2] == [OP, TOOL_NAME]
        name = attribute(data, TOOL, TOOL_NAME)
        assert name["coverage"] == 1.0 and name["type"] == "string" and name["distinct"] == 3
        assert name["top_values"] == [
            {"value": "issue_refund", "count": 3, "truncated": False},
            {"value": "cancel_order", "count": 2, "truncated": False},
            {"value": "lookup", "count": 1, "truncated": False},
        ]
        tier = attribute(data, TOOL, "app.tier")
        assert tier["coverage"] == pytest.approx(2 / 6)
        assert tier["top_values"] == [{"value": "gold", "count": 2, "truncated": False}]
        assert attribute(data, TOOL, "app.retries")["type"] == "mixed"

    def test_top_values_are_capped_and_cut(
        self, authenticated_client: TestClient, db_project, monkeypatch
    ):
        monkeypatch.setattr(span_attributes, "VALUE_MAX_LENGTH", 5)
        project_id = str(db_project.id)
        names = [f"tool_{i:02d}" for i in range(12)]
        ingest(authenticated_client, project_id, [tool_span(project_id, n) for n in names])

        top = attribute(catalogue(authenticated_client, project_id), TOOL, TOOL_NAME)

        assert len(top["top_values"]) == span_attributes.TOP_VALUES
        assert top["distinct"] == 12
        assert top["top_values"][0] == {"value": "tool_", "count": 1, "truncated": True}

    def test_unique_flag(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        spans = [
            tool_span(project_id, "issue_refund", **{AIAttributes.TOOL_CALL_ID: f"call_{i}"})
            for i in range(span_attributes.UNIQUE_MIN_SPANS)
        ]
        ingest(authenticated_client, project_id, spans)

        data = catalogue(authenticated_client, project_id)

        assert attribute(data, TOOL, AIAttributes.TOOL_CALL_ID)["unique"] is True
        assert attribute(data, TOOL, TOOL_NAME)["unique"] is False

    def test_too_few_spans_are_not_unique(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        ingest(authenticated_client, project_id, [tool_span(project_id, "a", **{"x.id": "1"})])

        data = catalogue(authenticated_client, project_id)

        assert attribute(data, TOOL, "x.id")["unique"] is False

    def test_sample_takes_the_most_recent_spans(
        self, authenticated_client: TestClient, db_project, monkeypatch
    ):
        monkeypatch.setattr(span_attributes, "SAMPLE_SIZE", 3)
        project_id = str(db_project.id)
        recent = [tool_span(project_id, "recent") for _ in range(3)]
        old = _span(project_id, {OP: TOOL, "old.only": "yes"}, timedelta(hours=1))
        ingest(authenticated_client, project_id, [*recent, old])

        data = catalogue(authenticated_client, project_id)

        assert data["sampled_spans"] == 3
        keys = {a["key"] for a in data["kinds"][TOOL]["attributes"]}
        assert "old.only" not in keys

    def test_sample_is_taken_per_kind(
        self, authenticated_client: TestClient, db_project, monkeypatch
    ):
        monkeypatch.setattr(span_attributes, "SAMPLE_SIZE", 3)
        project_id = str(db_project.id)
        busy = [tool_span(project_id, "busy") for _ in range(8)]
        rare = _span(
            project_id,
            {OP: AIAttributes.OPERATION_GUARDRAIL, "guard.rule": "pii"},
            timedelta(hours=1),
        )
        ingest(authenticated_client, project_id, [*busy, rare])

        data = catalogue(authenticated_client, project_id)

        assert data["kinds"][TOOL]["spans"] == 3
        assert data["kinds"][AIAttributes.OPERATION_GUARDRAIL]["spans"] == 1
        assert attribute(data, AIAttributes.OPERATION_GUARDRAIL, "guard.rule")["top_values"] == [
            {"value": "pii", "count": 1, "truncated": False}
        ]
        assert data["sampled_spans"] == 4

    def test_days_window(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        ingest(
            authenticated_client,
            project_id,
            [_span(project_id, {OP: TOOL}, timedelta(days=3))],
        )

        assert catalogue(authenticated_client, project_id, days=1)["kinds"] == {}
        assert catalogue(authenticated_client, project_id, days=7)["sampled_spans"] == 1

    def test_kind_filter(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        ingest(
            authenticated_client,
            project_id,
            [
                tool_span(project_id, "issue_refund"),
                _span(project_id, {AIAttributes.MODEL_NAME: "gpt-4"}),
                _span(project_id, {}),
            ],
        )

        everything = catalogue(authenticated_client, project_id)
        tools_only = catalogue(authenticated_client, project_id, kind=TOOL)

        # A model name makes a span an LLM call, as on the spans list.
        assert set(everything["kinds"]) == {TOOL, LLM, SpanType.SPAN}
        assert everything["kinds"][SpanType.SPAN] == {"spans": 1, "attributes": []}
        assert set(tools_only["kinds"]) == {TOOL} and tools_only["sampled_spans"] == 1

    def test_limit_caps_keys_per_kind(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        ingest(authenticated_client, project_id, [tool_span(project_id, "a", **{"z.extra": 1})])

        data = catalogue(authenticated_client, project_id, limit=2)

        assert [a["key"] for a in data["kinds"][TOOL]["attributes"]] == [OP, TOOL_NAME]

    @pytest.mark.parametrize("params", [{"days": 0}, {"days": 365}, {"limit": 0}])
    def test_bounds(self, authenticated_client: TestClient, db_project, params):
        response = authenticated_client.get(
            "/telemetry/attributes", params={"project_id": str(db_project.id), **params}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_requires_auth(self, client: TestClient, db_project):
        response = client.get(f"/telemetry/attributes?project_id={db_project.id}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.integration
class TestAttributeCatalogueProjects:
    @pytest.fixture(autouse=True)
    def project_check_uses_test_db(self, test_db, monkeypatch):
        @contextmanager
        def _fake(*_args, **_kwargs):
            yield test_db

        monkeypatch.setattr(dependencies, "get_db_with_tenant_variables", _fake)

    @pytest.fixture
    def other_project(self, test_db, test_organization, db_user, db_owner_user, db_status):
        project = Project(
            name="Attribute Catalogue Other Project",
            user_id=db_user.id,
            owner_id=db_owner_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add(project)
        test_db.flush()
        return project

    def _join(self, test_db, project, test_organization, user_id) -> None:
        test_db.add(
            ProjectMembership(
                project_id=project.id, user_id=user_id, organization_id=test_organization.id
            )
        )
        test_db.flush()

    def test_only_the_requested_projects_spans(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_project,
        other_project,
        authenticated_user_id,
    ):
        self._join(test_db, other_project, test_organization, authenticated_user_id)
        other_id = str(other_project.id)
        ingest(
            authenticated_client,
            other_id,
            [tool_span(other_id, "elsewhere", **{"other.only": "yes"})],
            headers={"X-Project-Id": other_id},
        )
        scope_to_project(test_db, db_project.id)
        ingest(authenticated_client, str(db_project.id), [tool_span(str(db_project.id), "here")])

        mine = catalogue(authenticated_client, str(db_project.id))
        theirs = catalogue(authenticated_client, other_id)

        assert "other.only" not in {a["key"] for a in mine["kinds"][TOOL]["attributes"]}
        assert mine["sampled_spans"] == 1
        assert attribute(theirs, TOOL, "other.only")["coverage"] == 1.0
        assert theirs["sampled_spans"] == 1

    def test_another_organizations_project_is_not_read(
        self, authenticated_client: TestClient, test_db, client: TestClient
    ):
        from rhesis.backend.app.crud.project import create_project
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        suffix = uuid.uuid4()
        org, user, token = create_test_organization_and_user(
            test_db, f"Org Attrs {suffix}", f"user-attrs-{suffix}@test.com", "User Attrs"
        )
        project = create_project(
            test_db,
            {"name": f"Project Attrs {suffix}", "description": "Test project"},
            organization_id=str(org.id),
            user_id=str(user.id),
        )
        project_id = str(project.id)
        org_client = TestClient(client.app)
        org_client.headers = {"Authorization": f"Bearer {token.token}"}
        scope_to_org(test_db, str(org.id))
        scope_to_project(test_db, project_id)
        ingest(org_client, project_id, [tool_span(project_id, "x", **{"other.org": "yes"})])
        assert attribute(catalogue(org_client, project_id), TOOL, "other.org")

        response = authenticated_client.get(
            "/telemetry/attributes", params={"project_id": project_id}
        )

        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
