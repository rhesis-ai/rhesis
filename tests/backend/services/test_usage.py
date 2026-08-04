"""Tests for rhesis.backend.app.services.usage.

Flow-resource tests exercise the real `usage` table via `test_db` (a
Postgres-backed session, isolated per test via SAVEPOINT rollback -- see
tests/backend/fixtures/database.py). Stock-resource tests create Project/
Endpoint rows directly against the same session.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.usage import Usage
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services.usage import (
    _current_period,
    count_org_endpoints,
    count_org_projects,
    count_org_seats,
    dispatch_accrual,
    get_usage_summary,
    increment_usage,
)


class TestCurrentPeriod:
    def test_returns_first_and_last_day_of_month(self):
        start, end = _current_period(date(2026, 2, 10))
        assert start == date(2026, 2, 1)
        assert end == date(2026, 2, 28)

    def test_handles_leap_year(self):
        _, end = _current_period(date(2024, 2, 10))
        assert end == date(2024, 2, 29)

    def test_handles_31_day_month(self):
        _, end = _current_period(date(2026, 1, 15))
        assert end == date(2026, 1, 31)

    def test_defaults_to_the_utc_date_not_the_local_one(self):
        """Billing periods are UTC-anchored so workers in different
        timezones agree on which month a call belongs to."""
        start, end = _current_period()
        utc_today = datetime.now(timezone.utc).date()

        assert start == utc_today.replace(day=1)
        assert end.month == utc_today.month


class TestDispatchAccrual:
    """`dispatch_accrual` is the only entry point call sites use. It queues
    the write and must never raise back into the operation it measures."""

    @pytest.fixture
    def fake_delay(self, monkeypatch):
        recorded = []
        monkeypatch.setattr(
            "rhesis.backend.tasks.usage.accrue_usage.delay",
            lambda *args: recorded.append(args),
        )
        return recorded

    def test_queues_the_task_with_the_resource_as_a_string(self, fake_delay):
        dispatch_accrual("org-1", QuotaResource.TEST_EXECUTIONS, 12)

        assert fake_delay == [("org-1", "test_executions", 12)]

    def test_defaults_to_one(self, fake_delay):
        dispatch_accrual("org-1", QuotaResource.TEST_EXECUTIONS)

        assert fake_delay == [("org-1", "test_executions", 1)]

    @pytest.mark.parametrize("amount", [0, -5])
    def test_non_positive_amount_queues_nothing(self, amount, fake_delay):
        dispatch_accrual("org-1", QuotaResource.TEST_EXECUTIONS, amount)

        assert fake_delay == []

    @pytest.mark.parametrize("org_id", [None, ""])
    def test_missing_org_queues_nothing(self, org_id, fake_delay):
        """A task whose tenant context never resolved has no org to bill."""
        dispatch_accrual(org_id, QuotaResource.TEST_EXECUTIONS, 5)

        assert fake_delay == []

    def test_broker_failure_is_swallowed(self, monkeypatch):
        """The primary operation must survive a broker outage: an unlogged
        counter is recoverable, a failed test run is not."""

        def boom(*args):
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr("rhesis.backend.tasks.usage.accrue_usage.delay", boom)

        dispatch_accrual("org-1", QuotaResource.TRACING_SPANS, 5)  # must not raise


class TestIncrementUsage:
    def test_creates_and_increments_on_first_call(self, test_db, test_org_id):
        increment_usage(test_db, test_org_id, QuotaResource.TEST_GENERATION, 5)

        assert _usage_row(test_db, test_org_id, QuotaResource.TEST_GENERATION).used == 5

    def test_accumulates_across_calls(self, test_db, test_org_id):
        increment_usage(test_db, test_org_id, QuotaResource.MODEL_TOKENS, 100)
        increment_usage(test_db, test_org_id, QuotaResource.MODEL_TOKENS, 250)

        assert _usage_row(test_db, test_org_id, QuotaResource.MODEL_TOKENS).used == 350

    def test_zero_amount_is_noop(self, test_db, test_org_id):
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 0)

        assert _usage_row(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS) is None

    def test_negative_amount_is_noop(self, test_db, test_org_id):
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, -5)

        assert _usage_row(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS) is None

    def test_default_amount_is_one(self, test_db, test_org_id):
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS)

        assert _usage_row(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS).used == 1


def _usage_row(db, org_id, resource: QuotaResource) -> Usage | None:
    period_start, _ = _current_period()
    return (
        db.query(Usage)
        .filter(
            Usage.organization_id == org_id,
            Usage.resource == resource.value,
            Usage.period_start == period_start,
        )
        .first()
    )


class TestStockCounters:
    def test_count_org_seats_includes_session_user(self, test_db, test_org_id):
        assert count_org_seats(test_db, test_org_id) >= 1

    def test_count_org_projects_excludes_soft_deleted(self, test_db, test_org_id):
        baseline = count_org_projects(test_db, test_org_id)

        active = Project(name="usage-test-active-project", organization_id=test_org_id)
        deleted = Project(
            name="usage-test-deleted-project",
            organization_id=test_org_id,
            deleted_at=datetime.now(timezone.utc),
        )
        test_db.add_all([active, deleted])
        test_db.commit()

        assert count_org_projects(test_db, test_org_id) == baseline + 1

    def test_count_org_endpoints_excludes_soft_deleted(self, test_db, test_org_id):
        project = Project(name="usage-test-endpoint-project", organization_id=test_org_id)
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        baseline = count_org_endpoints(test_db, test_org_id)

        active = Endpoint(
            name="usage-test-endpoint-active",
            connection_type="rest",
            organization_id=test_org_id,
            project_id=project.id,
        )
        deleted = Endpoint(
            name="usage-test-endpoint-deleted",
            connection_type="rest",
            organization_id=test_org_id,
            project_id=project.id,
            deleted_at=datetime.now(timezone.utc),
        )
        test_db.add_all([active, deleted])
        test_db.commit()

        assert count_org_endpoints(test_db, test_org_id) == baseline + 1


class TestGetUsageSummary:
    def test_includes_every_quota_resource(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)

        summary = get_usage_summary(test_db, test_org_id, org)

        assert set(summary["resources"].keys()) == {r.value for r in QuotaResource}
        assert "edition" in summary

    def test_flow_resource_reflects_accrued_usage(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)
        increment_usage(test_db, test_org_id, QuotaResource.TRACING_SPANS, 42)

        summary = get_usage_summary(test_db, test_org_id, org)

        assert summary["resources"][QuotaResource.TRACING_SPANS.value]["used"] == 42

    def test_stock_resource_reflects_live_count(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)

        summary = get_usage_summary(test_db, test_org_id, org)

        assert summary["resources"][QuotaResource.SEATS.value]["used"] >= 1

    def test_every_resource_has_limit_and_period_fields(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)

        summary = get_usage_summary(test_db, test_org_id, org)

        for item in summary["resources"].values():
            assert "limit" in item
            assert "period_start" in item
            assert "period_end" in item
            assert item["kind"] in ("flow", "stock")

    def test_kind_matches_stock_vs_flow_split(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)

        summary = get_usage_summary(test_db, test_org_id, org)

        stock_resources = {
            QuotaResource.SEATS.value,
            QuotaResource.PROJECTS.value,
            QuotaResource.ENDPOINTS.value,
        }
        for resource_value, item in summary["resources"].items():
            expected_kind = "stock" if resource_value in stock_resources else "flow"
            assert item["kind"] == expected_kind
