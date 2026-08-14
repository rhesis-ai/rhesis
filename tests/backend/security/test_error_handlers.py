"""The contract the router batches rely on.

Unexpected failures must tell the client nothing and the logs everything, tied
together by one id. Deliberate 4xx messages must keep working untouched -- that
is the regression that would hurt users most.
"""

import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from rhesis.backend.app.error_handlers import (
    UpstreamHTTPException,
    http_exception_handler,
    internal_error,
    public_message,
    unhandled_exception_handler,
)
from rhesis.backend.app.utils.request_context import RequestIDMiddleware

SECRET = "could not connect to server at 10.0.3.14:5432 password=hunter2"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/boom")
    def boom():
        raise RuntimeError(SECRET)

    @app.get("/server-error")
    def server_error():
        raise HTTPException(status_code=500, detail=f"Failed to sync: {SECRET}")

    @app.get("/bad-request")
    def bad_request():
        raise HTTPException(status_code=400, detail="Test set name already exists")

    @app.get("/not-found")
    def not_found():
        raise HTTPException(status_code=404, detail="Organization not found")

    @app.get("/internal")
    def internal():
        try:
            raise RuntimeError(SECRET)
        except RuntimeError as exc:
            raise internal_error(exc, context="ctx") from exc

    @app.get("/internal-400")
    def internal_400():
        try:
            raise RuntimeError(SECRET)
        except RuntimeError as exc:
            raise internal_error(exc, context="ctx", status_code=400) from exc

    @app.get("/upstream")
    def upstream():
        raise UpstreamHTTPException(status_code=502, detail="Upstream returned 401 Unauthorized")

    @app.get("/upstream-logged")
    def upstream_logged():
        """What services/endpoint/testing.py raises: logged by the caller."""
        exc = UpstreamHTTPException(status_code=500, detail="Connection refused")
        exc.rhesis_logged = True
        raise exc

    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_hides_detail_and_returns_error_id(client):
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == public_message(500)
    assert SECRET not in response.text
    assert body["error_id"]
    assert body["error_id"] == response.headers["x-request-id"]


def test_unhandled_exception_is_logged_with_traceback(client, caplog):
    with caplog.at_level(logging.ERROR):
        error_id = client.get("/boom").json()["error_id"]

    record = next(r for r in caplog.records if "Unhandled exception" in r.getMessage())
    assert error_id in record.getMessage()
    assert record.exc_info is not None, "traceback must reach the logs"
    assert SECRET in str(record.exc_info[1]), "the real reason must survive in the log"


def test_server_side_http_exception_is_genericised(client):
    response = client.get("/server-error")

    assert response.status_code == 500
    assert SECRET not in response.text
    assert response.json()["detail"] == public_message(500)


@pytest.mark.parametrize(
    "path,status,detail",
    [
        ("/bad-request", 400, "Test set name already exists"),
        ("/not-found", 404, "Organization not found"),
    ],
)
def test_client_errors_keep_their_message(client, path, status, detail):
    """Deliberate validation messages are for the user -- they must survive."""
    response = client.get(path)

    assert response.status_code == status
    assert response.json()["detail"] == detail
    assert "error_id" not in response.json()


def test_request_id_is_per_request(client):
    first = client.get("/boom").json()["error_id"]
    second = client.get("/boom").json()["error_id"]

    assert first != second


def test_safe_inbound_request_id_is_reused(client):
    response = client.get("/boom", headers={"X-Request-ID": "trace-abc-123"})

    assert response.json()["error_id"] == "trace-abc-123"


@pytest.mark.parametrize("hostile", ["bad id\nINJECTED: forged log line", "x" * 200, "a;b|c"])
def test_hostile_inbound_request_id_is_rejected(client, hostile):
    """An inbound id reaches the logs, so it must not be able to forge lines."""
    response = client.get("/boom", headers={"X-Request-ID": hostile})

    assert response.json()["error_id"] != hostile


def test_request_id_header_is_not_duplicated(client):
    """The middleware adds the header; handlers must not add it again."""
    for path in ("/boom", "/server-error", "/bad-request"):
        response = client.get(path)
        ids = [v for k, v in response.headers.multi_items() if k.lower() == "x-request-id"]
        assert len(ids) == 1, f"{path} returned {len(ids)} X-Request-ID headers"


def test_internal_error_is_logged_once(client, caplog):
    """internal_error logs with context; the handler must not log it again."""
    with caplog.at_level(logging.ERROR):
        client.get("/internal")

    with_traceback = [r for r in caplog.records if r.exc_info]
    assert len(with_traceback) == 1, f"expected 1 traceback, got {len(with_traceback)}"
    assert "ctx" in with_traceback[0].getMessage()


def test_internal_error_uses_client_wording_for_4xx(client):
    """A 400 described as "an unexpected error occurred" misattributes the fault."""
    response = client.get("/internal-400")

    assert response.status_code == 400
    assert response.json()["detail"] == "The request could not be processed."


def test_internal_error_does_not_log_a_traceback_for_4xx(client, caplog):
    """A caller's mistake is a warning, not a stack trace in the error stream."""
    with caplog.at_level(logging.WARNING):
        client.get("/internal-400")

    records = [r for r in caplog.records if "ctx" in r.getMessage()]
    assert records, "the failure must still leave one line"
    assert all(r.levelno == logging.WARNING for r in records)
    assert not any(r.exc_info for r in records)


def test_upstream_exception_keeps_its_detail(client):
    """A 5xx describing the CALLER's system is theirs to read."""
    response = client.get("/upstream")

    assert response.status_code == 502
    assert response.json()["detail"] == "Upstream returned 401 Unauthorized"
    assert response.json()["error_id"]


def test_upstream_exemption_does_not_leak_our_errors(client):
    """The exemption is opt-in -- a plain 500 is still masked."""
    assert client.get("/server-error").json()["detail"] == public_message(500)
    assert SECRET not in client.get("/server-error").text


def test_already_logged_upstream_error_is_not_logged_again(client, caplog):
    """A user's own endpoint refusing must not also land in the error stream."""
    with caplog.at_level(logging.WARNING):
        response = client.get("/upstream-logged")

    assert response.json()["detail"] == "Connection refused"
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
