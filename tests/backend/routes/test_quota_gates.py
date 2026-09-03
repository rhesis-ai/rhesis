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

from rhesis.backend.app.auth.quota_gates import (
    QUOTA_WARNING_HEADER,
    require_backstop,
    require_quota,
)
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.services.usage import count_org_projects, count_org_seats, increment_usage


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
    "the next create is blocked".

    Both limits are derived from the org's *actual* project count rather than
    hardcoded. An earlier version used a fixed limit of 0 to block and 1,000
    to allow, which passed with the stock counters stubbed to return 0 --
    i.e. it proved nothing about whether the live count was ever read. Here a
    wrong count moves the boundary and both tests fail.
    """

    def test_one_below_the_limit_succeeds(
        self, authenticated_client: TestClient, test_db, test_org_id, clean_registry
    ):
        existing = count_org_projects(test_db, test_org_id)
        _install(
            QuotaPolicy(limits={QuotaResource.PROJECTS: existing + 1}, overage=OveragePolicy.HARD)
        )

        response = authenticated_client.post("/projects/", json=_project_payload())

        assert response.status_code == status.HTTP_200_OK

    def test_at_the_limit_returns_402(
        self, authenticated_client: TestClient, test_db, test_org_id, clean_registry
    ):
        test_db.add(Project(name="quota-gate-existing-project", organization_id=test_org_id))
        test_db.commit()
        existing = count_org_projects(test_db, test_org_id)
        assert existing >= 1, "fixture should leave at least the project just created"
        _install(QuotaPolicy(limits={QuotaResource.PROJECTS: existing}, overage=OveragePolicy.HARD))

        response = authenticated_client.post("/projects/", json=_project_payload())

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.PROJECTS.value
        assert body["limit"] == existing
        # The live count really was read, not defaulted to 0.
        assert body["used"] == existing


class TestSeatGateOnUserInvite:
    """`POST /users/` is the one gated route wrapped by
    `@handle_database_exceptions`, whose bare `except Exception` rewrites
    anything raised out of the route body into a 500.

    The gate survives that only because it runs as a `Depends()` -- FastAPI
    resolves dependencies before calling the decorated function, so
    `QuotaExceededError` never passes through the decorator and reaches the
    global 402 handler intact. Nothing else in the suite covers that, and
    reordering the decorator or inlining the check into the body would break
    it silently, so it is pinned here.
    """

    def test_at_the_seat_limit_returns_402(
        self, authenticated_client: TestClient, test_db, test_org_id, clean_registry
    ):
        existing = count_org_seats(test_db, test_org_id)
        _install(QuotaPolicy(limits={QuotaResource.SEATS: existing}, overage=OveragePolicy.HARD))

        response = authenticated_client.post(
            "/users/", json={"email": "quota-gate-invitee@example.com"}
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.SEATS.value
        assert body["used"] == existing

    def test_under_the_seat_limit_is_not_blocked_by_quota(
        self, authenticated_client: TestClient, test_db, test_org_id, clean_registry
    ):
        """Only asserts the quota gate did not fire -- the invite itself can
        still fail on email deliverability, which is not this gate's business."""
        existing = count_org_seats(test_db, test_org_id)
        _install(
            QuotaPolicy(limits={QuotaResource.SEATS: existing + 1}, overage=OveragePolicy.HARD)
        )

        response = authenticated_client.post(
            "/users/", json={"email": "quota-gate-invitee@example.com"}
        )

        assert response.status_code != status.HTTP_402_PAYMENT_REQUIRED, response.text


@pytest.fixture
def _bypass_model_validation():
    """Replace ``validate_execution_model`` and ``validate_generation_model``
    with no-ops so the quota gate is the first dependency that can block.

    Without this, FastAPI resolves model validation before the quota gate
    (signature order), and a missing/invalid model config would return 400
    before the gate ever fires -- hiding the thing under test.
    """
    from rhesis.backend.app.main import app
    from rhesis.backend.app.utils.execution_validation import (
        validate_execution_model,
        validate_generation_model,
    )

    app.dependency_overrides[validate_execution_model] = lambda: None
    app.dependency_overrides[validate_generation_model] = lambda: None
    yield
    app.dependency_overrides.pop(validate_execution_model, None)
    app.dependency_overrides.pop(validate_generation_model, None)


class TestFlowResourceQuotaGate:
    """Flow resources (TEST_EXECUTIONS, TEST_GENERATION) are period-scoped
    counters read from the ``usage`` table, not live ``COUNT(*)`` queries.
    The blocking arithmetic is identical to stock resources (same
    ``enforce_quota`` call), but the read path is different -- a missing or
    un-incremented ``usage`` row means the gate reads zero and never blocks.

    These tests seed the ``usage`` table via ``increment_usage``, then hit
    a real gated route through ``authenticated_client`` and assert 402.
    Model-validation dependencies are overridden to no-ops so the quota
    gate is the one that decides the response.
    """

    def test_execute_at_the_limit_returns_402(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
        _bypass_model_validation,
    ):
        limit = 10
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: limit}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, limit)

        response = authenticated_client.post(
            "/test_configurations/00000000-0000-0000-0000-000000000001/execute"
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.TEST_EXECUTIONS.value
        assert body["used"] == limit
        assert body["limit"] == limit

    def test_execute_under_the_limit_is_not_blocked(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
        _bypass_model_validation,
    ):
        """The gate passes; the route itself returns 404 (no such test config)
        -- that's fine, we only care that the quota gate did not fire."""
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 100}, overage=OveragePolicy.HARD)
        )

        response = authenticated_client.post(
            "/test_configurations/00000000-0000-0000-0000-000000000001/execute"
        )

        assert response.status_code != status.HTTP_402_PAYMENT_REQUIRED, response.text

    def test_generate_at_the_limit_returns_402(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
        _bypass_model_validation,
    ):
        limit = 5
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: limit}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_GENERATION, limit)

        response = authenticated_client.post("/test_sets/generate", json={"num_tests": 1})

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.TEST_GENERATION.value
        assert body["used"] == limit
        assert body["limit"] == limit

    def test_generate_under_the_limit_is_not_blocked(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
        _bypass_model_validation,
    ):
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: 100}, overage=OveragePolicy.HARD)
        )

        response = authenticated_client.post("/test_sets/generate", json={"num_tests": 1})

        assert response.status_code != status.HTTP_402_PAYMENT_REQUIRED, response.text

    def test_owasp_generate_at_the_limit_returns_402(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
        _bypass_model_validation,
    ):
        """`POST /owasp/generate` accrues against the same TEST_GENERATION
        quota as the plain generator (see tasks/test_set.py's
        dispatch_accrual call in generate_and_save_owasp_test_set) and must
        be gated the same way."""
        limit = 5
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: limit}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_GENERATION, limit)

        response = authenticated_client.post(
            "/owasp/generate", json={"purpose": "Customer service chatbot", "num_tests": 1}
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.TEST_GENERATION.value
        assert body["used"] == limit
        assert body["limit"] == limit

    def test_owasp_generate_under_the_limit_is_not_blocked(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
        _bypass_model_validation,
    ):
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: 100}, overage=OveragePolicy.HARD)
        )

        response = authenticated_client.post(
            "/owasp/generate", json={"purpose": "Customer service chatbot", "num_tests": 1}
        )

        assert response.status_code != status.HTTP_402_PAYMENT_REQUIRED, response.text

    def test_test_pipeline_at_the_limit_returns_402(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
    ):
        """`POST /services/generate/test_pipeline` streams the sample preview
        shown before a test set is actually created. It had no quota
        enforcement of its own, so an org already at its TEST_GENERATION
        limit could open the stream and start generating anyway."""
        limit = 5
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: limit}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_GENERATION, limit)

        response = authenticated_client.post(
            "/services/generate/test_pipeline", json={"prompt": "Test the login flow"}
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.TEST_GENERATION.value
        assert body["used"] == limit
        assert body["limit"] == limit

    def test_test_pipeline_under_the_limit_is_not_blocked(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
    ):
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: 100}, overage=OveragePolicy.HARD)
        )

        response = authenticated_client.post(
            "/services/generate/test_pipeline", json={"prompt": "Test the login flow"}
        )

        assert response.status_code != status.HTTP_402_PAYMENT_REQUIRED, response.text

    def test_generate_tests_at_the_limit_returns_402(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
        _bypass_model_validation,
    ):
        """`POST /services/generate/tests` is the non-streaming sample
        preview `handleRegenerateSample`/`handleLoadMoreSamples` call --
        it had neither a client-side check nor a require_quota gate."""
        limit = 5
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: limit}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_GENERATION, limit)

        response = authenticated_client.post(
            "/services/generate/tests",
            json={"config": {"requirements": ["Accuracy"]}, "num_tests": 1},
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.TEST_GENERATION.value

    def test_generate_multiturn_tests_at_the_limit_returns_402(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
        _bypass_model_validation,
    ):
        limit = 5
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: limit}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_GENERATION, limit)

        response = authenticated_client.post(
            "/services/generate/multiturn-tests",
            json={"generation_prompt": "Test a chatbot", "num_tests": 1},
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.TEST_GENERATION.value

    def test_generate_test_config_at_the_limit_returns_402(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        clean_registry,
    ):
        """`POST /services/generate/test_config` backs the config-only step
        of the same preview flow and was gated neither client- nor
        server-side."""
        limit = 5
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_GENERATION: limit}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_GENERATION, limit)

        response = authenticated_client.post(
            "/services/generate/test_config", json={"prompt": "Test the login flow"}
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        body = response.json()
        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.TEST_GENERATION.value


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


class TestRequireBackstopFailsOpen:
    """``require_backstop`` guards span ingest, whose contract is that a
    billing-side problem never breaks ingestion. These call the dependency
    callable directly: the branches under test are about what the *lookup*
    returns, so driving them through a real route would mean engineering a
    broken org row rather than simply handing one over.
    """

    def _dep(self, resource=QuotaResource.TRACING_SPANS):
        return require_backstop(resource)

    def test_a_missing_org_row_allows_the_request(self, test_db, test_org_id, clean_registry):
        """The regression this guards: falling through with ``org=None``
        resolves the *community* policy, so a possibly-paid org would be
        backstopped at 10x the free tier and 402 on ingest -- caused purely
        by a lookup that failed."""
        _install(QuotaPolicy(limits={QuotaResource.TRACING_SPANS: 1}))
        increment_usage(test_db, test_org_id, QuotaResource.TRACING_SPANS, 10_000)

        class _NoOrgSession:
            def get(self, *_args, **_kwargs):
                return None

        # Returns None (allows) rather than raising QuotaExceededError.
        assert self._dep()(tenant_context=(test_org_id, None), db=_NoOrgSession()) is None

    def test_no_org_in_context_allows_the_request(self, clean_registry):
        """Nothing to attribute usage to, so nothing to backstop."""
        _install(QuotaPolicy(limits={QuotaResource.TRACING_SPANS: 1}))

        assert self._dep()(tenant_context=(None, None), db=None) is None

    def test_a_lookup_that_raises_allows_the_request(self, clean_registry):
        """Fail-open covers the DB being unreachable, not just a null row."""
        _install(QuotaPolicy(limits={QuotaResource.TRACING_SPANS: 1}))

        class _BrokenSession:
            def get(self, *_args, **_kwargs):
                raise RuntimeError("connection reset")

        assert self._dep()(tenant_context=("some-org", None), db=_BrokenSession()) is None
