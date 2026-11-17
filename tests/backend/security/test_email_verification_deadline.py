"""Unverified password accounts lose access after the grace period or a hard bounce."""

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth import email_verification
from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.email_verification import EMAIL_NOT_VERIFIED, EMAIL_UNDELIVERABLE
from rhesis.backend.app.auth.rbac import (
    DefaultAuthorizationProvider,
    get_authorization_provider,
    set_authorization_provider,
)
from rhesis.backend.app.auth.refresh_token_utils import create_refresh_token
from rhesis.backend.app.auth.token_utils import (
    create_password_reset_token,
    create_service_delegation_token,
    get_secret_key,
)
from rhesis.backend.app.auth.user_utils import get_authenticated_user_with_context
from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.schemas import UserCreate
from rhesis.backend.app.services.email_events import PUBLIC_KEY_ENV, record_bounces
from rhesis.backend.app.utils.encryption import hash_password
from tests.backend.fixtures.test_setup import (
    create_test_api_token,
    create_test_organization_and_user,
)

PASSWORD = "Correct-Horse-Battery-9"
WEBHOOK_PATH = "/webhooks/sendgrid/events"


@pytest.fixture(autouse=True)
def smtp_configured(monkeypatch):
    """The lock only applies where the verification mail can be sent."""
    monkeypatch.setattr(email_verification, "verification_enforced", lambda: True)


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def _password_user(
    db: Session,
    *,
    due_in: timedelta,
    verified: bool = False,
    bounced: bool = False,
    org_id: str | None = None,
) -> models.User:
    now = datetime.now(timezone.utc)
    user = user_crud.create_user(
        db,
        UserCreate(
            email=_email("deadline"),
            password_hash=hash_password(PASSWORD),
            provider_type=AuthProviderType.EMAIL,
            is_active=True,
            is_email_verified=verified,
            organization_id=uuid.UUID(org_id) if org_id else None,
        ),
    )
    user.email_verification_due_at = now + due_in
    user.email_bounced_at = now if bounced else None
    db.flush()
    return user


def _login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/auth/login/email", json={"email": email, "password": password})


@pytest.mark.unit
@pytest.mark.security
class TestPasswordLogin:
    def test_inside_grace_period_signs_in(self, client: TestClient, test_db: Session):
        user = _password_user(test_db, due_in=timedelta(days=2))
        assert _login(client, user.email).status_code == status.HTTP_200_OK

    def test_after_deadline_is_refused(self, client: TestClient, test_db: Session):
        user = _password_user(test_db, due_in=-timedelta(minutes=1))
        response = _login(client, user.email)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == EMAIL_NOT_VERIFIED

    def test_bounce_locks_before_deadline(self, client: TestClient, test_db: Session):
        user = _password_user(test_db, due_in=timedelta(days=2), bounced=True)
        response = _login(client, user.email)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == EMAIL_UNDELIVERABLE

    def test_not_enforced_without_smtp(self, client: TestClient, test_db: Session, monkeypatch):
        monkeypatch.setattr(email_verification, "verification_enforced", lambda: False)
        user = _password_user(test_db, due_in=-timedelta(days=1), bounced=True)
        assert _login(client, user.email).status_code == status.HTTP_200_OK

    def test_password_reset_verifies_and_unlocks(self, client: TestClient, test_db: Session):
        user = _password_user(test_db, due_in=-timedelta(days=1))
        new_password = "Another-Horse-Battery-7"
        with (
            patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value="test-secret"),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            token = create_password_reset_token(str(user.id), user.email)
            response = client.post(
                "/auth/reset-password", json={"token": token, "new_password": new_password}
            )
        assert response.status_code == status.HTTP_200_OK, response.text

        test_db.refresh(user)
        assert user.is_email_verified is True
        assert _login(client, user.email, new_password).status_code == status.HTTP_200_OK

    def test_wrong_password_still_401_after_deadline(self, client: TestClient, test_db: Session):
        user = _password_user(test_db, due_in=-timedelta(days=1))
        response = _login(client, user.email, "Wrong-Password-123")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verified_account_ignores_deadline(self, client: TestClient, test_db: Session):
        user = _password_user(test_db, due_in=-timedelta(days=1), verified=True, bounced=True)
        assert _login(client, user.email).status_code == status.HTTP_200_OK

    def test_registration_sets_deadline(self, client: TestClient, test_db: Session, monkeypatch):
        # Skip the MX lookup; example.com takes no mail.
        monkeypatch.setattr(
            "rhesis.backend.app.utils.validation.validate_and_normalize_email",
            lambda email, *args, **kwargs: email.lower(),
        )
        email = _email("register")
        response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
        assert response.status_code == status.HTTP_200_OK, response.text

        user = user_crud.get_user_by_email(test_db, email)
        assert user.is_email_verified is False
        remaining = user.email_verification_due_at - datetime.now(timezone.utc)
        assert timedelta(days=2, hours=23) < remaining <= timedelta(days=3)


@pytest.mark.unit
@pytest.mark.security
class TestExistingCredentials:
    def test_refresh_refused_after_deadline(self, client: TestClient, test_db: Session):
        user = _password_user(test_db, due_in=-timedelta(minutes=1))
        refresh = create_refresh_token(test_db, str(user.id))
        test_db.flush()

        response = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_works_inside_grace_period(self, client: TestClient, test_db: Session):
        user = _password_user(test_db, due_in=timedelta(days=1))
        refresh = create_refresh_token(test_db, str(user.id))
        test_db.flush()

        response = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert response.status_code == status.HTTP_200_OK

    def test_api_token_refused_after_deadline(
        self, client: TestClient, test_db: Session, test_org_id: str
    ):
        user = _password_user(test_db, due_in=-timedelta(minutes=1), org_id=test_org_id)
        token = create_test_api_token(test_db, user, name="locked")
        test_db.flush()

        response = client.get("/projects/", headers={"Authorization": f"Bearer {token.token}"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == EMAIL_NOT_VERIFIED

    @pytest.mark.asyncio
    async def test_job_delegation_token_outlives_deadline(self, test_db: Session, test_org_id: str):
        user = _password_user(test_db, due_in=-timedelta(minutes=1), org_id=test_org_id)
        token = create_service_delegation_token(user, "backend")
        request = Mock()
        request.session = {}
        request.state = SimpleNamespace()
        request.headers = {}
        request.client = None

        resolved = await get_authenticated_user_with_context(
            request,
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
            secret_key=get_secret_key(),
        )
        assert resolved is not None and resolved.id == user.id


@pytest.mark.unit
@pytest.mark.security
class TestInvites:
    @pytest.fixture
    def unverified_owner(self, test_db: Session):
        """An org owner inside the grace period, with community authz so the owner may invite."""
        previous = get_authorization_provider()
        set_authorization_provider(DefaultAuthorizationProvider())
        suffix = uuid.uuid4().hex[:8]
        _, owner, token = create_test_organization_and_user(
            test_db, f"Invites {suffix}", f"owner-{suffix}@rhesis-test.com", "Owner"
        )
        owner.is_email_verified = False
        owner.email_verification_due_at = datetime.now(timezone.utc) + timedelta(days=2)
        test_db.commit()
        try:
            yield {"Authorization": f"Bearer {token.token}"}
        finally:
            set_authorization_provider(previous)

    def test_unverified_owner_cannot_send_invite(
        self, client: TestClient, test_db: Session, unverified_owner
    ):
        invitee = _email("invitee")
        response = client.post(
            "/users/", json={"email": invitee, "send_invite": True}, headers=unverified_owner
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "verify your email" in response.json()["detail"].lower()
        assert user_crud.get_user_by_email(test_db, invitee) is None

    def test_unverified_owner_can_add_member_without_mail(
        self, client: TestClient, unverified_owner, monkeypatch
    ):
        monkeypatch.setattr(
            "rhesis.backend.app.routers.user.validate_and_normalize_email",
            lambda email, check_deliverability=False: email,
        )
        response = client.post(
            "/users/",
            json={"email": f"silent-{uuid.uuid4().hex[:8]}@rhesis-test.com", "send_invite": False},
            headers=unverified_owner,
        )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), response.text


def _signing_keys() -> tuple[ec.EllipticCurvePrivateKey, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    der = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, base64.b64encode(der).decode()


def _signed_post(client: TestClient, private_key, events: list[dict]):
    payload = json.dumps(events)
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    signature = private_key.sign((timestamp + payload).encode(), ec.ECDSA(hashes.SHA256()))
    return client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Twilio-Email-Event-Webhook-Signature": base64.b64encode(signature).decode(),
            "X-Twilio-Email-Event-Webhook-Timestamp": timestamp,
        },
    )


@pytest.mark.unit
@pytest.mark.security
class TestSendGridWebhook:
    def test_not_found_when_unconfigured(self, client: TestClient, monkeypatch):
        monkeypatch.delenv(PUBLIC_KEY_ENV, raising=False)
        assert client.post(WEBHOOK_PATH, json=[]).status_code == status.HTTP_404_NOT_FOUND

    def test_rejects_bad_signature(self, client: TestClient, monkeypatch):
        _, public_key = _signing_keys()
        other_key, _ = _signing_keys()
        monkeypatch.setenv(PUBLIC_KEY_ENV, public_key)
        response = _signed_post(client, other_key, [{"event": "bounce", "email": "x@y.com"}])
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rejects_unsigned(self, client: TestClient, monkeypatch):
        _, public_key = _signing_keys()
        monkeypatch.setenv(PUBLIC_KEY_ENV, public_key)
        assert client.post(WEBHOOK_PATH, json=[]).status_code == status.HTTP_401_UNAUTHORIZED

    def test_hard_bounce_locks_account(self, client: TestClient, test_db: Session, monkeypatch):
        private_key, public_key = _signing_keys()
        monkeypatch.setenv(PUBLIC_KEY_ENV, public_key)
        user = _password_user(test_db, due_in=timedelta(days=3))

        response = _signed_post(
            client,
            private_key,
            [{"event": "bounce", "type": "bounce", "email": user.email, "timestamp": 1}],
        )
        assert response.status_code == status.HTTP_200_OK

        test_db.refresh(user)
        assert user.email_bounced_at is not None
        assert _login(client, user.email).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.unit
class TestRecordBounces:
    @pytest.mark.parametrize(
        "event, counted",
        [
            ({"event": "bounce", "type": "bounce"}, True),
            ({"event": "bounce"}, True),
            ({"event": "bounce", "type": "blocked"}, False),
            ({"event": "dropped", "reason": "Bounced Address"}, True),
            ({"event": "dropped", "reason": "Unsubscribed Address"}, False),
            ({"event": "delivered"}, False),
        ],
    )
    def test_only_hard_bounces_count(self, test_db: Session, event: dict, counted: bool):
        user = _password_user(test_db, due_in=timedelta(days=3))
        assert record_bounces(test_db, [{**event, "email": user.email}]) == int(counted)

    def test_unknown_address_and_junk_are_ignored(self, test_db: Session):
        events = ["junk", {"event": "bounce"}, {"event": "bounce", "email": _email("nobody")}]
        assert record_bounces(test_db, events) == 0
