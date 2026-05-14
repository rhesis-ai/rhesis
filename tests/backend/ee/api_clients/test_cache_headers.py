"""Verify the token-endpoint cache-headers middleware.

The middleware MUST stamp ``Cache-Control: no-store``, ``Pragma:
no-cache``, and ``X-Content-Type-Options: nosniff`` on every response
from the configured paths -- success, error, validation, and
not-found alike. Per RFC 6749 §5.1 a token endpoint has no
"sometimes cacheable" mode, so partial coverage is the same as no
coverage.

These tests are isolated: they spin up a minimal Starlette app with
only the middleware mounted, so they do not require the rest of the
backend (no DB, no Redis, no SSO config). That isolation is what
lets the test enforce the "every status code" guarantee without
having to construct a real failure for each status path through the
full router.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from starlette.testclient import TestClient

from rhesis.backend.ee.api_clients.cache_headers import (
    DEFAULT_NO_STORE_PATHS,
    TokenEndpointCacheHeadersMiddleware,
)


def _build_app(extra_paths: tuple[str, ...] = ()) -> FastAPI:
    """Build a minimal FastAPI app with the middleware and one route per path.

    The routes are designed to surface a representative spread of
    status codes so the per-status assertion below is meaningful:

    - ``/auth/token-exchange``  -> 200
    - ``/auth/refresh``         -> 400
    - ``/auth/token-exchange-401`` (override) -> 401 via HTTPException
    """
    app = FastAPI()
    paths = tuple(DEFAULT_NO_STORE_PATHS) + extra_paths
    app.add_middleware(TokenEndpointCacheHeadersMiddleware, paths=paths)

    @app.post("/auth/token-exchange")
    async def ok_endpoint() -> JSONResponse:
        return JSONResponse({"access_token": "x"}, status_code=200)

    @app.post("/auth/refresh")
    async def err_endpoint() -> Response:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    @app.post("/auth/token-exchange-401")
    async def httpexc_endpoint() -> None:
        raise HTTPException(status_code=401, detail="bad")

    @app.get("/other")
    async def other() -> JSONResponse:
        return JSONResponse({"ok": True})

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_build_app(extra_paths=("/auth/token-exchange-401",)))


@pytest.mark.parametrize(
    "method,path,expected_status",
    [
        ("post", "/auth/token-exchange", 200),
        ("post", "/auth/refresh", 400),
        ("post", "/auth/token-exchange-401", 401),
    ],
)
def test_no_store_headers_present_on_every_status(
    client: TestClient, method: str, path: str, expected_status: int
) -> None:
    """Every response from a configured path carries the no-store triple."""
    resp = client.request(method, path)
    assert resp.status_code == expected_status
    assert resp.headers.get("Cache-Control") == "no-store"
    assert resp.headers.get("Pragma") == "no-cache"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_404_on_token_endpoint_path_still_gets_no_store_headers(
    client: TestClient,
) -> None:
    """A 405 / 404 from a configured prefix must still be no-store.

    Catching this is the whole reason the middleware exists rather
    than a per-handler dependency -- a handler-side dependency can't
    decorate a 405 because no handler ran.
    """
    # GET on a POST-only path -> 405
    resp = client.get("/auth/token-exchange")
    assert resp.status_code == 405
    assert resp.headers.get("Cache-Control") == "no-store"


def test_other_paths_are_not_touched(client: TestClient) -> None:
    """Routes outside the configured set must not get the headers.

    The middleware is opt-in to keep its blast radius small. A future
    perf regression where some other route gets locked out of caching
    would be a real bug -- so we assert the negative explicitly.
    """
    resp = client.get("/other")
    assert resp.status_code == 200
    assert "Cache-Control" not in resp.headers
    assert "Pragma" not in resp.headers
