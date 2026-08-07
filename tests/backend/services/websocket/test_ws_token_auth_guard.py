"""SP9 regression: POST /ws/token must be session-only.

A WebSocket token carries no scopes, so it resolves to a full-access *session*
principal on connect. Minting one from a scoped ``rh-*`` API token would let
that token escalate to full session access over the WebSocket transport,
bypassing SP9 scope enforcement. The endpoint must refuse token-authenticated
callers; API-token clients connect to ``/ws`` directly (scopes preserved).

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/services/websocket/test_ws_token_auth_guard.py -v
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from rhesis.backend.app.auth.principal import REQUEST_STATE_AUTH_KIND, AuthKind


@pytest.mark.asyncio
async def test_ws_token_denied_for_token_auth():
    """A request authenticated via an API token (auth_kind=TOKEN) is refused."""
    from rhesis.backend.app.routers.websocket import get_websocket_token

    request = SimpleNamespace(state=SimpleNamespace())
    setattr(request.state, REQUEST_STATE_AUTH_KIND, AuthKind.TOKEN)
    user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())

    with pytest.raises(HTTPException) as exc:
        get_websocket_token(request=request, current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_ws_token_allowed_for_session_auth():
    """A session-authenticated request (no auth_kind on state) still mints a token."""
    from rhesis.backend.app.routers import websocket as ws_router

    request = SimpleNamespace(state=SimpleNamespace())  # no auth_kind => session
    user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())

    stub = SimpleNamespace(
        create_ws_token=lambda user_id, org_id: "ws-token-xyz",
        WS_TOKEN_TTL_SECONDS=60,
    )
    with patch.object(ws_router, "get_ws_token_service", return_value=stub):
        resp = ws_router.get_websocket_token(request=request, current_user=user)

    assert resp.token == "ws-token-xyz"
    assert resp.expires_in == 60
