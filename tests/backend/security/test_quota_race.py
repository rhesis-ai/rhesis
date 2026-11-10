"""Concurrent requests must not all pass a quota check against the same usage.

Each thread uses its own connection through the production session path
(``get_db_with_tenant_variables``), against the real Postgres container, so
the database decides the outcome rather than a mock.
"""

from __future__ import annotations

import threading
import time
import uuid

import pytest
from sqlalchemy import text

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, enforce_quota
from rhesis.backend.app.services.usage import count_org_projects
from tests.backend.fixtures.database import AdminSessionLocal

_ADVISORY_LOCKS_HELD_BY_ME = text(
    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()"
)

N_REQUESTS = 8
LIMIT = 3
# Time between the check and the commit, wide enough that unserialized checks overlap.
WORK_SECONDS = 0.3


class _FixedPolicyProvider:
    def __init__(self, policy: QuotaPolicy):
        self._policy = policy

    def get_policy(self, org=None) -> QuotaPolicy:
        return self._policy


@pytest.fixture
def quota_policy():
    saved = QuotaRegistry._provider

    def install(policy: QuotaPolicy) -> None:
        QuotaRegistry.set_quota_provider(_FixedPolicyProvider(policy))

    yield install
    QuotaRegistry._provider = saved


@pytest.fixture
def race_org(real_commit_test_db) -> str:
    """A committed org of its own, so other tests' rows cannot move the count."""
    admin = AdminSessionLocal()
    try:
        org = Organization(name=f"quota-race-{uuid.uuid4().hex[:8]}")
        admin.add(org)
        admin.commit()
        org_id = str(org.id)
    finally:
        admin.close()
    real_commit_test_db.info["_owned_org_ids"].append(org_id)
    return org_id


def _race(worker, n: int = N_REQUESTS) -> list[str]:
    """Start *n* workers at once; return each one's outcome."""
    barrier = threading.Barrier(n)
    outcomes: list[str] = []
    lock = threading.Lock()

    def run():
        barrier.wait()
        try:
            worker()
            outcome = "ok"
        except QuotaExceededError:
            outcome = "quota"
        except Exception as exc:  # surfaced in the assertion message
            outcome = f"error: {exc!r}"
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=run) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "a request never finished"
    return outcomes


@pytest.mark.integration
class TestStockQuotaRace:
    def test_concurrent_creates_at_limit_yield_exactly_limit_successes(
        self, race_org, quota_policy
    ):
        quota_policy(
            QuotaPolicy(limits={QuotaResource.PROJECTS: LIMIT}, overage=OveragePolicy.HARD)
        )

        def create_project():
            # What the gated route does: check, then insert on the same session, then commit.
            with get_db_with_tenant_variables(race_org) as db:
                enforce_quota(db, race_org, None, QuotaResource.PROJECTS)
                time.sleep(WORK_SECONDS)
                db.add(Project(name=f"race-{uuid.uuid4().hex[:8]}", organization_id=race_org))
                db.flush()

        outcomes = _race(create_project)

        assert sorted(outcomes) == ["ok"] * LIMIT + ["quota"] * (N_REQUESTS - LIMIT), outcomes
        with get_db_with_tenant_variables(race_org) as db:
            assert count_org_projects(db, race_org) == LIMIT

    def test_soft_band_is_serialized_too(self, race_org, quota_policy):
        # 25% of 4 floors to 1: limit 4, ceiling 5.
        quota_policy(
            QuotaPolicy(
                limits={QuotaResource.PROJECTS: 4},
                overage=OveragePolicy.SOFT,
                overage_tolerance_percent=25,
            )
        )

        def create_project():
            with get_db_with_tenant_variables(race_org) as db:
                enforce_quota(db, race_org, None, QuotaResource.PROJECTS)
                time.sleep(WORK_SECONDS)
                db.add(Project(name=f"race-{uuid.uuid4().hex[:8]}", organization_id=race_org))
                db.flush()

        outcomes = _race(create_project)

        assert outcomes.count("ok") == 5, outcomes
        assert outcomes.count("quota") == N_REQUESTS - 5, outcomes

    def test_unlimited_takes_no_lock(self, race_org, quota_policy):
        quota_policy(QuotaPolicy(limits={QuotaResource.PROJECTS: None}))

        with get_db_with_tenant_variables(race_org) as db:
            enforce_quota(db, race_org, None, QuotaResource.PROJECTS)
            held = db.execute(_ADVISORY_LOCKS_HELD_BY_ME).scalar()

        assert held == 0
