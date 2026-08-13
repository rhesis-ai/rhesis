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
    http_exception_handler,
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
