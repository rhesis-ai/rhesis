"""``last_used_at`` is stamped at most once per five minutes per token.

Every API-token request runs ``validate_token``, which used to assign
``last_used_at = now()`` unconditionally. That turned an authentication into a
write: an UPDATE plus the row lock it takes, inside the auth transaction, on
every single request from an SDK or CI job. The field is only ever read as
"was this token used recently", so a five-minute resolution loses nothing.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth import token_validation
from rhesis.backend.app.auth.token_validation import (
    TOKEN_USAGE_WRITE_INTERVAL,
    update_token_usage,
    validate_token,
)
from rhesis.backend.app.utils.encryption import hash_token


def _make_token(db: Session, org_id: str, user_id: str, *, last_used_at=None) -> models.Token:
    value = f"rh-{uuid.uuid4().hex}"
    token = models.Token(
        name="Debounce Token",
        token=value,
        token_hash=hash_token(value),
        token_obfuscated="rh-...test",
        token_type="bearer",
        organization_id=uuid.UUID(org_id),
        user_id=uuid.UUID(user_id),
        last_used_at=last_used_at,
    )
    db.add(token)
    db.flush()
    return token


class _UpdateCounter:
    """Count UPDATE statements against the token table."""

    def __init__(self) -> None:
        self.count = 0

    def __enter__(self) -> "_UpdateCounter":
        event.listen(Engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info) -> None:
        event.remove(Engine, "before_cursor_execute", self._record)

    def _record(self, conn, cursor, statement, parameters, context, executemany) -> None:
        collapsed = " ".join(statement.split()).lower()
        if collapsed.startswith("update token"):
            self.count += 1


@pytest.mark.unit
class TestTokenUsageDebounce:
    def test_interval_is_five_minutes(self):
        assert TOKEN_USAGE_WRITE_INTERVAL == timedelta(minutes=5)

    def test_first_use_stamps_the_token(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        token = _make_token(test_db, test_org_id, authenticated_user_id)

        update_token_usage(test_db, token)

        assert token.last_used_at is not None

    def test_recent_use_is_left_alone(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        recent = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = _make_token(test_db, test_org_id, authenticated_user_id, last_used_at=recent)

        update_token_usage(test_db, token)

        assert token.last_used_at == recent

    def test_stale_use_is_restamped(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        stale = datetime.now(timezone.utc) - timedelta(minutes=6)
        token = _make_token(test_db, test_org_id, authenticated_user_id, last_used_at=stale)

        update_token_usage(test_db, token)

        assert token.last_used_at > stale

    def test_naive_timestamp_is_read_as_utc(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Postgres can hand back a naive datetime; that must not look ancient."""
        naive_recent = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        token = _make_token(test_db, test_org_id, authenticated_user_id)
        token.last_used_at = naive_recent

        update_token_usage(test_db, token)

        assert token.last_used_at == naive_recent

    def test_two_validations_inside_the_interval_write_once(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """The whole point: back-to-back requests cost one UPDATE, not two."""
        token = _make_token(test_db, test_org_id, authenticated_user_id)

        with _UpdateCounter() as updates:
            assert validate_token(token, update_usage=True, db=test_db) == (True, None)
            test_db.flush()
            assert validate_token(token, update_usage=True, db=test_db) == (True, None)
            test_db.flush()

        assert updates.count == 1

    def test_a_validation_after_the_interval_writes_again(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, monkeypatch
    ):
        token = _make_token(test_db, test_org_id, authenticated_user_id)

        with _UpdateCounter() as updates:
            validate_token(token, update_usage=True, db=test_db)
            test_db.flush()

            later = datetime.now(timezone.utc) + TOKEN_USAGE_WRITE_INTERVAL + timedelta(seconds=1)

            class _FrozenDatetime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return later

            monkeypatch.setattr(token_validation, "datetime", _FrozenDatetime)
            validate_token(token, update_usage=True, db=test_db)
            test_db.flush()

        assert updates.count == 2
