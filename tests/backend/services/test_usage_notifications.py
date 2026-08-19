"""Tests for services.usage_notifications.check_and_notify_threshold_crossing().

Covers the transition-detection rule: a notification fires only when
`previous_used`/`new_used` actually span a threshold, never on a call that
starts and ends on the same side of it -- otherwise an org sitting past 80%
for weeks would be renotified on every subsequent accrual.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from rhesis.backend.app.crud.notification import get_notifications
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.services.usage_notifications import check_and_notify_threshold_crossing


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
            check_and_notify_threshold_crossing(
                self.db,
                self.org,
                QuotaResource.MODEL_TOKENS,
                previous_used=0,
                new_used=10_000_000,
            )
        assert self._event_types() == set()

    def test_no_notification_when_staying_under_the_threshold(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            check_and_notify_threshold_crossing(
                self.db, self.org, QuotaResource.TEST_EXECUTIONS, previous_used=10, new_used=20
            )
        assert self._event_types() == set()

    def test_fires_approaching_on_crossing_80_percent(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            check_and_notify_threshold_crossing(
                self.db, self.org, QuotaResource.TEST_EXECUTIONS, previous_used=79, new_used=80
            )
        assert self._event_types() == {"usage.approaching_limit"}

    def test_does_not_refire_once_already_past_the_threshold(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            check_and_notify_threshold_crossing(
                self.db, self.org, QuotaResource.TEST_EXECUTIONS, previous_used=85, new_used=86
            )
        assert self._event_types() == set()

    def test_fires_blocked_on_crossing_a_hard_ceiling(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.PROJECTS: 5}, overage=OveragePolicy.HARD))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            check_and_notify_threshold_crossing(
                self.db, self.org, QuotaResource.PROJECTS, previous_used=4, new_used=5
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
            check_and_notify_threshold_crossing(
                self.db,
                self.org,
                QuotaResource.TEST_EXECUTIONS,
                previous_used=99,
                new_used=100,
            )
        assert self._event_types() == set()

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            check_and_notify_threshold_crossing(
                self.db,
                self.org,
                QuotaResource.TEST_EXECUTIONS,
                previous_used=124,
                new_used=125,
            )
        assert self._event_types() == {"usage.blocked"}

    def test_blocked_wins_over_approaching_when_one_jump_crosses_both(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            check_and_notify_threshold_crossing(
                self.db, self.org, QuotaResource.TEST_EXECUTIONS, previous_used=10, new_used=100
            )
        assert self._event_types() == {"usage.blocked"}

    def test_noop_when_org_is_none(self, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}))
        # Must not raise.
        check_and_notify_threshold_crossing(
            self.db, None, QuotaResource.TEST_EXECUTIONS, previous_used=79, new_used=80
        )
