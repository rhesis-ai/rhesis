"""Joining an organization requires the invited person to accept.

``POST /users/`` for an existing org-less account used to set its
``organization_id`` on the spot, pulling the account in by email alone. It now
issues an invitation instead: membership is granted only when the invited person
consumes the token from ``POST /auth/accept-invitation``, proving control of the
mailbox it was sent to. The token is single-use and expires.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/security/test_invitation_consent.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

from rhesis.backend.app import models
from rhesis.backend.app.auth.rbac import (
    DefaultAuthorizationProvider,
    get_authorization_provider,
    set_authorization_provider,
)
from rhesis.backend.app.auth.token_utils import (
    create_organization_invitation_token,
    get_jwt_algorithm,
    get_secret_key,
)
from rhesis.backend.app.scope import RequestScope, bypass_tenant_filter
from tests.backend.fixtures.test_setup import (
    create_test_organization_and_user,
    create_test_user,
)

pytestmark = [pytest.mark.security, pytest.mark.integration]


@pytest.fixture(autouse=True)
def _community_provider():
    previous = get_authorization_provider()
    set_authorization_provider(DefaultAuthorizationProvider())
    try:
        yield
    finally:
        set_authorization_provider(previous)


@pytest.fixture(autouse=True)
def _no_dns(monkeypatch):
    # The invite path validates the email's deliverability; skip the DNS check.
    monkeypatch.setattr(
        "rhesis.backend.app.routers.user.validate_and_normalize_email",
        lambda email, check_deliverability=False: email,
    )


@pytest.fixture(autouse=True)
def _single_use_store(monkeypatch):
    # The jti single-use mark lives in Redis; make the claim deterministic so the
    # tests exercise the attach logic, not the token store. Tests that need the
    # "already used" branch override this.
    monkeypatch.setattr(
        "rhesis.backend.app.routers.auth.claim_token_jti",
        AsyncMock(return_value=True),
    )


def _org_of(db, user_id):
    db.expire_all()
    with bypass_tenant_filter():
        user = db.query(models.User).filter_by(id=user_id).first()
        return user.organization_id if user is not None else None


@pytest.fixture
def ctx(test_db):
    suffix = f"{datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}"
    org, owner, owner_token = create_test_organization_and_user(
        test_db, f"Consent {suffix}", f"owner-{suffix}@rhesis-test.com", "Owner"
    )
    owner.is_email_verified = True

    # An existing account that left / was removed from an org (org-less).
    returning = create_test_user(test_db, None, f"returning-{suffix}@rhesis-test.com")
    returning.is_email_verified = True
    test_db.commit()
    return {
        "db": test_db,
        "org_id": org.id,
        "owner": owner,
        "returning": returning,
        "owner_auth": {"Authorization": f"Bearer {owner_token.token}"},
    }


@contextmanager
def _active(db, org_id, user):
    previous = db.info.get("_scope")
    db.info["_scope"] = RequestScope(
        organization_id=str(org_id),
        user_id=str(user.id),
        project_id=None,
    )
    try:
        yield
    finally:
        db.info["_scope"] = previous


def _token_from_invite_email(send_mock: MagicMock) -> str:
    """Pull the accept token out of the invitation email's action link."""
    assert send_mock.called, "an invitation email should have been sent"
    action_url = send_mock.call_args.kwargs["magic_link_url"]
    assert "/auth/accept-invitation" in action_url, action_url
    token = parse_qs(urlparse(action_url).query).get("token", [None])[0]
    assert token, action_url
    return token


def test_invite_does_not_attach_and_sends_accept_link(client, ctx, monkeypatch):
    """Inviting an existing org-less account issues a link instead of attaching it."""
    send_mock = MagicMock(return_value=True)
    email_mock = MagicMock(is_configured=True, send_team_invitation_email=send_mock)
    monkeypatch.setattr("rhesis.backend.app.routers.user.email_service", email_mock)

    with _active(ctx["db"], ctx["org_id"], ctx["owner"]):
        resp = client.post(
            "/users/",
            json={"email": ctx["returning"].email, "send_invite": True},
            headers=ctx["owner_auth"],
        )

    assert resp.status_code == 200, resp.text
    # The account is NOT pulled into the org by the invite itself.
    assert _org_of(ctx["db"], ctx["returning"].id) is None
    # The invitation email carries an accept link, not a bare attach.
    _token_from_invite_email(send_mock)


def test_accept_grants_membership_exactly_once(client, ctx):
    """Consuming the token attaches the account; a second use is refused."""
    token = create_organization_invitation_token(
        user_id=str(ctx["returning"].id),
        email=ctx["returning"].email,
        organization_id=str(ctx["org_id"]),
    )

    resp = client.post("/auth/accept-invitation", json={"token": token})
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    assert str(_org_of(ctx["db"], ctx["returning"].id)) == str(ctx["org_id"])

    # Second use: the account already belongs to the org, so it is refused even
    # if the token store would still accept the jti.
    resp2 = client.post("/auth/accept-invitation", json={"token": token})
    assert resp2.status_code == 409, resp2.text


def test_accept_rejects_expired_token(client, ctx):
    """An expired invitation cannot be accepted."""
    token = create_organization_invitation_token(
        user_id=str(ctx["returning"].id),
        email=ctx["returning"].email,
        organization_id=str(ctx["org_id"]),
        expire_minutes=-1,
    )

    resp = client.post("/auth/accept-invitation", json={"token": token})
    assert resp.status_code == 400, resp.text
    assert _org_of(ctx["db"], ctx["returning"].id) is None


def test_accept_rejects_already_claimed_token(client, ctx, monkeypatch):
    """A token whose single-use mark is already spent is refused."""
    monkeypatch.setattr(
        "rhesis.backend.app.routers.auth.claim_token_jti",
        AsyncMock(return_value=False),
    )
    token = create_organization_invitation_token(
        user_id=str(ctx["returning"].id),
        email=ctx["returning"].email,
        organization_id=str(ctx["org_id"]),
    )

    resp = client.post("/auth/accept-invitation", json={"token": token})
    assert resp.status_code == 400, resp.text
    assert "already used" in resp.json().get("detail", "").lower()
    assert _org_of(ctx["db"], ctx["returning"].id) is None


def test_accept_rejects_token_without_email_claim(client, ctx):
    """A decodable token missing the email claim is a 400, never a 500."""
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(ctx["returning"].id),
            "type": "organization_invitation",
            "organization_id": str(ctx["org_id"]),
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        get_secret_key(),
        algorithm=get_jwt_algorithm(),
    )

    resp = client.post("/auth/accept-invitation", json={"token": token})
    assert resp.status_code == 400, resp.text
    assert _org_of(ctx["db"], ctx["returning"].id) is None
