"""Request provenance: who made a request, and how it reached the backend."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from starlette.requests import HTTPConnection

from rhesis.backend.app.auth.user_utils import get_authenticated_user_with_context
from rhesis.backend.app.provenance import (
    ActorType,
    Channel,
    ProvenanceMiddleware,
    attach_current_request,
    bind_job_provenance,
    client_channel,
    in_process_headers,
    provenance_of,
    record_credential,
    resolve_provenance,
)
from rhesis.backend.app.utils.rate_limit import CLIENT_IP_HEADER, get_real_ip
from rhesis.backend.app.utils.request_context import RequestIDMiddleware


def _connection(headers=None, peer="10.0.0.5", state=None) -> HTTPConnection:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (peer, 1234) if peer else None,
        "state": state or {},
    }
    return HTTPConnection(scope)


def _session():
    return SimpleNamespace(info={})


class TestInClusterClientIp:
    def test_private_peer_without_forwarded_for_is_trusted(self):
        request = _connection({CLIENT_IP_HEADER: "203.0.113.7"}, peer="10.0.0.5")
        assert get_real_ip(request) == "203.0.113.7"

    def test_loopback_peer_is_trusted(self):
        request = _connection({CLIENT_IP_HEADER: "203.0.113.7"}, peer="127.0.0.1")
        assert get_real_ip(request) == "203.0.113.7"

    def test_ignored_when_the_request_came_through_the_ingress(self):
        request = _connection(
            {CLIENT_IP_HEADER: "203.0.113.7", "X-Forwarded-For": "198.51.100.9"},
            peer="10.0.0.5",
        )
        assert get_real_ip(request) == "198.51.100.9"

    def test_ignored_from_a_public_peer(self):
        request = _connection({CLIENT_IP_HEADER: "203.0.113.7"}, peer="8.8.8.8")
        assert get_real_ip(request) == "8.8.8.8"

    def test_ignored_when_not_an_ip(self):
        request = _connection({CLIENT_IP_HEADER: "not-an-ip"}, peer="10.0.0.5")
        assert get_real_ip(request) == "10.0.0.5"


class TestClientChannel:
    @pytest.mark.parametrize("claimed", ["web", "sdk", "mcp", "architect", " SDK "])
    def test_known_clients(self, claimed):
        assert client_channel(_connection({"X-Rhesis-Client": claimed})).value == (
            claimed.strip().lower()
        )

    @pytest.mark.parametrize("headers", [{}, {"X-Rhesis-Client": "curl"}])
    def test_anything_else_is_plain_api(self, headers):
        assert client_channel(_connection(headers)) is Channel.API

    def test_a_client_cannot_claim_to_be_a_job(self):
        assert client_channel(_connection({"X-Rhesis-Client": "job"})) is Channel.API


class TestResolveProvenance:
    def test_unauthenticated_request_is_anonymous(self):
        provenance = resolve_provenance(_connection({"User-Agent": "curl/8"}))
        assert provenance.actor_type is ActorType.ANONYMOUS
        assert provenance.actor_id is None
        assert provenance.user_agent == "curl/8"

    def test_authenticated_user_defaults_to_user(self):
        request = _connection(state={"user": SimpleNamespace(id="u-1"), "request_id": "r-1"})
        provenance = resolve_provenance(request)
        assert provenance.actor_type is ActorType.USER
        assert provenance.actor_id == "u-1"
        assert provenance.request_id == "r-1"

    def test_recorded_credential_is_used(self):
        request = _connection(state={"user": SimpleNamespace(id="u-1")})
        record_credential(request, ActorType.API_TOKEN, "tok-1", "rh-...7f2a")
        provenance = resolve_provenance(request)
        assert provenance.actor_type is ActorType.API_TOKEN
        assert (provenance.credential_id, provenance.credential_hint) == ("tok-1", "rh-...7f2a")


class TestProvenanceOf:
    def test_none_outside_a_request_or_job(self):
        assert provenance_of(_session()) is None

    def test_job_binding_wins_over_a_request(self):
        session = _session()
        session.info["_provenance_request"] = _connection()
        bind_job_provenance(session, user_id="u-1", job_id="j-1", request_id="r-1")
        provenance = provenance_of(session)
        assert provenance.actor_type is ActorType.SYSTEM
        assert provenance.channel is Channel.JOB
        assert (provenance.actor_id, provenance.job_id, provenance.request_id) == (
            "u-1",
            "j-1",
            "r-1",
        )

    def test_attach_does_nothing_outside_a_request(self):
        session = _session()
        attach_current_request(session)
        assert session.info == {}


class TestInProcessHeaders:
    def test_passes_on_the_original_client(self):
        request = _connection(
            {"User-Agent": "Cursor/1.0"}, peer="10.0.0.5", state={"request_id": "r-9"}
        )
        headers = in_process_headers(Channel.MCP, request)
        assert headers == {
            "X-Rhesis-Client": "mcp",
            CLIENT_IP_HEADER: "10.0.0.5",
            "User-Agent": "Cursor/1.0",
            "X-Request-ID": "r-9",
        }

    def test_without_a_request_only_names_the_channel(self):
        assert in_process_headers(Channel.ARCHITECT) == {"X-Rhesis-Client": "architect"}


def test_sessions_opened_during_a_request_see_the_authenticated_actor():
    """End to end through the middleware: the session is opened before auth runs
    (in the threadpool), and still reports the actor and the request id."""
    app = FastAPI()
    session = _session()

    def open_session():
        attach_current_request(session)
        return session

    def authenticate(request: Request):
        request.state.user = SimpleNamespace(id="u-7")
        record_credential(request, ActorType.API_TOKEN, "tok-7", "rh-...0000")

    @app.get("/probe")
    def probe(db=Depends(open_session), _auth=Depends(authenticate)):
        provenance = provenance_of(db)
        return {
            "actor_type": str(provenance.actor_type),
            "actor_id": provenance.actor_id,
            "credential_id": provenance.credential_id,
            "channel": str(provenance.channel),
            "request_id": provenance.request_id,
        }

    app.add_middleware(ProvenanceMiddleware)
    app.add_middleware(RequestIDMiddleware)

    response = TestClient(app).get(
        "/probe", headers={"X-Rhesis-Client": "sdk", "X-Request-ID": "req-123"}
    )
    assert response.json() == {
        "actor_type": "api_token",
        "actor_id": "u-7",
        "credential_id": "tok-7",
        "channel": "sdk",
        "request_id": "req-123",
    }


@pytest.mark.asyncio
async def test_api_token_auth_records_the_token(test_db, rhesis_api_key):
    request = Mock()
    request.session = {}
    request.state = SimpleNamespace()
    request.headers = {}
    request.client = None

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=rhesis_api_key)
    user = await get_authenticated_user_with_context(request, credentials=credentials)

    provenance = resolve_provenance(request)
    assert provenance.actor_type is ActorType.API_TOKEN
    assert provenance.actor_id == str(user.id)
    assert provenance.credential_id
    assert provenance.credential_hint.startswith(rhesis_api_key[:3])
    assert provenance.credential_hint.endswith(rhesis_api_key[-4:])
