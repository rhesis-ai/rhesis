"""Verify ``/auth/token-exchange`` is feature-gated at request time.

The endpoint's docstring promises gating via ``FeatureName.API_CLIENTS``,
and that promise was the kind of thing that's easy to lose: an org with
existing ``auth_client`` rows would otherwise keep exchanging tokens
forever, even after the feature was disabled in the license.

These tests pin the contract by driving ``run_token_exchange`` past
parse-validation and org resolution, then asserting the orchestrator
denies with ``invalid_target`` / ``feature_unavailable`` when the
registry reports the feature is not available for the resolved org.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.ee.sso.token_exchange.exchange import (
    TokenExchangeError,
    TokenExchangeRequest,
    run_token_exchange,
)
from rhesis.backend.ee.sso.token_exchange.schemas import (
    GRANT_TYPE_TOKEN_EXCHANGE,
    TOKEN_TYPE_ACCESS_TOKEN,
)


def _payload(**overrides) -> TokenExchangeRequest:
    base = dict(
        grant_type=GRANT_TYPE_TOKEN_EXCHANGE,
        subject_token="header.body.sig",
        subject_token_type=TOKEN_TYPE_ACCESS_TOKEN,
        audience="rhesis:org:acme",
        requested_token_type=None,
        scope=None,
        client_id="brain-prod",
        client_secret="s3cret",
    )
    base.update(overrides)
    return TokenExchangeRequest(**base)


def _live_org_with_sso():
    """Return a MagicMock that satisfies the org-resolution checks."""
    org = MagicMock()
    org.id = "00000000-0000-0000-0000-000000000001"
    org.slug = "acme"
    org.is_active = True
    org.sso_config = {"issuer_url": "https://idp.example.com"}
    return org


def _db_returning(org):
    """Return a MagicMock Session whose org-by-slug query yields *org*."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = org
    return db


@pytest.mark.asyncio
async def test_denies_when_feature_unavailable(monkeypatch):
    """When ``API_CLIENTS`` is not available for the org, the orchestrator
    raises ``invalid_target`` / ``feature_unavailable`` before client auth.

    Performing the check before client authentication is what stops the
    endpoint from leaking client existence: a feature-disabled org gets
    the same uniform rejection whether or not a matching ``auth_client``
    row exists.
    """
    monkeypatch.setattr(
        FeatureRegistry,
        "is_available",
        classmethod(lambda cls, name, org: False),
    )

    org = _live_org_with_sso()
    db = _db_returning(org)

    with pytest.raises(TokenExchangeError) as exc:
        await run_token_exchange(
            db,
            _payload(),
            sso_config_loader=lambda _org: object(),
        )
    assert exc.value.error == "invalid_target"
    assert exc.value.reason_code == "feature_unavailable"


@pytest.mark.asyncio
async def test_proceeds_past_feature_check_when_available(monkeypatch):
    """When the feature is available, the gating step does not fire and
    execution proceeds to the next ordered step (client authentication).

    We rig ``authenticate_client`` to return ``None`` so we can pin that
    the orchestrator made it that far without making this test depend on
    the full mint path.
    """
    monkeypatch.setattr(
        FeatureRegistry,
        "is_available",
        classmethod(lambda cls, name, org: True),
    )
    monkeypatch.setattr(
        "rhesis.backend.ee.sso.token_exchange.exchange.authenticate_client",
        lambda *a, **kw: None,
    )

    org = _live_org_with_sso()
    db = _db_returning(org)

    with pytest.raises(TokenExchangeError) as exc:
        await run_token_exchange(
            db,
            _payload(),
            sso_config_loader=lambda _org: object(),
        )
    # Reaching ``invalid_client`` (step 3) means we successfully passed
    # the feature gate (between step 2 and step 3) without raising.
    assert exc.value.error == "invalid_client"
    assert exc.value.reason_code == "client_auth_failed"


@pytest.mark.parametrize(
    "feature_name_str",
    [FeatureName.API_CLIENTS, "api_clients"],
)
def test_feature_name_resolution(feature_name_str):
    """The orchestrator queries the registry with ``FeatureName.API_CLIENTS``.

    Pinning the enum value here means a future rename of the feature
    string is a deliberate, test-visible change rather than a silent
    decoupling between the orchestrator and the registry.
    """
    assert FeatureName.API_CLIENTS == "api_clients"
    assert FeatureName(feature_name_str) == FeatureName.API_CLIENTS
