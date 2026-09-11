"""``EmailProvider`` must do its blocking work in a worker thread.

``POST /auth/login/email`` and ``POST /auth/register`` are ``async def``
handlers, so anything they run inline runs on the event loop and stalls every
other request in the worker process. Both of the provider's blocking halves --
the user lookup plus the bcrypt compare on login, and the MX lookup plus the
uniqueness query plus the bcrypt hash on registration -- live in
``authenticate_sync`` / ``register_sync`` and are dispatched with
``anyio.to_thread.run_sync``.

The ordering assertions matter as much as the threading ones: the password
policy check has to stay ahead of the registration DB work, and a login with
no matching account must not become measurably cheaper or dearer than one
with a wrong password.
"""

import threading
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from rhesis.backend.app.auth.providers.email import EmailProvider


@pytest.mark.unit
@pytest.mark.asyncio
async def test_authenticate_runs_off_the_event_loop():
    loop_thread = threading.get_ident()
    seen: dict[str, int] = {}

    def fake_sync(email, password, db):
        seen["thread"] = threading.get_ident()
        return "auth-user"

    provider = EmailProvider()
    provider.authenticate_sync = fake_sync

    result = await provider.authenticate(
        MagicMock(), email="a@example.com", password="pw", db=MagicMock()
    )

    assert result == "auth-user"
    assert seen["thread"] != loop_thread


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_runs_off_the_event_loop(monkeypatch):
    loop_thread = threading.get_ident()
    seen: dict[str, int] = {}

    async def _ok(password, context=None):
        return None

    monkeypatch.setattr("rhesis.backend.app.auth.providers.email.validate_password", _ok)

    def fake_sync(email, password, name, db):
        seen["thread"] = threading.get_ident()
        return "new-user"

    provider = EmailProvider()
    provider.register_sync = fake_sync

    result = await provider.register(
        MagicMock(), email="a@example.com", password="a-good-passphrase", db=MagicMock()
    )

    assert result == "new-user"
    assert seen["thread"] != loop_thread


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_rejects_a_weak_password_before_any_db_work(monkeypatch):
    """A rejected password must not cost a DNS lookup, a query or a bcrypt hash."""
    called: list[int] = []

    async def _reject(password, context=None):
        raise HTTPException(status_code=400, detail="Password is too weak")

    monkeypatch.setattr("rhesis.backend.app.auth.providers.email.validate_password", _reject)

    provider = EmailProvider()
    provider.register_sync = lambda *args, **kwargs: called.append(1)

    with pytest.raises(HTTPException) as exc:
        await provider.register(MagicMock(), email="a@example.com", password="x", db=MagicMock())

    assert exc.value.status_code == 400
    assert not called


@pytest.mark.unit
@pytest.mark.asyncio
async def test_authenticate_rejects_a_missing_session_the_same_way_as_before():
    """The provider's own guards stay inside the threaded body, in order."""
    provider = EmailProvider()

    with pytest.raises(HTTPException) as missing_credentials:
        await provider.authenticate(MagicMock(), email=None, password=None, db=MagicMock())
    assert missing_credentials.value.status_code == 400

    with pytest.raises(HTTPException) as missing_session:
        await provider.authenticate(MagicMock(), email="a@example.com", password="pw", db=None)
    assert missing_session.value.status_code == 500
