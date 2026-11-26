"""Which project ingested spans go to: the same rule on the SDK and OTLP routes."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from rhesis.telemetry.schemas import OTELSpan, SpanKind, StatusCode

from rhesis.backend.app.routers import telemetry_intake

TENANT = ("org-1", "user-1")


def _span(project_id, span_id="a" * 16):
    start = datetime.now(timezone.utc)
    return OTELSpan(
        trace_id="b" * 32,
        span_id=span_id,
        project_id=project_id,
        environment="test",
        span_name="function.chat",
        span_kind=SpanKind.SERVER,
        start_time=start,
        end_time=start + timedelta(milliseconds=5),
        status_code=StatusCode.OK,
        attributes={},
    )


@pytest.fixture
def checked(monkeypatch):
    """Projects passed to the access check; ``forbidden`` ones answer 403."""
    seen = {"checked": [], "forbidden": set()}

    def check(request, current_user, project_id):
        seen["checked"].append(project_id)
        if project_id in seen["forbidden"]:
            raise HTTPException(status_code=403)
        return project_id

    monkeypatch.setattr(telemetry_intake, "check_project_access", check)
    return seen


def _jobs(spans, scope=None, hooks=()):
    return telemetry_intake.ingest_jobs(None, None, TENANT, spans, scope, hooks)


@pytest.mark.unit
class TestIngestProjectRule:
    def test_the_scope_wins_over_the_spans_project(self, checked):
        jobs = _jobs([_span("p-span")], scope="p-scope")

        assert [(j.project_id, len(j.spans)) for j in jobs] == [("p-scope", 1)]
        assert checked["checked"] == []

    def test_without_a_scope_each_span_goes_to_its_own_project(self, checked):
        spans = [_span("p-1", "1" * 16), _span("p-2", "2" * 16), _span("p-1", "3" * 16)]

        jobs = _jobs(spans)

        assert {j.project_id: len(j.spans) for j in jobs} == {"p-1": 2, "p-2": 1}
        assert sorted(checked["checked"]) == ["p-1", "p-2"]

    def test_a_span_without_a_project_takes_the_scope(self, checked):
        jobs = _jobs([_span("unknown"), _span(None, "1" * 16)], scope="p-scope")

        assert [(j.project_id, len(j.spans)) for j in jobs] == [("p-scope", 2)]

    @pytest.mark.parametrize("project_id", [None, "", "unknown"])
    def test_no_scope_and_no_span_project_is_unresolved(self, checked, project_id):
        with pytest.raises(telemetry_intake.ProjectUnresolved):
            _jobs([_span("p-1", "1" * 16), _span(project_id)])

    def test_a_spans_project_the_caller_cannot_enter_is_refused(self, checked):
        checked["forbidden"].add("p-2")

        with pytest.raises(HTTPException) as exc:
            _jobs([_span("p-1", "1" * 16), _span("p-2", "2" * 16)])
        assert exc.value.status_code == 403

    def test_jobs_carry_the_tenant_and_hooks(self, checked):
        (job,) = _jobs([_span("p-1")], hooks=["hook"])

        assert (job.organization_id, job.user_id, job.pre_store_hooks) == (
            "org-1",
            "user-1",
            ["hook"],
        )
