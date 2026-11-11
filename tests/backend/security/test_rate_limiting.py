"""Rate limits are shared across workers, mounted on every route, and per user
on the costly ones.

The suite runs with ``RATELIMIT_ENABLED=false`` (see tests/backend/conftest.py);
tests here switch the limiter on and key every counter on a fresh IP or user so
the shared Redis never carries counts between tests.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from limits.storage import RedisStorage
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.wrappers import LimitGroup
from starlette.requests import Request as StarletteRequest

from rhesis.backend.app.main import app
from rhesis.backend.app.utils import rate_limit
from rhesis.backend.app.utils.rate_limit import (
    DefaultRateLimitMiddleware,
    get_real_ip,
    get_user_identifier,
    hit_post_parse_limit,
    limiter,
    rate_limit_ip_key,
)

BACKEND_DIR = Path(__file__).resolve().parents[3] / "apps" / "backend"

# Routes that call an LLM, call a user's endpoint, or start a job.
COSTLY_ROUTES = [
    ("POST", "/endpoints/test"),
    ("POST", "/endpoints/auto-configure"),
    ("POST", "/endpoints/{endpoint_id}/invoke"),
    ("POST", "/endpoints/{endpoint_id}/explore"),
    ("POST", "/test_sets/generate"),
    ("POST", "/test_sets/{test_set_identifier}/execute/{endpoint_id}"),
    ("POST", "/test_configurations/{test_configuration_id}/execute"),
    ("POST", "/tests/execute"),
    ("POST", "/garak/import"),
    ("POST", "/garak/sync/{test_set_id}"),
    ("POST", "/garak/generate"),
    ("POST", "/owasp/generate"),
    ("GET", "/services/github/contents"),
    ("POST", "/services/generate/content"),
    ("POST", "/services/generate/embedding"),
    ("POST", "/services/generate/tests"),
    ("POST", "/services/generate/multiturn-tests"),
    ("POST", "/services/generate/test_pipeline"),
    ("POST", "/services/generate/test_config"),
    ("POST", "/services/mcp/query"),
    ("POST", "/import/analyze"),
    ("POST", "/models/test-connection"),
    ("POST", "/tools/test-connection"),
    ("POST", "/metrics/generate"),
    ("POST", "/metrics/{metric_id}/improve"),
    ("POST", "/metrics/{metric_id}/tuning/run"),
    ("POST", "/metrics/{metric_id}/tuning/improve"),
    ("POST", "/explorer/{test_set_identifier}/generate_outputs"),
    ("POST", "/explorer/{test_set_identifier}/evaluate"),
    ("POST", "/explorer/{test_set_identifier}/generate_suggestions"),
    ("POST", "/explorer/{test_set_identifier}/generate_suggestion_outputs"),
    ("POST", "/explorer/{test_set_identifier}/suggestion_pipeline"),
    ("POST", "/explorer/{test_set_identifier}/evaluate_suggestions"),
    ("POST", "/tests/{test_id}/interpretation"),
    ("POST", "/tests/extract-from-conversation"),
    ("POST", "/test_runs/{test_run_id}/rescore"),
    ("POST", "/preflight-checks"),
    ("POST", "/connector/trigger"),
    ("POST", "/sources/{source_id}/embeddings/compute-graph"),
    ("POST", "/test_sets/{test_set_identifier}/embeddings/compute-graph"),
    ("POST", "/tools/{tool_id}/extract"),
]

# Handlers that call one of these directly start a job, call a model or call a
# user's endpoint. A new one fails the gate below until it gets a per-user limit
# or a reason here.
COSTLY_CALLS = {
    "launch_job",
    "delay",
    "apply_async",
    "invoke_endpoint",
    "invoke_endpoint_off_loop",
    "invoke_endpoint_for_suggestions_stream",
    "resolve_model",
    "build_model_or_raise",
    "a_generate",
    "generate",
}
COSTLY_CALL_EXEMPT = {
    # Text extraction for uploaded files, bounded by the upload size cap.
    "routers/file.py:upload_files",
    # SDK span export, metered by the tracing quota.
    "routers/telemetry.py:ingest_trace",
}
ROUTER_DIRS = [
    BACKEND_DIR / "src" / "rhesis" / "backend" / "app" / "routers",
    BACKEND_DIR.parents[1] / "ee" / "backend" / "src" / "rhesis" / "backend" / "ee",
]

AUTH_ROUTE_FUNCTIONS = [
    "rhesis.backend.app.routers.auth.reset_password",
    "rhesis.backend.app.routers.auth.verify_magic_link",
    "rhesis.backend.app.routers.auth.refresh_tokens",
    "rhesis.backend.app.routers.auth.local_login",
]

EXEMPT_FUNCTIONS = [
    "rhesis.backend.app.main.root",
    "rhesis.backend.app.main.health_check",
    "rhesis.backend.app.main.readiness_check",
    "rhesis.backend.app.routers.telemetry.ingest_trace",
]


def _fresh_ip() -> str:
    """A TEST-NET address unique enough that no other test shares its bucket."""
    n = uuid.uuid4().int
    return f"198.51.{(n >> 8) % 256}.{n % 256}"


def _find_route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"{method} {path} is not registered")


def _has_per_user_limit(dependant) -> bool:
    for dep in dependant.dependencies:
        name = getattr(dep.call, "__qualname__", "")
        if name.startswith("per_user_rate_limit.") or _has_per_user_limit(dep):
            return True
    return False


@pytest.fixture
def limiter_on(monkeypatch):
    monkeypatch.setattr(limiter, "enabled", True)


# --- shared storage -------------------------------------------------------------


def test_limiter_counts_live_in_redis():
    assert isinstance(limiter._storage, RedisStorage)
    assert rate_limit.rate_limit_storage_uri().endswith("/11")


def test_counts_are_shared_across_processes(limiter_on):
    """A second process (another gunicorn worker or pod) sees the same count."""
    namespace = "shared-count-test"
    key = uuid.uuid4().hex
    script = (
        "from rhesis.backend.app.utils.rate_limit import hit_post_parse_limit\n"
        f"for _ in range(3): hit_post_parse_limit('3/minute', namespace={namespace!r}, "
        f"key={key!r})\n"
    )
    env = {**os.environ, "RATELIMIT_ENABLED": "true"}
    subprocess.run(
        [sys.executable, "-c", script], cwd=BACKEND_DIR, env=env, check=True, timeout=120
    )

    with pytest.raises(HTTPException) as exc:
        hit_post_parse_limit("3/minute", namespace=namespace, key=key)
    assert exc.value.status_code == 429


def test_unreachable_redis_falls_back_to_memory(monkeypatch):
    """Requests keep working with Redis down, still limited per process."""
    offline = rate_limit.build_limiter("redis://127.0.0.1:1/11")
    offline.enabled = True
    monkeypatch.setattr(rate_limit, "limiter", offline)
    key = uuid.uuid4().hex

    rate_limit.hit_post_parse_limit("2/minute", namespace="fallback-test", key=key)
    rate_limit.hit_post_parse_limit("2/minute", namespace="fallback-test", key=key)
    with pytest.raises(HTTPException):
        rate_limit.hit_post_parse_limit("2/minute", namespace="fallback-test", key=key)
    assert offline._storage_dead


def test_unreachable_redis_keeps_routes_serving():
    offline = rate_limit.build_limiter("redis://127.0.0.1:1/11")
    offline.enabled = True
    mini = FastAPI()
    mini.state.limiter = offline
    mini.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    mini.add_middleware(DefaultRateLimitMiddleware)

    @mini.get("/limited")
    @offline.limit("2/minute")
    def limited(request: Request):
        return {"ok": True}

    @mini.get("/default")
    def default(request: Request):
        return {"ok": True}

    with TestClient(mini) as c:
        assert [c.get("/limited").status_code for _ in range(3)] == [200, 200, 429]
        assert c.get("/default").status_code == 200
    assert offline._storage_dead


# --- default limit on every route ------------------------------------------------


def test_default_limit_middleware_is_registered():
    assert DefaultRateLimitMiddleware in [m.cls for m in app.user_middleware]


def test_default_limit_middleware_passes_streamed_responses_through():
    """A response sent in several chunks arrives whole (file downloads, SSE)."""
    memory = rate_limit.build_limiter("memory://")
    memory.enabled = True
    mini = FastAPI()
    mini.state.limiter = memory
    mini.add_middleware(DefaultRateLimitMiddleware)

    @mini.get("/stream")
    def stream():
        return StreamingResponse(iter([b"a", b"b", b"c"]))

    with TestClient(mini) as c:
        response = c.get("/stream")
    assert response.status_code == 200
    assert response.content == b"abc"


def test_default_limit_applies_to_undecorated_routes(limiter_on, monkeypatch):
    monkeypatch.setattr(
        limiter,
        "_default_limits",
        [LimitGroup("2/minute", rate_limit_ip_key, None, False, None, None, None, 1, False)],
    )
    headers = {"X-Forwarded-For": _fresh_ip()}
    with TestClient(app) as c:
        codes = [c.get("/auth/providers", headers=headers).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_health_and_trace_ingest_skip_the_default_limit(limiter_on, monkeypatch):
    for name in EXEMPT_FUNCTIONS:
        assert name in limiter._exempt_routes, name
    monkeypatch.setattr(
        limiter,
        "_default_limits",
        [LimitGroup("1/minute", rate_limit_ip_key, None, False, None, None, None, 1, False)],
    )
    headers = {"X-Forwarded-For": _fresh_ip()}
    with TestClient(app) as c:
        codes = [c.get("/health", headers=headers).status_code for _ in range(3)]
    assert 429 not in codes


# --- auth routes ------------------------------------------------------------------


@pytest.mark.parametrize("name", AUTH_ROUTE_FUNCTIONS)
def test_auth_route_has_its_own_limit(name):
    assert limiter._route_limits.get(name), f"{name} has no rate limit"


# --- per-user limits on costly routes --------------------------------------------


@pytest.mark.parametrize(("method", "path"), COSTLY_ROUTES)
def test_costly_route_has_per_user_limit(method, path):
    assert _has_per_user_limit(_find_route(method, path).dependant), f"{method} {path}"


def test_costly_route_is_limited_per_user(limiter_on, authenticated_client):
    """The 21st generation call in a minute is refused."""
    headers = {"X-Forwarded-For": _fresh_ip()}

    def call() -> int:
        # An empty body is a 422 once the limit check has passed, so nothing is generated.
        return authenticated_client.post(
            "/services/generate/tests", json={}, headers=headers
        ).status_code

    codes = [call() for _ in range(21)]
    assert codes[:20] == [422] * 20
    assert codes[20] == 429


def test_per_user_limit_keys_on_the_account(limiter_on):
    """Users behind one IP each get their own bucket, per route."""
    from rhesis.backend.app.dependencies import per_user_rate_limit

    check = per_user_rate_limit("1/minute").dependency
    route = SimpleNamespace(path=f"/limited/{uuid.uuid4().hex}")
    request = StarletteRequest({"type": "http", "headers": [], "route": route})
    alice, bob = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())

    check(request, alice)
    check(request, bob)
    with pytest.raises(HTTPException) as exc:
        check(request, alice)
    assert exc.value.status_code == 429


def _route_handlers(tree):
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            func = getattr(dec, "func", None)
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "router"
                and func.attr in {"get", "post", "put", "patch", "delete"}
            ):
                yield node, dec


def _called_names(node):
    for call in ast.walk(node):
        if isinstance(call, ast.Call):
            func = call.func
            yield func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)


def test_every_route_with_a_costly_call_has_a_per_user_limit():
    missing = []
    for root in ROUTER_DIRS:
        assert root.is_dir(), root
        for path in root.rglob("*.py"):
            for handler, decorator in _route_handlers(ast.parse(path.read_text())):
                if not COSTLY_CALLS.intersection(_called_names(handler)):
                    continue
                label = f"{path.parent.name}/{path.name}:{handler.name}"
                if label in COSTLY_CALL_EXEMPT:
                    continue
                if "per_user_rate_limit" not in ast.unparse(decorator):
                    missing.append(label)
    assert not missing, f"costly routes without per_user_rate_limit: {missing}"


# --- user_limiter key -------------------------------------------------------------


def _request_as(user_id: str | None) -> StarletteRequest:
    request = StarletteRequest(
        {"type": "http", "headers": [], "client": ("10.0.0.5", 1234), "state": {}}
    )
    if user_id:
        request.state.user = SimpleNamespace(id=user_id)
    return request


def test_ratelimit_enabled_env_turns_the_limiter_off(monkeypatch):
    monkeypatch.setenv("RATELIMIT_ENABLED", "false")
    assert not rate_limit.build_limiter("memory://").enabled
    monkeypatch.setenv("RATELIMIT_ENABLED", "true")
    assert rate_limit.build_limiter("memory://").enabled


def test_user_key_is_read_after_auth_dependencies_run():
    """The decorator's key_func sees request.state.user set by the auth dependency."""
    memory = rate_limit.build_limiter("memory://")
    memory.enabled = True
    mini = FastAPI()
    mini.state.limiter = memory
    mini.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    def fake_auth(request: Request, x_user: str = Header()):
        request.state.user = SimpleNamespace(id=x_user)

    @mini.post("/invite", dependencies=[Depends(fake_auth)])
    @memory.limit("1/minute", key_func=get_user_identifier)
    def invite(request: Request):
        return {"ok": True}

    with TestClient(mini) as c:
        assert c.post("/invite", headers={"x-user": "a"}).status_code == 200
        assert c.post("/invite", headers={"x-user": "b"}).status_code == 200
        assert c.post("/invite", headers={"x-user": "a"}).status_code == 429


def test_invite_route_limit_keys_on_the_inviter(
    limiter_on, monkeypatch, authenticated_client, authenticated_user_id, quotas_disabled
):
    """POST /users/ counts against the signed-in user, not the client IP."""
    from unittest.mock import patch

    name = "rhesis.backend.app.routers.user.create_user"
    one_per_minute = list(
        LimitGroup("1/minute", get_user_identifier, None, False, None, None, None, 1, True)
    )
    monkeypatch.setitem(limiter._route_limits, name, one_per_minute)
    headers = {"X-Forwarded-For": _fresh_ip()}

    def invite() -> int:
        body = {"email": f"invite_{uuid.uuid4().hex[:10]}@rhesis-test.com", "name": "Invitee"}
        return authenticated_client.post("/users/", json=body, headers=headers).status_code

    # Earlier tests in this worker may have used the window; start from a clean one.
    limiter.limiter.clear(one_per_minute[0].limit, f"user:{authenticated_user_id}", name)
    with patch(
        "rhesis.backend.app.routers.user.validate_and_normalize_email",
        side_effect=lambda email, check_deliverability=False: email,
    ):
        assert invite() in (200, 201)
        assert invite() == 429
    stats = limiter.limiter.get_window_stats(
        one_per_minute[0].limit, f"user:{authenticated_user_id}", name
    )
    assert stats.remaining == 0


def test_user_identifier_keys_on_the_signed_in_account():
    """Two users behind the same proxy get separate invitation buckets."""
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    assert get_user_identifier(_request_as(a)) == f"user:{a}"
    assert get_user_identifier(_request_as(a)) != get_user_identifier(_request_as(b))
    assert get_user_identifier(_request_as(None)) == "10.0.0.5"


# --- IPv6 keys -------------------------------------------------------------------


def _request_from(xff: str) -> StarletteRequest:
    return StarletteRequest(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", xff.encode())],
            "client": ("203.0.113.9", 443),
            "state": {},
        }
    )


def test_ipv6_addresses_in_one_slash_64_share_a_key():
    a = rate_limit_ip_key(_request_from("2001:db8:1:2::1"))
    b = rate_limit_ip_key(_request_from("2001:db8:1:2:ffff:abcd:1234:5678"))
    assert a == b == "2001:db8:1:2::/64"


def test_different_ipv6_slash_64s_get_different_keys():
    a = rate_limit_ip_key(_request_from("2001:db8:1:2::1"))
    b = rate_limit_ip_key(_request_from("2001:db8:1:3::1"))
    assert a != b


def test_ipv4_keys_are_unchanged():
    assert rate_limit_ip_key(_request_from("198.51.100.7")) == "198.51.100.7"
    assert rate_limit_ip_key(_request_from("198.51.100.8")) == "198.51.100.8"
    # IPv4-mapped IPv6 keys on the IPv4 address, not on the shared ::ffff:0:0/64.
    assert rate_limit_ip_key(_request_from("::ffff:198.51.100.7")) == "198.51.100.7"


def test_get_real_ip_still_returns_the_full_address():
    assert get_real_ip(_request_from("2001:db8:1:2::1")) == "2001:db8:1:2::1"
    assert get_real_ip(_request_from("198.51.100.7")) == "198.51.100.7"


def test_ipv6_rotation_within_a_slash_64_shares_one_bucket(limiter_on, monkeypatch):
    monkeypatch.setattr(
        limiter,
        "_default_limits",
        [LimitGroup("2/minute", rate_limit_ip_key, None, False, None, None, None, 1, False)],
    )
    prefix = f"2001:db8:{uuid.uuid4().int % 65536:x}:{uuid.uuid4().int % 65536:x}"
    with TestClient(app) as c:
        codes = [
            c.get(
                "/auth/providers", headers={"X-Forwarded-For": f"{prefix}::{i + 1:x}"}
            ).status_code
            for i in range(3)
        ]
    assert codes == [200, 200, 429]


def test_invite_key_falls_back_to_the_ipv6_slash_64():
    assert get_user_identifier(_request_from("2001:db8:1:2::1")) == "2001:db8:1:2::/64"
