"""Tests for services.usage_notifications.

Covers the transition-detection rule: a notification fires only when
`previous_used`/`new_used` actually span a threshold, never on a call that
starts and ends on the same side of it -- otherwise an org sitting past 80%
for weeks would be renotified on every subsequent accrual.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from rhesis.backend.app.crud.notification import get_notifications
from rhesis.backend.app.database import bind_scope_to_session
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.services.usage import count_org_projects
from rhesis.backend.app.services.usage_notifications import (
    notify_flow_crossing,
    notify_stock_crossing,
)


class _FixedPolicyProvider:
    def __init__(self, policy: QuotaPolicy):
        self._policy = policy

    def get_policy(self, org=None) -> QuotaPolicy:
        return self._policy


@pytest.fixture
def clean_registry():
    saved_provider = QuotaRegistry._provider
    QuotaRegistry.reset()
    yield
    QuotaRegistry._provider = saved_provider


def _install(policy: QuotaPolicy) -> None:
    QuotaRegistry.set_quota_provider(_FixedPolicyProvider(policy))


@pytest.mark.integration
class TestThresholdCrossing:
    @pytest.fixture(autouse=True)
    def _setup(self, test_db, test_org_id):
        self.db = test_db
        self.org = test_db.query(Organization).filter(Organization.id == test_org_id).first()

    def _event_types(self) -> set[str]:
        rows = get_notifications(self.db, user_id=str(self.org.owner_id))
        return {r.event_type for r in rows}

    def test_no_notification_for_unlimited_resource(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.MODEL_TOKENS: None}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                self.db,
                str(self.org.id),
                QuotaResource.MODEL_TOKENS,
                previous_used=0,
                new_used=10_000_000,
            )
        assert self._event_types() == set()

    def test_no_notification_when_staying_under_the_threshold(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                self.db,
                str(self.org.id),
                QuotaResource.TEST_EXECUTIONS,
                previous_used=10,
                new_used=20,
            )
        assert self._event_types() == set()

    def test_fires_approaching_on_crossing_80_percent(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                self.db,
                str(self.org.id),
                QuotaResource.TEST_EXECUTIONS,
                previous_used=79,
                new_used=80,
            )
        assert self._event_types() == {"usage.approaching_limit"}

    def test_does_not_refire_once_already_past_the_threshold(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                self.db,
                str(self.org.id),
                QuotaResource.TEST_EXECUTIONS,
                previous_used=85,
                new_used=86,
            )
        assert self._event_types() == set()

    def test_fires_blocked_on_crossing_a_hard_ceiling(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.PROJECTS: 5}, overage=OveragePolicy.HARD))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                self.db, str(self.org.id), QuotaResource.PROJECTS, previous_used=4, new_used=5
            )
        assert self._event_types() == {"usage.blocked"}

    def test_fires_blocked_on_crossing_a_soft_tier_s_ceiling_not_its_bare_limit(
        self, clean_registry
    ):
        # limit=100, 25% tolerance -> ceiling=125. Crossing the bare limit
        # (100) must not fire "blocked" -- that's the grace band, not the cut-off.
        _install(
            QuotaPolicy(
                limits={QuotaResource.TEST_EXECUTIONS: 100},
                overage=OveragePolicy.SOFT,
                overage_tolerance_percent=25,
            )
        )
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                self.db,
                str(self.org.id),
                QuotaResource.TEST_EXECUTIONS,
                previous_used=99,
                new_used=100,
            )
        assert self._event_types() == set()

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                self.db,
                str(self.org.id),
                QuotaResource.TEST_EXECUTIONS,
                previous_used=124,
                new_used=125,
            )
        assert self._event_types() == {"usage.blocked"}

    def test_blocked_wins_over_approaching_when_one_jump_crosses_both(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                self.db,
                str(self.org.id),
                QuotaResource.TEST_EXECUTIONS,
                previous_used=10,
                new_used=100,
            )
        assert self._event_types() == {"usage.blocked"}

    def test_noop_when_org_is_none(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        # Must not raise.
        notify_flow_crossing(
            self.db, None, QuotaResource.TEST_EXECUTIONS, previous_used=79, new_used=80
        )


@pytest.mark.integration
class TestOrgWideScoping:
    """A quota crossing is org state, so its notification must be visible in
    every project -- `project_id` NULL.

    Regression test: `auto_stamp` (models/scope_events.py) fills a `None`
    `project_id` from the session's scope, and the stock-resource callers run
    inside a project-scoped request. Before `_notify_owner` pinned the scope,
    the row was stamped with whichever project the acting admin had selected,
    and `auto_filter` plus the RESTRICTIVE `project_isolation` RLS policy then
    hid it from the owner in every other project.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, test_db, test_org_id):
        self.db = test_db
        self.org = test_db.query(Organization).filter(Organization.id == test_org_id).first()

    def test_notification_is_not_stamped_with_the_active_project(
        self, test_db, test_org_id, clean_registry
    ):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        active_project = str(uuid.uuid4())
        bind_scope_to_session(test_db, test_org_id, str(self.org.owner_id), active_project)

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_flow_crossing(
                test_db,
                test_org_id,
                QuotaResource.TEST_EXECUTIONS,
                previous_used=79,
                new_used=80,
            )

        rows = [
            r
            for r in get_notifications(test_db, user_id=str(self.org.owner_id))
            if r.event_type == "usage.approaching_limit"
        ]
        assert rows, "no approaching_limit notification was written"
        assert rows[0].project_id is None


@pytest.mark.integration
class TestStockCrossing:
    @pytest.fixture(autouse=True)
    def _setup(self, test_db, test_org_id):
        self.db = test_db
        self.org = test_db.query(Organization).filter(Organization.id == test_org_id).first()

    def test_notifies_when_a_created_project_reaches_the_limit(self, clean_registry):
        # count_org_projects is live, so pin the limit to whatever the count
        # is right now: creating the row that reaches it is the crossing.
        current = count_org_projects(self.db, str(self.org.id))
        _install(QuotaPolicy(limits={QuotaResource.PROJECTS: current}, overage=OveragePolicy.HARD))

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify_stock_crossing(self.db, self.org, QuotaResource.PROJECTS)

        rows = get_notifications(self.db, user_id=str(self.org.owner_id))
        assert {r.event_type for r in rows} == {"usage.blocked"}

    def test_swallows_a_failure_rather_than_raising_into_a_committed_route(self, clean_registry):
        # The three creation routes call this AFTER the row is committed (or
        # flushed), so a raise here would 500 a request whose work already
        # landed. project.py in particular commits first.
        class _Boom:
            def get_policy(self, org=None):
                raise RuntimeError("tier config is malformed")

        QuotaRegistry.set_quota_provider(_Boom())

        notify_stock_crossing(self.db, self.org, QuotaResource.PROJECTS)

    def test_ignores_a_flow_resource(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 1}))

        notify_stock_crossing(self.db, self.org, QuotaResource.TEST_EXECUTIONS)

        assert get_notifications(self.db, user_id=str(self.org.owner_id)) == []
