"""Unit tests for :mod:`rhesis.backend.ee.api_clients.refresh_minter`.

The module-private ``_strip_offline_access`` helper is the
security-relevant unit here: ``offline_access`` is an OIDC
convention for "give me a refresh token", not an authority. The
access token's ``scope`` claim must NOT carry it (or a future
per-route scope check might mistakenly grant it as an authority),
but the persisted refresh row MUST keep it so re-rotation preserves
the original intent.

``TestMintForClientBoundRefresh`` covers the sibling regression this
module is exposed to for ``project_id``: without re-minting it from
``old_token.project_id`` on every rotation, a token-exchange-issued
access token's ``project`` claim would work until the first refresh
and vanish silently after.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest

from rhesis.backend.app.auth.token_utils import get_jwt_algorithm
from rhesis.backend.ee.api_clients.refresh_minter import (
    _strip_offline_access,
    mint_for_client_bound_refresh,
)

SECRET = "test-secret-key-for-tests"


def _basic_auth_header(client_id: str, client_secret: str = "s3cret") -> str:
    raw = f"{client_id}:{client_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


@pytest.mark.parametrize(
    "given,expected",
    [
        ("full offline_access", "full"),
        ("read offline_access", "read"),
        ("offline_access full", "full"),
        ("read full offline_access", "read full"),
        ("full", "full"),
        ("offline_access", None),  # only offline_access -> nothing left
    ],
)
def test_strips_offline_access_token(given: str, expected: str | None) -> None:
    assert _strip_offline_access(given) == expected


def test_none_input_passes_through() -> None:
    """UI/SSO refresh rows have NULL scope; the helper must not coerce that."""
    assert _strip_offline_access(None) is None


def test_empty_string_passes_through() -> None:
    assert _strip_offline_access("") == ""


def test_does_not_strip_substrings() -> None:
    """``offline_access_v2`` is a different scope; substring match would be wrong."""
    assert _strip_offline_access("full offline_access_v2") == (
        "full offline_access_v2"
    )


@pytest.mark.unit
@patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
class TestMintForClientBoundRefresh:
    """``db`` is unused when ``authenticate_client`` is mocked, so a bare
    ``None`` stands in for it -- the function never touches it directly."""

    def _auth_client(self, **overrides):
        base = dict(
            client_id="warehouse-sync",
            organization_id="22222222-2222-2222-2222-222222222222",
            token_epoch=0,
            disabled=False,
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def _old_token(self, **overrides):
        base = dict(
            client_id="warehouse-sync",
            scope="read",
            project_id="33333333-3333-3333-3333-333333333333",
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def _user(self, **overrides):
        base = dict(
            id="11111111-1111-1111-1111-111111111111",
            organization_id="22222222-2222-2222-2222-222222222222",
            email="user@example.com",
            name="Test User",
            picture=None,
            is_email_verified=True,
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def _request(self, client_id: str = "warehouse-sync") -> SimpleNamespace:
        return SimpleNamespace(
            headers=SimpleNamespace(get=lambda name: _basic_auth_header(client_id))
        )

    def test_project_id_reminted_on_rotation(self, mock_secret) -> None:
        old_token = self._old_token()
        with patch(
            "rhesis.backend.ee.api_clients.refresh_minter.authenticate_client",
            return_value=self._auth_client(),
        ):
            access_token = mint_for_client_bound_refresh(
                db=None,
                request=self._request(),
                old_token=old_token,
                user=self._user(),
            )

        payload = jwt.decode(
            access_token,
            SECRET,
            algorithms=[get_jwt_algorithm()],
            options={"verify_exp": False, "verify_aud": False},
        )
        assert payload["project"] == old_token.project_id

    def test_no_project_claim_when_old_token_has_none(self, mock_secret) -> None:
        old_token = self._old_token(project_id=None)
        with patch(
            "rhesis.backend.ee.api_clients.refresh_minter.authenticate_client",
            return_value=self._auth_client(),
        ):
            access_token = mint_for_client_bound_refresh(
                db=None,
                request=self._request(),
                old_token=old_token,
                user=self._user(),
            )

        payload = jwt.decode(
            access_token,
            SECRET,
            algorithms=[get_jwt_algorithm()],
            options={"verify_exp": False, "verify_aud": False},
        )
        assert "project" not in payload
