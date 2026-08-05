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
    InvalidPeriodError,
    _current_period,
    _recent_period_starts,
    count_org_endpoints,
    count_org_projects,
    count_org_seats,
    dispatch_accrual,
    get_usage_history,
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


class TestGetUsageSummaryForPastPeriod:
    def test_reports_a_past_month_s_flow_usage(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)
        past_start, past_end = _current_period(date(2026, 1, 15))
        test_db.add(
            Usage(
                organization_id=test_org_id,
                resource=QuotaResource.TEST_EXECUTIONS.value,
                period_start=past_start,
                period_end=past_end,
                used=99,
            )
        )
        test_db.commit()

        summary = get_usage_summary(test_db, test_org_id, org, period_start=past_start)

        item = summary["resources"][QuotaResource.TEST_EXECUTIONS.value]
        assert item["used"] == 99
        assert item["period_start"] == past_start.isoformat()
        assert item["period_end"] == past_end.isoformat()

    def test_includes_stock_resources_for_a_past_period(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)
        past_start, _ = _current_period(date(2026, 1, 15))

        summary = get_usage_summary(test_db, test_org_id, org, period_start=past_start)

        assert summary["resources"][QuotaResource.SEATS.value]["used"] >= 1

    def test_stock_resources_report_the_current_period_not_the_requested_one(
        self, test_db, test_org_id
    ):
        org = test_db.get(Organization, test_org_id)
        past_start, _ = _current_period(date(2026, 1, 15))
        current_start, current_end = _current_period()

        summary = get_usage_summary(test_db, test_org_id, org, period_start=past_start)

        seats = summary["resources"][QuotaResource.SEATS.value]
        assert seats["period_start"] == current_start.isoformat()
        assert seats["period_end"] == current_end.isoformat()

    def test_zero_fills_a_past_month_with_no_accrual(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)
        past_start, _ = _current_period(date(2026, 1, 15))

        summary = get_usage_summary(test_db, test_org_id, org, period_start=past_start)

        assert summary["resources"][QuotaResource.TRACING_SPANS.value]["used"] == 0

    def test_current_period_start_is_treated_as_current(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)
        current_start, _ = _current_period()

        summary = get_usage_summary(test_db, test_org_id, org, period_start=current_start)

        assert set(summary["resources"].keys()) == {r.value for r in QuotaResource}

    def test_rejects_a_period_start_that_is_not_the_first_of_the_month(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)

        with pytest.raises(InvalidPeriodError, match="first day of a month"):
            get_usage_summary(test_db, test_org_id, org, period_start=date(2026, 1, 15))

    def test_rejects_a_period_start_in_the_future(self, test_db, test_org_id):
        org = test_db.get(Organization, test_org_id)
        current_start, _ = _current_period()
        next_month = date(
            current_start.year + (1 if current_start.month == 12 else 0),
            1 if current_start.month == 12 else current_start.month + 1,
            1,
        )

        with pytest.raises(InvalidPeriodError, match="later than the current period"):
            get_usage_summary(test_db, test_org_id, org, period_start=next_month)


class TestRecentPeriodStarts:
    def test_returns_months_oldest_first_ending_at_today(self):
        starts = _recent_period_starts(3, today=date(2026, 3, 15))

        assert starts == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]

    def test_crosses_a_year_boundary(self):
        starts = _recent_period_starts(3, today=date(2026, 2, 10))

        assert starts == [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)]

    def test_single_month_is_just_the_current_one(self):
        starts = _recent_period_starts(1, today=date(2026, 6, 20))

        assert starts == [date(2026, 6, 1)]


class TestGetUsageHistory:
    def test_excludes_stock_resources(self, test_db, test_org_id):
        history = get_usage_history(test_db, test_org_id, months=3)

        stock_resources = {
            QuotaResource.SEATS.value,
            QuotaResource.PROJECTS.value,
            QuotaResource.ENDPOINTS.value,
        }
        assert stock_resources.isdisjoint(history["resources"].keys())
        flow_resources = {
            QuotaResource.TEST_EXECUTIONS.value,
            QuotaResource.TRACING_SPANS.value,
            QuotaResource.TEST_GENERATION.value,
            QuotaResource.MODEL_TOKENS.value,
        }
        assert set(history["resources"].keys()) == flow_resources

    def test_zero_fills_months_with_no_accrual(self, test_db, test_org_id):
        history = get_usage_history(test_db, test_org_id, months=3)

        points = history["resources"][QuotaResource.TEST_EXECUTIONS.value]
        assert len(points) == 3
        assert all(p["used"] == 0 for p in points)

    def test_reflects_current_month_accrual_at_the_last_point(self, test_db, test_org_id):
        increment_usage(test_db, test_org_id, QuotaResource.TRACING_SPANS, 15)

        history = get_usage_history(test_db, test_org_id, months=3)

        points = history["resources"][QuotaResource.TRACING_SPANS.value]
        assert points[-1]["used"] == 15
        assert points[-1]["period_start"] == _current_period()[0].isoformat()
        assert all(p["used"] == 0 for p in points[:-1])

    def test_includes_a_past_month_row_at_its_own_point(self, test_db, test_org_id):
        # Derived from today rather than hardcoded: a fixed date eventually
        # falls outside the trailing 12-month window this queries, and the
        # test would then fail for reasons unrelated to the code.
        past_period_start, past_period_end = _current_period(_recent_period_starts(3)[0])

        db_row = Usage(
            organization_id=test_org_id,
            resource=QuotaResource.TEST_GENERATION.value,
            period_start=past_period_start,
            period_end=past_period_end,
            used=7,
        )
        test_db.add(db_row)
        test_db.commit()

        history = get_usage_history(
            test_db,
            test_org_id,
            months=12,
        )
        point_at_past_month = next(
            p
            for p in history["resources"][QuotaResource.TEST_GENERATION.value]
            if p["period_start"] == past_period_start.isoformat()
        )
        assert point_at_past_month["used"] == 7

    @pytest.mark.parametrize("months", [0, -1])
    def test_rejects_a_non_positive_month_count(self, months, test_db, test_org_id):
        """Guarded in the service, not just by the router's ``Query(ge=1)``:
        an empty period list would otherwise raise ``IndexError``."""
        with pytest.raises(InvalidPeriodError, match="at least 1"):
            get_usage_history(test_db, test_org_id, months=months)

    def test_points_are_ordered_oldest_first(self, test_db, test_org_id):
        history = get_usage_history(test_db, test_org_id, months=6)

        points = history["resources"][QuotaResource.MODEL_TOKENS.value]
        period_starts = [p["period_start"] for p in points]
        assert period_starts == sorted(period_starts)
