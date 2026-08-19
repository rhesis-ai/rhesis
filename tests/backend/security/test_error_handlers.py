"""The contract the router batches rely on.

Unexpected failures must tell the client nothing and the logs everything, tied
together by one id. Deliberate 4xx messages must keep working untouched -- that
is the regression that would hurt users most.
"""

import ast
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from rhesis.backend.app.error_handlers import (
    PUBLIC_ERROR_MESSAGES,
    PublicHTTPException,
    UpstreamHTTPException,
    create_validation_error_response,
    http_exception_handler,
    internal_error,
    log_validation_error,
    public_message,
    unhandled_exception_handler,
)
from rhesis.backend.app.utils.request_context import RequestIDMiddleware

SECRET = "could not connect to server at 10.0.3.14:5432 password=hunter2"


class Payload(BaseModel):
    name: str
    count: int


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    # Both bases, and the 422 pair, exactly as main.py registers them.
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc: RequestValidationError):
        log_validation_error(exc, request)
        return create_validation_error_response(exc)

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

    @app.get("/masked/{status}")
    def masked(status: int):
        raise HTTPException(status_code=status, detail=f"Failed to sync: {SECRET}")

    @app.get("/starlette-server-error")
    def starlette_server_error():
        """main.py registers Starlette's base too; only this route exercises it."""
        raise StarletteHTTPException(status_code=500, detail=f"Failed to sync: {SECRET}")

    @app.get("/public-503")
    def public_503():
        raise PublicHTTPException(status_code=503, detail="Garak package is not installed")

    @app.get("/internal-public-detail")
    def internal_public_detail():
        try:
            raise RuntimeError(SECRET)
        except RuntimeError as exc:
            raise internal_error(
                exc, context="ctx", public_detail="No generation model is configured"
            ) from exc

    @app.get("/internal-public-detail-400")
    def internal_public_detail_400():
        try:
            raise RuntimeError(SECRET)
        except RuntimeError as exc:
            raise internal_error(
                exc,
                context="ctx",
                status_code=400,
                public_detail="No generation model is configured",
            ) from exc

    @app.get("/needs-auth")
    def needs_auth():
        raise HTTPException(
            status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"}
        )

    @app.get("/structured-detail")
    def structured_detail():
        raise HTTPException(status_code=400, detail=[{"field": "name", "error": "taken"}])

    @app.post("/validate")
    def validate(payload: Payload):
        return {"ok": True}

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
    body = response.json()
    assert body["detail"] == public_message(500)
    # Masking without a usable id is what makes a support request unanswerable.
    assert body["error_id"]
    assert body["error_id"] == response.headers["x-request-id"]


def test_starlette_http_exception_is_genericised_too(client):
    """main.py registers both bases; a Starlette-raised 5xx must mask as well."""
    response = client.get("/starlette-server-error")

    assert response.status_code == 500
    assert SECRET not in response.text
    body = response.json()
    assert body["detail"] == public_message(500)
    assert body["error_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("status", sorted(PUBLIC_ERROR_MESSAGES))
def test_each_masked_status_keeps_its_own_wording(client, status):
    """Collapsing 502/503/504 into the 500 text tells the caller the wrong thing."""
    response = client.get(f"/masked/{status}")

    assert response.status_code == status
    assert response.json()["detail"] == PUBLIC_ERROR_MESSAGES[status]
    assert SECRET not in response.text
    assert response.json()["error_id"]


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


def test_public_http_exception_keeps_its_literal_detail(client):
    """The exemption routers use for "the package isn't installed" answers."""
    response = client.get("/public-503")

    assert response.status_code == 503
    assert response.json()["detail"] == "Garak package is not installed"
    assert response.json()["error_id"]


def test_public_http_exception_is_a_warning_without_a_traceback(client, caplog):
    """A missing optional package is not a fault to debug -- no stack, no ERROR."""
    with caplog.at_level(logging.WARNING):
        client.get("/public-503")

    records = [r for r in caplog.records if "Garak package is not installed" in r.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert not records[0].exc_info


def test_public_exemption_does_not_widen_to_plain_5xx(client):
    """Same status, same file: only the PublicHTTPException detail survives."""
    assert client.get("/masked/503").json()["detail"] == public_message(503)
    assert SECRET not in client.get("/masked/503").text


def test_unlogged_upstream_error_is_a_warning_without_a_traceback(client, caplog):
    """The 5xx passthrough logs the reason, not a stack pointing at our raise."""
    with caplog.at_level(logging.WARNING):
        client.get("/upstream")

    records = [r for r in caplog.records if "Upstream returned 401" in r.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert not records[0].exc_info


def test_internal_error_public_detail_reaches_the_client(client):
    """Only survives because internal_error upgrades to PublicHTTPException --
    a plain HTTPException would have its 5xx detail masked straight back off."""
    response = client.get("/internal-public-detail")

    assert response.status_code == 500
    assert response.json()["detail"] == "No generation model is configured"
    assert SECRET not in response.text


def test_internal_error_public_detail_reaches_the_client_on_a_4xx(client):
    """Below 500 nothing masks it, so this is where public_detail works today."""
    response = client.get("/internal-public-detail-400")

    assert response.status_code == 400
    assert response.json()["detail"] == "No generation model is configured"
    assert SECRET not in response.text


def test_internal_error_public_detail_is_still_logged_in_full(client, caplog):
    """A caller-facing message is not a reason to stop logging the real one."""
    with caplog.at_level(logging.ERROR):
        client.get("/internal-public-detail")

    records = [r for r in caplog.records if "ctx" in r.getMessage()]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert SECRET in records[0].getMessage()


def test_validation_error_still_names_the_field(client):
    """A 422 exists to tell the caller which field is wrong."""
    response = client.post("/validate", json={"count": "not-a-number"})

    assert response.status_code == 422
    fields = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert ("body", "name") in fields
    assert ("body", "count") in fields
    assert all(error["msg"] for error in response.json()["detail"])


def test_validation_error_is_logged_as_a_warning_without_a_traceback(client, caplog):
    """A 422 is the caller sending the wrong shape, not a server fault."""
    with caplog.at_level(logging.WARNING):
        client.post("/validate", json={"count": "not-a-number"})

    records = [r for r in caplog.records if "Validation error on" in r.getMessage()]
    assert records
    assert all(r.levelno == logging.WARNING for r in records)
    assert not any(r.exc_info for r in records)


def test_client_error_headers_survive(client):
    """Drop WWW-Authenticate and every 401 stops telling clients how to retry."""
    response = client.get("/needs-auth")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_non_string_client_error_detail_survives(client):
    """Field-level 4xx detail is sometimes a list; passing it through must keep it."""
    response = client.get("/structured-detail")

    assert response.status_code == 400
    assert response.json()["detail"] == [{"field": "name", "error": "taken"}]


MAIN_PY = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "backend"
    / "src"
    / "rhesis"
    / "backend"
    / "app"
    / "main.py"
)


def _registered_handlers() -> set[tuple[str, str]]:
    """(exception class, handler) pairs main.py registers on the real app.

    Read from the source rather than by importing the app: main.py pulls in the
    whole dependency graph and needs live database settings, and this only has to
    catch the registration going missing.
    """
    tree = ast.parse(MAIN_PY.read_text())
    registered = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_exception_handler"
            and len(node.args) == 2
        ):
            registered.add((ast.unparse(node.args[0]), ast.unparse(node.args[1])))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "exception_handler"
            and node.args
        ):
            registered.add((ast.unparse(node.args[0]), "decorator"))
    return registered


@pytest.mark.parametrize(
    "exception_class,handler",
    [
        # Both bases: FastAPI's HTTPException subclasses Starlette's, but the
        # lookup tries the exact class first.
        ("StarletteHTTPException", "http_exception_handler"),
        ("FastAPIHTTPException", "http_exception_handler"),
        ("Exception", "unhandled_exception_handler"),
        ("RequestValidationError", "decorator"),
    ],
)
def test_real_app_registers_the_masking_handlers(exception_class, handler):
    """Every test above builds its own app, so nothing here notices main.py
    dropping a registration -- and then nothing masks anything in production."""
    assert (exception_class, handler) in _registered_handlers()


@pytest.fixture
def cors_client() -> TestClient:
    """The real middleware order: CORS inside RequestIDMiddleware, as in main.py."""
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"])
    app.add_middleware(RequestIDMiddleware)

    @app.get("/boom")
    def boom():
        raise RuntimeError(SECRET)

    @app.get("/server-error")
    def server_error():
        raise HTTPException(status_code=500, detail=SECRET)

    return TestClient(app, raise_server_exceptions=False)


ORIGIN = {"Origin": "http://localhost:3000"}


def test_http_exception_500_is_readable_by_browser_js(cors_client):
    """Raised 5xx come from ExceptionMiddleware, which sits inside CORS."""
    response = cors_client.get("/server-error", headers=ORIGIN)

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.json()["error_id"]


def test_unhandled_500_carries_no_cors_headers(cors_client):
    """Documents a known gap, not a wanted behaviour: ServerErrorMiddleware builds
    this response *outside* CORSMiddleware, so browser JS can read neither the
    body nor X-Request-ID -- the id support asks for is unreachable exactly when
    it is needed most. Fixing it means moving middleware, not touching this test.
    """
    response = cors_client.get("/boom", headers=ORIGIN)

    assert response.status_code == 500
    assert response.json()["error_id"]
    assert "access-control-allow-origin" not in response.headers
