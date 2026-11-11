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
from datetime import datetime, timezone
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
    create_password_reset_token,
    create_session_token,
    get_jwt_algorithm,
    get_secret_key,
)
from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.schemas import UserCreate
from rhesis.backend.app.utils.encryption import hash_password
from tests.backend.fixtures.fake_redis import FakeRedis, fake_redis_manager

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
