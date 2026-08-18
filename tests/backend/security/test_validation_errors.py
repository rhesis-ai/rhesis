"""A 422 must not hand back, or write down, what the caller submitted.

Pydantic attaches the offending value to every validation error. For a *missing*
field there is no single value to attach, so it attaches the whole request body
-- which is how a signup that forgets its email address ends up answering with
the password of the person who typed it.
"""

import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, SecretStr

from rhesis.backend.app.error_handlers import (
    create_validation_error_response,
    log_validation_error,
)

PASSWORD = "hunter2-but-far-too-short"
CLIENT_SECRET = "sso-client-secret-value"


@pytest.fixture
def client() -> TestClient:
    """Mirrors main.py's validation handler so both paths are the real ones."""
    app = FastAPI()

    class Signup(BaseModel):
        email: str
        password: str = Field(min_length=32)

    class SSOConfig(BaseModel):
        issuer: str
        # SecretStr masks the value everywhere Pydantic prints it -- but `input`
        # is the raw body, captured before any of that applies.
        client_secret: SecretStr

    @app.exception_handler(RequestValidationError)
    async def handler(request: Request, exc: RequestValidationError):
        log_validation_error(exc, request)
        return create_validation_error_response(exc)

    @app.post("/signup")
    def signup(body: Signup):  # pragma: no cover - never reached
        return {}

    @app.put("/sso")
    def sso(body: SSOConfig):  # pragma: no cover - never reached
        return {}

    return TestClient(app)


def test_response_omits_the_offending_value(client):
    response = client.post("/signup", json={"email": "a@b.com", "password": PASSWORD})

    assert response.status_code == 422
    assert "input" not in response.json()["detail"][0]
    assert PASSWORD not in response.text


def test_missing_field_does_not_echo_the_whole_body(client):
    """The case that makes this more than cosmetic."""
    response = client.post("/signup", json={"password": PASSWORD})

    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


def test_secretstr_field_is_not_echoed_either(client):
    """SecretStr is no defence here -- worth pinning so nobody assumes it is."""
    response = client.put("/sso", json={"client_secret": CLIENT_SECRET})

    assert response.status_code == 422
    assert CLIENT_SECRET not in response.text


def test_response_still_says_what_is_wrong(client):
    """Dropping the value must not cost the caller the diagnosis."""
    response = client.post("/signup", json={"email": "a@b.com", "password": "short"})

    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "password"]
    assert error["type"] == "string_too_short"
    assert "at least 32" in error["msg"]
    assert error["ctx"] == {"min_length": "32"}


def test_logging_omits_the_offending_value(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/signup", json={"email": "a@b.com", "password": PASSWORD})

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert PASSWORD not in logged
    assert "password" in logged, "the field that failed is still worth logging"


def test_logging_omits_the_whole_body_too(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/signup", json={"password": PASSWORD})

    assert PASSWORD not in "\n".join(r.getMessage() for r in caplog.records)


def test_validation_error_is_not_logged_as_a_server_fault(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/signup", json={"email": "a@b.com", "password": PASSWORD})

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
