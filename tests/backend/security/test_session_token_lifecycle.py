"""Session and token lifecycle: what logout, password reset/change and one-time links revoke.

- Logout and password change mark a user's session JWTs as revoked in Redis, so every
  pod rejects them on every request, and a later login does not undo the mark.
- Password reset and change revoke refresh tokens; change hands the caller a new pair.
- Only an interactive session can change or set a password, not an API token.
- A scoped token cannot mint a token wider than itself by leaving out ``scopes``.
- An email-verification link signs the user in at most once.
- A WebSocket token is single-use across processes.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import anyio
import jwt
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth import session_invalidation
from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.refresh_token_utils import create_refresh_token
from rhesis.backend.app.auth.token_utils import (
    create_email_verification_token,
    create_password_reset_token,
    create_service_delegation_token,
    create_session_token,
    get_jwt_algorithm,
    get_secret_key,
)
from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.schemas import UserCreate
from rhesis.backend.app.services.websocket.token_service import WebSocketTokenService
from rhesis.backend.app.utils.encryption import hash_password
from tests.backend.fixtures.fake_redis import FakeRedis, fake_redis_manager
from tests.backend.fixtures.test_setup import create_test_api_token

PASSWORD = "Correct-Horse-Battery-9"
NEW_PASSWORD = "Another-Long-Passphrase-42"


def _user(db: Session, org_id: str, *, password: bool = True) -> models.User:
    user = user_crud.create_user(
        db,
        UserCreate(
            email=f"lifecycle-{uuid.uuid4().hex[:10]}@example.com",
            password_hash=hash_password(PASSWORD) if password else None,
            provider_type=AuthProviderType.EMAIL if password else AuthProviderType.GOOGLE,
            is_active=True,
            is_email_verified=True,
            organization_id=uuid.UUID(org_id),
        ),
    )
    db.flush()
    return user


def _aged(token: str, seconds: int = 5) -> str:
    """Re-sign ``token`` as if it had been issued ``seconds`` ago."""
    payload = jwt.decode(
        token, get_secret_key(), algorithms=[get_jwt_algorithm()], options={"verify_aud": False}
    )
    payload["iat"] = int(payload["iat"]) - seconds
    return jwt.encode(payload, get_secret_key(), algorithm=get_jwt_algorithm())


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _api_ok(client: TestClient, token: str) -> int:
    return client.get("/users/settings", headers=_bearer(token)).status_code


def _logout(client: TestClient, token: str):
    return client.get("/auth/logout", headers={**_bearer(token), "Accept": "application/json"})


def _refresh(client: TestClient, refresh_token: str) -> int:
    return client.post("/auth/refresh", json={"refresh_token": refresh_token}).status_code


@pytest.mark.unit
@pytest.mark.security
class TestLogoutRevokesSessionJwts:
    def test_logged_out_jwt_is_rejected_on_api_routes(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        token = _aged(create_session_token(user))
        with fake_redis_manager():
            assert _api_ok(client, token) == status.HTTP_200_OK
            assert _logout(client, token).status_code == status.HTTP_200_OK
            assert _api_ok(client, token) == status.HTTP_401_UNAUTHORIZED

    def test_revocation_lives_in_redis_with_a_ttl(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        token = _aged(create_session_token(user))
        with fake_redis_manager() as redis:
            _logout(client, token)
        key = f"{session_invalidation.KEY_PREFIX}{user.id}"
        assert key in redis.data
        assert redis.ttls[key] > 0

    def test_mark_from_another_process_is_honoured(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        """Nothing is cached per process: a mark written elsewhere applies here."""
        user = _user(test_db, test_org_id)
        token = _aged(create_session_token(user))
        redis = FakeRedis()
        redis.data[f"{session_invalidation.KEY_PREFIX}{user.id}"] = str(
            int(datetime.now(timezone.utc).timestamp())
        )
        with fake_redis_manager(redis):
            assert _api_ok(client, token) == status.HTTP_401_UNAUTHORIZED
            assert _api_ok(client, create_session_token(user)) == status.HTTP_200_OK

    def test_login_after_logout_does_not_revive_old_jwts(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        old = _aged(create_session_token(user))
        with fake_redis_manager():
            _logout(client, old)
            login = client.post(
                "/auth/login/email", json={"email": user.email, "password": PASSWORD}
            )
            assert login.status_code == status.HTTP_200_OK
            exchanged = client.post("/auth/exchange-code", json={"code": login.json()["auth_code"]})
            new = exchanged.json()["session_token"]
            # Login also sets the backend session cookie; test the bearer JWTs alone.
            client.cookies.clear()

            assert _api_ok(client, new) == status.HTTP_200_OK
            assert _api_ok(client, old) == status.HTTP_401_UNAUTHORIZED

    def test_verify_endpoint_rejects_logged_out_jwt(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        token = _aged(create_session_token(user))
        with fake_redis_manager():
            _logout(client, token)
            response = client.post("/auth/verify", json={"session_token": token})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_existing_sessions_survive_when_nothing_was_revoked(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        """No mark means valid: a deploy with an empty Redis logs nobody out."""
        user = _user(test_db, test_org_id)
        token = _aged(create_session_token(user), seconds=600)
        with fake_redis_manager():
            assert _api_ok(client, token) == status.HTTP_200_OK

    def test_redis_down_fails_open(self, client: TestClient, test_db: Session, test_org_id: str):
        user = _user(test_db, test_org_id)
        token = _aged(create_session_token(user))
        with fake_redis_manager(available=False):
            assert _logout(client, token).status_code == status.HTTP_200_OK
            assert _api_ok(client, token) == status.HTTP_200_OK

    def test_slow_redis_does_not_stall_requests(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        class Hung(FakeRedis):
            async def get(self, key):
                await anyio.sleep(30)

        user = _user(test_db, test_org_id)
        token = create_session_token(user)
        with (
            fake_redis_manager(Hung()),
            patch.object(session_invalidation, "LOOKUP_TIMEOUT_SECONDS", 0.05),
        ):
            assert _api_ok(client, token) == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_check_never_waits_on_a_reconnect(self):
        """A down Redis is reported unavailable at once, without a connect attempt."""
        with fake_redis_manager(available=False):
            from rhesis.backend.app.services.connector.redis_client import redis_manager

            with patch.object(redis_manager, "initialize", new_callable=AsyncMock) as connect:
                assert await session_invalidation.is_session_revoked("user-1", 0) is False
            connect.assert_not_called()


@pytest.mark.unit
@pytest.mark.security
class TestPasswordResetAndChangeRevokeTokens:
    def test_reset_revokes_refresh_tokens_and_sessions(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        refresh = create_refresh_token(test_db, str(user.id))
        session = _aged(create_session_token(user))
        test_db.flush()
        reset = create_password_reset_token(str(user.id), user.email)

        with (
            fake_redis_manager(),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            response = client.post(
                "/auth/reset-password", json={"token": reset, "new_password": NEW_PASSWORD}
            )
            assert response.status_code == status.HTTP_200_OK
            assert _refresh(client, refresh) == status.HTTP_401_UNAUTHORIZED
            assert _api_ok(client, session) == status.HTTP_401_UNAUTHORIZED

    def test_change_revokes_other_refresh_tokens_and_keeps_caller_signed_in(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        other_refresh = create_refresh_token(test_db, str(user.id))
        session = _aged(create_session_token(user))
        test_db.flush()

        with fake_redis_manager():
            response = client.post(
                "/auth/change-password",
                headers=_bearer(session),
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            )
            assert response.status_code == status.HTTP_200_OK
            body = response.json()

            assert _refresh(client, other_refresh) == status.HTTP_401_UNAUTHORIZED
            assert _api_ok(client, session) == status.HTTP_401_UNAUTHORIZED

            exchanged = client.post("/auth/exchange-code", json={"code": body["auth_code"]}).json()
            assert _api_ok(client, exchanged["session_token"]) == status.HTTP_200_OK
            assert _refresh(client, exchanged["refresh_token"]) == status.HTTP_200_OK
            assert _api_ok(client, body["session_token"]) == status.HTTP_200_OK


@pytest.mark.unit
@pytest.mark.security
class TestChangePasswordNeedsInteractiveSession:
    def _set_password(self, client: TestClient, token: str):
        return client.post(
            "/auth/change-password", headers=_bearer(token), json={"new_password": NEW_PASSWORD}
        )

    def test_api_token_cannot_set_a_password(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id, password=False)
        api_token = create_test_api_token(test_db, user, name="scoped").token
        response = self._set_password(client, api_token)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        test_db.refresh(user)
        assert user.password_hash is None

    def test_exchanged_jwt_cannot_set_a_password(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id, password=False)
        token = create_session_token(user, azp="test-client", epoch=0, scope="openid")
        assert self._set_password(client, token).status_code == status.HTTP_403_FORBIDDEN

    def test_service_delegation_jwt_cannot_set_a_password(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id, password=False)
        token = create_service_delegation_token(user, "backend")
        assert self._set_password(client, token).status_code == status.HTTP_403_FORBIDDEN

    def test_session_jwt_can_set_a_password(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id, password=False)
        with fake_redis_manager():
            response = self._set_password(client, create_session_token(user))
        assert response.status_code == status.HTTP_200_OK
        test_db.refresh(user)
        assert user.password_hash is not None


@pytest.mark.unit
@pytest.mark.security
class TestScopedTokenMint:
    def test_omitted_scopes_inherit_the_callers_scopes(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        parent = create_test_api_token(test_db, user, name="parent")
        parent.scopes = ["token:create", "token:read"]
        test_db.flush()

        response = client.post("/tokens/", headers=_bearer(parent.token), json={"name": "child"})

        assert response.status_code == status.HTTP_200_OK, response.text
        child = test_db.query(models.Token).filter(models.Token.id == response.json()["id"]).one()
        assert child.scopes is not None
        assert set(child.scopes) == {"token:create", "token:read"}

    def test_unscoped_caller_still_mints_unscoped(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        parent = create_test_api_token(test_db, user, name="parent")

        response = client.post("/tokens/", headers=_bearer(parent.token), json={"name": "child"})

        assert response.status_code == status.HTTP_200_OK, response.text
        child = test_db.query(models.Token).filter(models.Token.id == response.json()["id"]).one()
        assert child.scopes is None


@pytest.mark.unit
@pytest.mark.security
class TestScopedTokenRefresh:
    def _tokens(self, db: Session, org_id: str, target_scopes):
        user = _user(db, org_id)
        caller = create_test_api_token(db, user, name="caller")
        caller.scopes = ["token:create", "token:read"]
        target = create_test_api_token(db, user, name="target")
        target.scopes = target_scopes
        db.flush()
        return caller, target

    def _refresh_token(self, client: TestClient, caller, target):
        return client.post(f"/tokens/{target.id}/refresh", headers=_bearer(caller.token), json={})

    def test_scoped_token_cannot_refresh_an_unscoped_token(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        caller, target = self._tokens(test_db, test_org_id, None)
        old_hash = target.token_hash

        response = self._refresh_token(client, caller, target)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        test_db.refresh(target)
        assert target.token_hash == old_hash

    def test_scoped_token_cannot_refresh_a_wider_token(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        caller, target = self._tokens(test_db, test_org_id, ["token:create", "token:delete"])
        response = self._refresh_token(client, caller, target)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_scoped_token_can_refresh_a_token_within_its_scopes(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        caller, target = self._tokens(test_db, test_org_id, ["token:read"])
        response = self._refresh_token(client, caller, target)
        assert response.status_code == status.HTTP_200_OK, response.text

    def test_project_bound_token_cannot_refresh_another_projects_token(self):
        from fastapi import HTTPException

        from rhesis.backend.app.auth.principal import AuthKind, Principal
        from rhesis.backend.app.routers.token import _check_refresh_allowed

        principal = Principal(
            uuid.uuid4(), uuid.uuid4(), AuthKind.TOKEN, scopes=None, token_project_id=uuid.uuid4()
        )
        for project_id in (None, uuid.uuid4()):
            target = models.Token(scopes=None, project_id=project_id)
            with pytest.raises(HTTPException) as exc:
                _check_refresh_allowed(target, principal, db=None)
            assert exc.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.unit
@pytest.mark.security
class TestCookieSessionRevocation:
    def _login(self, client: TestClient, user: models.User):
        response = client.post(
            "/auth/login/email", json={"email": user.email, "password": PASSWORD}
        )
        assert response.status_code == status.HTTP_200_OK
        assert client.cookies.get("session")

    def _revoke_after_now(self, redis: FakeRedis, user: models.User):
        later = int(datetime.now(timezone.utc).timestamp()) + 5
        redis.data[f"{session_invalidation.KEY_PREFIX}{user.id}"] = str(later)

    def test_revoked_cookie_session_is_rejected_and_cleared(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        with fake_redis_manager() as redis:
            self._login(client, user)
            assert client.get("/users/settings").status_code == status.HTTP_200_OK

            self._revoke_after_now(redis, user)
            assert client.get("/users/settings").status_code == status.HTTP_401_UNAUTHORIZED

            redis.data.clear()
            # The session was cleared, so lifting the mark doesn't bring it back.
            assert client.get("/users/settings").status_code == status.HTTP_401_UNAUTHORIZED

    def test_cookie_session_survives_when_nothing_was_revoked(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _user(test_db, test_org_id)
        with fake_redis_manager():
            self._login(client, user)
            assert client.get("/users/settings").status_code == status.HTTP_200_OK

    def test_revocation_outlives_every_cookie_session(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        """The cookie slides while in use, so the mark must last as long as its cap."""
        from rhesis.backend.app.auth.constants import AUTH_ABSOLUTE_SESSION_MAX_DAYS

        user = _user(test_db, test_org_id)
        token = _aged(create_session_token(user))
        with fake_redis_manager() as redis:
            _logout(client, token)
        key = f"{session_invalidation.KEY_PREFIX}{user.id}"
        assert redis.ttls[key] >= AUTH_ABSOLUTE_SESSION_MAX_DAYS * 86400

    @pytest.mark.asyncio
    async def test_cookie_session_past_its_absolute_cap_is_rejected(
        self, test_db: Session, test_org_id: str
    ):
        from types import SimpleNamespace

        from rhesis.backend.app.auth import user_utils
        from rhesis.backend.app.auth.constants import AUTH_ABSOLUTE_SESSION_MAX_DAYS

        user = _user(test_db, test_org_id)
        too_old = int(datetime.now(timezone.utc).timestamp()) - (
            AUTH_ABSOLUTE_SESSION_MAX_DAYS * 86400 + 60
        )
        request = SimpleNamespace(session={"user_id": str(user.id), "iat": too_old})
        with fake_redis_manager():
            assert await user_utils.get_current_user(request) is None
        assert request.session == {}

    @pytest.mark.asyncio
    async def test_cookie_without_issue_time_is_stamped_not_dropped(
        self, test_db: Session, test_org_id: str
    ):
        """A cookie from before issue times existed keeps working and gets one."""
        from types import SimpleNamespace

        from rhesis.backend.app.auth import user_utils

        user = _user(test_db, test_org_id)
        request = SimpleNamespace(session={"user_id": str(user.id)})
        with fake_redis_manager():
            assert (await user_utils.get_current_user(request)).id == user.id
        assert request.session["iat"] == session_invalidation.PROCESS_STARTED_AT

    @pytest.mark.asyncio
    async def test_cookie_without_issue_time_honours_later_revocation(
        self, test_db: Session, test_org_id: str
    ):
        from types import SimpleNamespace

        from rhesis.backend.app.auth import user_utils

        user = _user(test_db, test_org_id)
        request = SimpleNamespace(session={"user_id": str(user.id)})
        redis = FakeRedis()
        redis.data[f"{session_invalidation.KEY_PREFIX}{user.id}"] = str(
            session_invalidation.PROCESS_STARTED_AT + 1
        )
        with fake_redis_manager(redis):
            assert await user_utils.get_current_user(request) is None
        assert request.session == {}


@pytest.mark.unit
@pytest.mark.security
class TestEmailVerificationLinkIsSingleUse:
    def _unverified(self, db: Session, org_id: str) -> models.User:
        user = _user(db, org_id)
        user.is_email_verified = False
        db.flush()
        return user

    def test_second_use_does_not_sign_in(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = self._unverified(test_db, test_org_id)
        token = create_email_verification_token(str(user.id), user.email)
        with fake_redis_manager():
            first = client.post("/auth/verify-email", json={"token": token})
            second = client.post("/auth/verify-email", json={"token": token})

        assert first.status_code == status.HTTP_200_OK
        assert first.json().get("auth_code")
        assert second.status_code == status.HTTP_200_OK
        assert "auth_code" not in second.json()
        test_db.refresh(user)
        assert user.is_email_verified is True

    def test_link_without_jti_verifies_but_does_not_sign_in(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        """Links mailed before single-use existed still verify the address."""
        user = self._unverified(test_db, test_org_id)
        now = datetime.now(timezone.utc)
        legacy = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "type": "email_verification",
                "iat": now,
                "exp": now + timedelta(hours=1),
            },
            get_secret_key(),
            algorithm=get_jwt_algorithm(),
        )
        with fake_redis_manager():
            response = client.post("/auth/verify-email", json={"token": legacy})
        assert response.status_code == status.HTTP_200_OK
        assert "auth_code" not in response.json()
        test_db.refresh(user)
        assert user.is_email_verified is True

    def test_redis_down_verifies_but_does_not_sign_in(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = self._unverified(test_db, test_org_id)
        token = create_email_verification_token(str(user.id), user.email)
        with fake_redis_manager(available=False):
            response = client.post("/auth/verify-email", json={"token": token})
        assert response.status_code == status.HTTP_200_OK
        assert "auth_code" not in response.json()
        test_db.refresh(user)
        assert user.is_email_verified is True


@pytest.mark.unit
@pytest.mark.security
class TestWebSocketTokenSingleUseAcrossProcesses:
    @pytest.mark.asyncio
    async def test_token_used_on_one_process_is_rejected_on_another(self):
        pod_a = WebSocketTokenService(secret_key="ws-secret")
        pod_b = WebSocketTokenService(secret_key="ws-secret")
        token = pod_a.create_ws_token(user_id=str(uuid.uuid4()), org_id=str(uuid.uuid4()))

        with fake_redis_manager():
            assert await pod_a.validate_ws_token(token) is not None
            assert await pod_b.validate_ws_token(token) is None

    @pytest.mark.asyncio
    async def test_redis_down_still_single_use_per_process(self):
        service = WebSocketTokenService(secret_key="ws-secret")
        token = service.create_ws_token(user_id=str(uuid.uuid4()), org_id=str(uuid.uuid4()))

        with fake_redis_manager(available=False):
            assert await service.validate_ws_token(token) is not None
            assert await service.validate_ws_token(token) is None
