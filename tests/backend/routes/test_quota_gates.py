"""Integration tests for :func:`~rhesis.backend.app.auth.quota_gates.require_quota`.

Goes through the real app and a real gated route (`POST /projects/`) rather
than a mocked-dependency mini-app, unlike `ee/licensing/test_feature_gates.py`
-- `require_quota` reads the FORCE-RLS'd `usage` table (for flow resources)
and a live `COUNT(*)` (for stock resources), and its own module docstring
explains why a GUC-less session would silently never block anyone. Only a
real tenant-scoped session (what `authenticated_client` gives us) exercises
that path honestly.

The org's real license/tier is irrelevant here: every test installs a fixed
`QuotaPolicy` directly via `QuotaRegistry`, the same technique
`test_quota_enforcement.py` uses, so these don't depend on which tier config
file happens to be active in the environment (`RHESIS_TIER_CONFIG` can point
anywhere -- see `tier_config.dev.yaml` for local low-limit testing).
"""

from __future__ import annotations

import pytest
from fastapi import Response, status
from fastapi.testclient import TestClient

from rhesis.backend.app.auth.quota_gates import QUOTA_WARNING_HEADER, require_quota
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.services.usage import increment_usage


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


def _project_payload() -> dict:
    import time

    return {"name": f"quota-gate-test-project-{int(time.time() * 1_000_000) % 1_000_000}"}


@pytest.fixture
def authenticated_org(test_db, test_org_id) -> Organization:
    return test_db.query(Organization).filter(Organization.id == test_org_id).one()


class TestRequireQuotaStockResource:
    """`POST /projects/` is gated on `QuotaResource.PROJECTS`, a stock (live
    COUNT) resource -- no accrual lag, so "already at the limit" is exactly
    "the next create is blocked", tested directly."""

    def test_under_the_limit_succeeds(self, authenticated_client: TestClient, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.PROJECTS: 1_000}))

        response = authenticated_client.post("/projects/", json=_project_payload())

        assert response.status_code == status.HTTP_200_OK

    def test_at_the_limit_returns_402(self, authenticated_client: TestClient, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.PROJECTS: 0}, overage=OveragePolicy.HARD))

        response = authenticated_client.post("/projects/", json=_project_payload())

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.PROJECTS.value
        assert body["limit"] == 0


class TestRequireQuotaFlowResourceWarningHeader:
    """The SOFT-policy grace band sets `QUOTA_WARNING_HEADER` on an allowed
    response, so a caller past the advertised limit is warned before the
    next request finally crosses the ceiling.

    Exercised by calling `require_quota`'s returned dependency directly
    (real `db`/`org`, no route needed) -- driving this through a real
    execute endpoint would mean standing up a full test-execution pipeline
    just to observe a response header. The HTTP wiring itself (the same
    dependency, reached via `Depends()`) is already covered end-to-end by
    `TestRequireQuotaStockResource` above.
    """

    def test_below_limit_sets_no_warning(
        self, test_db, test_org_id, authenticated_org, clean_registry
    ):
        _install(
            QuotaPolicy(
                limits={QuotaResource.TEST_EXECUTIONS: 100},
                overage=OveragePolicy.SOFT,
                overage_tolerance_percent=25,
            )
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 50)
        response = Response()

        dep = require_quota(QuotaResource.TEST_EXECUTIONS)
        dep(response=response, org=authenticated_org, db=test_db)

        assert QUOTA_WARNING_HEADER not in response.headers

    def test_in_the_grace_band_sets_the_warning_header(
        self, test_db, test_org_id, authenticated_org, clean_registry
    ):
        _install(
            QuotaPolicy(
                limits={QuotaResource.TEST_EXECUTIONS: 100},
                overage=OveragePolicy.SOFT,
                overage_tolerance_percent=25,
            )
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 110)
        response = Response()

        dep = require_quota(QuotaResource.TEST_EXECUTIONS)
        dep(response=response, org=authenticated_org, db=test_db)

        assert response.headers[QUOTA_WARNING_HEADER] == "test_executions=110/100"

    def test_at_the_ceiling_raises_instead_of_returning(
        self, test_db, test_org_id, authenticated_org, clean_registry
    ):
        from rhesis.backend.app.quota.enforcement import QuotaExceededError

        _install(
            QuotaPolicy(
                limits={QuotaResource.TEST_EXECUTIONS: 100},
                overage=OveragePolicy.SOFT,
                overage_tolerance_percent=25,
            )
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 125)
        response = Response()

        dep = require_quota(QuotaResource.TEST_EXECUTIONS)
        with pytest.raises(QuotaExceededError):
            dep(response=response, org=authenticated_org, db=test_db)
