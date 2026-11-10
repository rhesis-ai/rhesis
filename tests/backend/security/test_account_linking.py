"""Linking a provider login to an existing account by email, and self-service profile edits.

An account registered with a password is not proof that the registrant owns the address.
When someone later proves ownership (OAuth, SSO, magic link), credentials set before
verification must stop working, and a provider that did not verify the address must not
link at all. Profile updates must not let a user set server-managed fields like
``email`` or ``is_email_verified``.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.providers.base import AuthUser
from rhesis.backend.app.auth.providers.github import GitHubProvider
from rhesis.backend.app.auth.providers.google import GoogleProvider
from rhesis.backend.app.auth.refresh_token_utils import create_refresh_token
from rhesis.backend.app.auth.token_utils import create_magic_link_token
from rhesis.backend.app.auth.user_utils import find_or_create_user_from_auth
from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.models.refresh_token import RefreshToken
from rhesis.backend.app.schemas import UserCreate
from rhesis.backend.app.utils.encryption import hash_password, verify_password
from tests.backend.fixtures.test_setup import create_test_api_token

PASSWORD = "Correct-Horse-Battery-9"


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def _local_user(db: Session, email: str, *, verified: bool) -> models.User:
    """A password account, as POST /auth/register leaves it (optionally verified)."""
    user = user_crud.create_user(
        db,
        UserCreate(
            email=email,
            password_hash=hash_password(PASSWORD),
            provider_type=AuthProviderType.EMAIL,
            is_active=True,
            is_email_verified=verified,
        ),
    )
    db.flush()
    return user


def _live_refresh_tokens(db: Session, user_id) -> int:
    return (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .count()
    )


def _api_tokens(db: Session, user_id) -> int:
    return db.query(models.Token).filter(models.Token.user_id == user_id).count()


def _google_user(email: str) -> AuthUser:
    return AuthUser(
        provider_type=AuthProviderType.GOOGLE,
        external_id=f"google-{uuid.uuid4().hex[:8]}",
        email=email,
        name="Address Owner",
    )


def _password_login(client: TestClient, email: str):
    return client.post("/auth/login/email", json={"email": email, "password": PASSWORD})


@pytest.mark.unit
@pytest.mark.security
class TestOAuthLinksUnverifiedAccount:
    def test_oauth_login_drops_credentials_set_before_verification(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        email = _email("prereg")
        user = _local_user(test_db, email, verified=False)
        user.organization_id = uuid.UUID(test_org_id)
        create_refresh_token(test_db, str(user.id))
        create_test_api_token(test_db, user, name="pre-verification token")
        test_db.flush()
        assert _live_refresh_tokens(test_db, user.id) == 1
        assert _api_tokens(test_db, user.id) == 1

        linked = find_or_create_user_from_auth(test_db, _google_user(email))
        test_db.flush()

        assert linked.id == user.id
        assert linked.is_email_verified is True
        assert linked.password_hash is None
        assert _live_refresh_tokens(test_db, user.id) == 0
        assert _api_tokens(test_db, user.id) == 0

        response = _password_login(client, email)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_oauth_login_keeps_password_of_verified_account(self, test_db: Session):
        email = _email("verified")
        user = _local_user(test_db, email, verified=True)
        create_refresh_token(test_db, str(user.id))
        test_db.flush()

        linked = find_or_create_user_from_auth(test_db, _google_user(email))

        assert linked.id == user.id
        assert linked.password_hash is not None
        assert verify_password(PASSWORD, linked.password_hash)
        assert _live_refresh_tokens(test_db, user.id) == 1

    def test_password_login_does_not_verify_email(self, client: TestClient, test_db: Session):
        email = _email("pwlogin")
        user = _local_user(test_db, email, verified=False)

        response = _password_login(client, email)
        assert response.status_code == status.HTTP_200_OK

        test_db.refresh(user)
        assert user.is_email_verified is False

    def test_magic_link_drops_credentials_set_before_verification(
        self, client: TestClient, test_db: Session
    ):
        email = _email("magic")
        user = _local_user(test_db, email, verified=False)
        create_refresh_token(test_db, str(user.id))
        test_db.flush()

        with (
            patch(
                "rhesis.backend.app.auth.token_utils.get_secret_key",
                return_value="test-secret",
            ),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            token = create_magic_link_token(str(user.id), user.email)
            response = client.post("/auth/magic-link/verify", json={"token": token})
        assert response.status_code == status.HTTP_200_OK

        test_db.refresh(user)
        assert user.is_email_verified is True
        assert user.password_hash is None
        # Only the refresh token this magic-link login just minted is live.
        assert _live_refresh_tokens(test_db, user.id) == 1
        assert _password_login(client, email).status_code == status.HTTP_401_UNAUTHORIZED


def _google_provider() -> tuple[GoogleProvider, MagicMock]:
    provider = GoogleProvider()
    oauth = MagicMock()
    provider._get_oauth = MagicMock(return_value=oauth)
    return provider, oauth


@pytest.mark.unit
@pytest.mark.security
class TestProviderMustVerifyEmail:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("claim", [False, None, "false"])
    async def test_google_rejects_unverified_email(self, claim):
        provider, oauth = _google_provider()
        userinfo = {"sub": "123", "email": "someone@example.com"}
        if claim is not None:
            userinfo["email_verified"] = claim
        oauth.google.authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})

        with patch.object(GoogleProvider, "is_enabled", True):
            with pytest.raises(HTTPException) as exc:
                await provider.authenticate(MagicMock())
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_google_accepts_verified_email(self):
        provider, oauth = _google_provider()
        userinfo = {"sub": "123", "email": "someone@example.com", "email_verified": True}
        oauth.google.authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})

        with patch.object(GoogleProvider, "is_enabled", True):
            auth_user = await provider.authenticate(MagicMock())
        assert auth_user.email == "someone@example.com"

    @staticmethod
    def _github(profile_email, emails):
        provider = GitHubProvider()
        oauth = MagicMock()
        provider._get_oauth = MagicMock(return_value=oauth)
        oauth.github.authorize_access_token = AsyncMock(return_value={"access_token": "t"})

        async def get(path, token):
            body = {"id": 1, "login": "octo", "email": profile_email} if path == "user" else emails
            return MagicMock(json=MagicMock(return_value=body))

        oauth.github.get = get
        return provider

    @pytest.mark.asyncio
    async def test_github_rejects_account_without_verified_email(self):
        provider = self._github(
            None, [{"email": "someone@example.com", "primary": True, "verified": False}]
        )
        with patch.object(GitHubProvider, "is_enabled", True):
            with pytest.raises(HTTPException) as exc:
                await provider.authenticate(MagicMock())
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_github_ignores_unverified_profile_email(self):
        provider = self._github(
            "unverified@example.com",
            [
                {"email": "unverified@example.com", "primary": False, "verified": False},
                {"email": "primary@example.com", "primary": True, "verified": True},
            ],
        )
        with patch.object(GitHubProvider, "is_enabled", True):
            auth_user = await provider.authenticate(MagicMock())
        assert auth_user.email == "primary@example.com"

    @pytest.mark.asyncio
    async def test_github_keeps_verified_profile_email(self):
        provider = self._github(
            "public@example.com",
            [
                {"email": "public@example.com", "primary": False, "verified": True},
                {"email": "primary@example.com", "primary": True, "verified": True},
            ],
        )
        with patch.object(GitHubProvider, "is_enabled", True):
            auth_user = await provider.authenticate(MagicMock())
        assert auth_user.email == "public@example.com"


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.ee
class TestSSOLinksUnverifiedAccount:
    def test_sso_login_drops_credentials_set_before_verification(
        self, test_db: Session, test_org_id: str
    ):
        sso_user_utils = pytest.importorskip("rhesis.backend.ee.sso.user_utils")
        from pydantic import SecretStr

        from rhesis.backend.ee.sso.schemas import SSOConfig

        email = _email("sso")
        user = _local_user(test_db, email, verified=False)
        user.organization_id = uuid.UUID(test_org_id)
        create_refresh_token(test_db, str(user.id))
        test_db.flush()
        org = test_db.query(models.Organization).filter_by(id=test_org_id).one()
        config = SSOConfig(
            issuer_url="https://idp.example.com",
            client_id="c",
            client_secret=SecretStr("s"),
        )
        auth_user = AuthUser(provider_type=AuthProviderType.OIDC, external_id="sub", email=email)

        linked = sso_user_utils.find_or_create_sso_user(test_db, auth_user, org, config)

        assert linked.id == user.id
        assert linked.is_email_verified is True
        assert linked.password_hash is None
        assert _live_refresh_tokens(test_db, user.id) == 0

    @pytest.mark.parametrize(
        "claims, unverified",
        [
            ({"email_verified": False}, True),
            ({"email_verified": "false"}, True),
            ({"email_verified": True}, False),
            ({}, False),
        ],
    )
    def test_oidc_email_verified_claim(self, claims, unverified):
        oidc = pytest.importorskip("rhesis.backend.ee.sso.oidc")
        assert oidc.email_marked_unverified(claims) is unverified
