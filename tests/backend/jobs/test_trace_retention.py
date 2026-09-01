"""jobs/trace_retention.py: the sweep is disabled by default, keys trace
deletion on ``created_at`` per org, and respects per-org retention windows
resolved from the tier catalog. Integration-style, using
``real_commit_test_db``: the sweep opens its own ``SessionLocal()``
connections, so writes must be genuinely committed.

Modelled on ``test_retention.py`` (the job retention sweep), with the
additions the plan calls out: org-boundary isolation (a missing
``organization_id`` predicate under ``bypass_tenant_filter`` would silently
delete another org's data), per-org error isolation, dry-run vs live, and
the global ``TRACE_RETENTION_DAYS`` override.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.quota import QuotaPolicy, QuotaRegistry
from rhesis.backend.jobs import trace_retention
from rhesis.backend.jobs.trace_retention import sweep_expired_traces
from tests.backend.fixtures.test_setup import create_test_organization_and_user

_NOW = datetime.now(timezone.utc)
_OLD = _NOW - timedelta(days=100)
_RECENT = _NOW - timedelta(days=1)


class _FixedPolicyProvider:
    def __init__(self, policy: QuotaPolicy):
        self._policy = policy

    def get_policy(self, org=None) -> QuotaPolicy:
        return self._policy


def _settings(monkeypatch, *, enabled: bool, dry_run: bool = False, override_days=None):
    monkeypatch.setattr(
        "rhesis.backend.jobs.trace_retention.get_trace_retention_settings",
        lambda: SimpleNamespace(enabled=enabled, dry_run=dry_run, override_days=override_days),
    )


def _org(db: Session, name: str, email: str):
    org, user, _ = create_test_organization_and_user(db, name, email, f"{name} User")
    user.organization_id = org.id
    db.commit()
    return org, user


def _project(db: Session, org) -> str:
    proj = Project(name="retention-test-project", organization_id=org.id)
    db.add(proj)
    db.commit()
    project_id = str(proj.id)
    db.expunge(proj)
    return project_id


def _trace(db: Session, org, project_id: str, *, created_at) -> str:
    t = Trace(
        trace_id="deadbeef" * 4,
        span_id="abcd1234" * 2,
        project_id=project_id,
        organization_id=org.id,
        environment="test",
        span_name="test-span",
        span_kind="INTERNAL",
        start_time=created_at,
        end_time=created_at + timedelta(seconds=1),
        duration_ms=1000.0,
        status_code="OK",
        attributes={},
        events=[],
        links=[],
        resource={},
        created_at=created_at,
    )
    db.add(t)
    db.flush()
    trace_id = str(t.id)
    db.execute(
        text("UPDATE trace SET created_at = :ts WHERE id = :id"),
        {"ts": created_at, "id": trace_id},
    )
    db.commit()
    db.expunge(t)
    return trace_id


def _trace_exists(db: Session, trace_id: str) -> bool:
    db.expire_all()
    return (
        db.execute(text("SELECT 1 FROM trace WHERE id = :id"), {"id": trace_id}).first()
        is not None
    )


@pytest.mark.integration
class TestSweepDisabledByDefault:
    def test_disabled_deletes_nothing(self, monkeypatch, real_commit_test_db: Session):
        _settings(monkeypatch, enabled=False)
        db = real_commit_test_db
        org, user = _org(db, "Trace Ret Disabled Org", "trace-ret-disabled@test.com")
        project_id = _project(db, org)
        old_trace_id = _trace(db, org, project_id, created_at=_OLD)

        result = sweep_expired_traces()

        assert result == {"enabled": False}
        assert _trace_exists(db, old_trace_id)


@pytest.mark.integration
class TestSweepDeletesPastTheWindow:
    def test_deletes_old_traces_but_keeps_recent(
        self, monkeypatch, real_commit_test_db: Session
    ):
        _settings(monkeypatch, enabled=True)
        monkeypatch.setattr(
            "rhesis.backend.app.quota.get_application_settings",
            lambda: SimpleNamespace(usage_quotas_enabled=True),
        )
        QuotaRegistry.set_quota_provider(
            _FixedPolicyProvider(QuotaPolicy(limits={}, retention_days=30))
        )
        db = real_commit_test_db
        org, user = _org(db, "Trace Ret Delete Org", "trace-ret-delete@test.com")
        project_id = _project(db, org)

        old_trace_id = _trace(db, org, project_id, created_at=_OLD)
        recent_trace_id = _trace(db, org, project_id, created_at=_RECENT)

        try:
            result = sweep_expired_traces()

            assert result["enabled"] is True
            assert result["dry_run"] is False
            assert result["traces_affected"] >= 1
            assert not _trace_exists(db, old_trace_id)
            assert _trace_exists(db, recent_trace_id)
        finally:
            QuotaRegistry.reset()


@pytest.mark.integration
class TestSweepDryRun:
    def test_dry_run_counts_without_deleting(
        self, monkeypatch, real_commit_test_db: Session
    ):
        _settings(monkeypatch, enabled=True, dry_run=True)
        monkeypatch.setattr(
            "rhesis.backend.app.quota.get_application_settings",
            lambda: SimpleNamespace(usage_quotas_enabled=True),
        )
        QuotaRegistry.set_quota_provider(
            _FixedPolicyProvider(QuotaPolicy(limits={}, retention_days=30))
        )
        db = real_commit_test_db
        org, user = _org(db, "Trace Ret DryRun Org", "trace-ret-dryrun@test.com")
        project_id = _project(db, org)
        old_trace_id = _trace(db, org, project_id, created_at=_OLD)

        try:
            result = sweep_expired_traces()

            assert result["dry_run"] is True
            assert result["traces_affected"] >= 1
            assert _trace_exists(db, old_trace_id), "dry-run must not actually delete"
        finally:
            QuotaRegistry.reset()


@pytest.mark.integration
class TestSweepDeletesInBatches:
    def test_all_expired_rows_go_even_when_they_span_several_batches(
        self, monkeypatch, real_commit_test_db: Session
    ):
        """The delete is chunked to bound lock duration and WAL growth, so the
        loop has to come back for the remaining rows. Batch size is patched
        down to 2 rather than writing DELETE_BATCH_SIZE rows.

        Calls ``_sweep_organization`` directly rather than the task: the task
        sweeps every org in the database, so a total row count would also pick
        up whatever other tests in this file left behind.
        """
        monkeypatch.setattr(trace_retention, "DELETE_BATCH_SIZE", 2)
        db = real_commit_test_db
        org, _ = _org(db, "Trace Batch Org", "trace-batch@test.com")
        project_id = _project(db, org)

        # 5 expired rows over a batch size of 2: three passes, the last short.
        old_ids = [_trace(db, org, project_id, created_at=_OLD) for _ in range(5)]
        recent_id = _trace(db, org, project_id, created_at=_RECENT)

        deleted = trace_retention._sweep_organization(
            org, _NOW - timedelta(days=30), dry_run=False
        )

        assert deleted == 5, "every expired row must go, not just the first batch"
        for trace_id in old_ids:
            assert not _trace_exists(db, trace_id)
        assert _trace_exists(db, recent_id), "a recent trace must survive batching"


@pytest.mark.integration
class TestSweepUnlimitedRetention:
    def test_unlimited_retention_skips_the_org(
        self, monkeypatch, real_commit_test_db: Session
    ):
        """An org whose resolved retention_days is None (unlimited, e.g.
        enterprise default) is skipped entirely."""
        _settings(monkeypatch, enabled=True)
        monkeypatch.setattr(
            "rhesis.backend.app.quota.get_application_settings",
            lambda: SimpleNamespace(usage_quotas_enabled=True),
        )
        QuotaRegistry.set_quota_provider(
            _FixedPolicyProvider(QuotaPolicy(limits={}, retention_days=None))
        )
        db = real_commit_test_db
        org, user = _org(db, "Trace Ret Unlimited Org", "trace-ret-unlimited@test.com")
        project_id = _project(db, org)
        old_trace_id = _trace(db, org, project_id, created_at=_OLD)

        try:
            result = sweep_expired_traces()

            assert result["orgs_swept"] == 0
            assert _trace_exists(db, old_trace_id)
        finally:
            QuotaRegistry.reset()


@pytest.mark.integration
class TestSweepGlobalOverride:
    def test_override_days_supersedes_tier_retention(
        self, monkeypatch, real_commit_test_db: Session
    ):
        """TRACE_RETENTION_DAYS env var overrides the tier-resolved value.
        With a 200-day override, a 100-day-old trace is kept."""
        _settings(monkeypatch, enabled=True, override_days=200)
        monkeypatch.setattr(
            "rhesis.backend.app.quota.get_application_settings",
            lambda: SimpleNamespace(usage_quotas_enabled=True),
        )
        QuotaRegistry.set_quota_provider(
            _FixedPolicyProvider(QuotaPolicy(limits={}, retention_days=30))
        )
        db = real_commit_test_db
        org, user = _org(db, "Trace Ret Override Org", "trace-ret-override@test.com")
        project_id = _project(db, org)
        old_trace_id = _trace(db, org, project_id, created_at=_OLD)

        try:
            sweep_expired_traces()

            assert _trace_exists(db, old_trace_id), (
                "100-day-old trace should survive a 200-day override"
            )
        finally:
            QuotaRegistry.reset()


@pytest.mark.integration
class TestSweepOrgIsolation:
    def test_sweeping_one_org_never_touches_another_orgs_traces(
        self, monkeypatch, real_commit_test_db: Session
    ):
        """Regression guard: _sweep_organization uses an explicit
        organization_id filter. Without it, the delete under
        bypass_tenant_filter would wipe every org's expired traces."""
        _settings(monkeypatch, enabled=True)
        db = real_commit_test_db
        org_a, _ = _org(db, "Trace Iso Org A", "trace-iso-a@test.com")
        org_b, _ = _org(db, "Trace Iso Org B", "trace-iso-b@test.com")
        proj_a = _project(db, org_a)
        proj_b = _project(db, org_b)

        trace_a_id = _trace(db, org_a, proj_a, created_at=_OLD)
        trace_b_id = _trace(db, org_b, proj_b, created_at=_OLD)

        cutoff = _NOW - timedelta(days=30)
        trace_retention._sweep_organization(org_b, cutoff, dry_run=False)

        assert _trace_exists(db, trace_a_id), "sweeping org_b must not delete org_a's traces"
        assert not _trace_exists(db, trace_b_id)

    def test_one_organizations_failure_does_not_block_the_rest(
        self, monkeypatch, real_commit_test_db: Session
    ):
        _settings(monkeypatch, enabled=True)
        monkeypatch.setattr(
            "rhesis.backend.app.quota.get_application_settings",
            lambda: SimpleNamespace(usage_quotas_enabled=True),
        )
        QuotaRegistry.set_quota_provider(
            _FixedPolicyProvider(QuotaPolicy(limits={}, retention_days=30))
        )
        db = real_commit_test_db
        org_a, _ = _org(db, "Trace Fail Org A", "trace-fail-a@test.com")
        org_b, _ = _org(db, "Trace Fail Org B", "trace-fail-b@test.com")
        proj_a = _project(db, org_a)
        proj_b = _project(db, org_b)

        trace_a_id = _trace(db, org_a, proj_a, created_at=_OLD)
        trace_b_id = _trace(db, org_b, proj_b, created_at=_OLD)

        real_sweep = trace_retention._sweep_organization

        def flaky_sweep(org, cutoff, *, dry_run):
            if str(org.id) == str(org_a.id):
                raise RuntimeError("simulated failure")
            return real_sweep(org, cutoff, dry_run=dry_run)

        monkeypatch.setattr(trace_retention, "_sweep_organization", flaky_sweep)

        try:
            result = sweep_expired_traces()

            assert _trace_exists(db, trace_a_id), "org_a's failure is swallowed"
            assert not _trace_exists(db, trace_b_id), "org_b is still swept"
            assert result["orgs_failed"] >= 1, (
                "a failed org must be counted, not reported as a clean run"
            )
        finally:
            QuotaRegistry.reset()

    def test_a_failed_sweep_is_not_reported_as_a_clean_run(
        self, monkeypatch, real_commit_test_db: Session
    ):
        """_sweep_organization returns None on failure, not 0, so a run where
        every org errored is distinguishable from "nothing to delete" -- the
        two used to be identical in the returned dict."""
        _settings(monkeypatch, enabled=True)
        monkeypatch.setattr(
            "rhesis.backend.app.quota.get_application_settings",
            lambda: SimpleNamespace(usage_quotas_enabled=True),
        )
        QuotaRegistry.set_quota_provider(
            _FixedPolicyProvider(QuotaPolicy(limits={}, retention_days=30))
        )
        db = real_commit_test_db
        org, _ = _org(db, "Trace AllFail Org", "trace-allfail@test.com")
        project_id = _project(db, org)
        old_trace_id = _trace(db, org, project_id, created_at=_OLD)

        monkeypatch.setattr(
            trace_retention,
            "_sweep_organization",
            lambda org, cutoff, *, dry_run: None,
        )

        try:
            result = sweep_expired_traces()

            assert result["traces_affected"] == 0
            assert result["orgs_swept"] == 0
            assert result["orgs_failed"] >= 1
            assert _trace_exists(db, old_trace_id)
        finally:
            QuotaRegistry.reset()
