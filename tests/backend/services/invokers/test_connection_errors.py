"""Tests for the plain-language reasons given for failed outbound connections."""

import socket
import ssl

import httpx
import pytest
import requests

from rhesis.backend.app.services.invokers.common.connection_errors import (
    describe_connection_error,
    url_host,
)


def _chained(outer: Exception, cause: BaseException) -> Exception:
    outer.__cause__ = cause
    return outer


@pytest.fixture
def silent_server():
    """Accepts connections and never answers."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    yield f"http://127.0.0.1:{sock.getsockname()[1]}/"
    sock.close()


@pytest.fixture
def closed_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}/"


class TestRealFailures:
    @pytest.mark.asyncio
    async def test_httpx_read_timeout(self, silent_server):
        async with httpx.AsyncClient(timeout=0.2) as client:
            with pytest.raises(httpx.ReadTimeout) as exc_info:
                await client.post(silent_server)
        assert describe_connection_error(exc_info.value) == (
            "it did not respond before the timeout"
        )

    def test_requests_read_timeout(self, silent_server):
        with pytest.raises(requests.ReadTimeout) as exc_info:
            requests.post(silent_server, timeout=0.2)
        assert describe_connection_error(exc_info.value) == (
            "it did not respond before the timeout"
        )

    @pytest.mark.asyncio
    async def test_httpx_refused(self, closed_port):
        async with httpx.AsyncClient(timeout=1) as client:
            with pytest.raises(httpx.ConnectError) as exc_info:
                await client.post(closed_port)
        assert describe_connection_error(exc_info.value) == "the connection was refused"

    def test_requests_refused(self, closed_port):
        with pytest.raises(requests.ConnectionError) as exc_info:
            requests.post(closed_port, timeout=1)
        assert describe_connection_error(exc_info.value) == "the connection was refused"

    def test_requests_missing_scheme(self):
        with pytest.raises(requests.exceptions.MissingSchema) as exc_info:
            requests.post("auth.example.com/token", timeout=1)
        assert describe_connection_error(exc_info.value) == "the URL is not valid"


class TestChainedCauses:
    def test_dns_failure(self):
        exc = _chained(httpx.ConnectError("x"), socket.gaierror(8, "nodename nor servname"))
        assert describe_connection_error(exc) == "the host name could not be resolved"

    def test_certificate_rejected(self):
        cause = ssl.SSLCertVerificationError(1, "verify failed")
        cause.verify_message = "certificate has expired"
        exc = _chained(requests.exceptions.SSLError("x"), cause)
        assert describe_connection_error(exc) == (
            "its TLS certificate was rejected (certificate has expired)"
        )

    def test_connect_timeout(self):
        assert describe_connection_error(httpx.ConnectTimeout("")) == "the connection timed out"

    def test_unknown_error_without_text_falls_back_to_its_name(self):
        assert describe_connection_error(httpx.RemoteProtocolError("")) == ("RemoteProtocolError")


def test_url_host():
    assert url_host("https://api.example.com/v1/chat") == "api.example.com"
    assert url_host("http://127.0.0.1:8080/x") == "127.0.0.1:8080"
    assert url_host(None) == "the server"


@pytest.mark.parametrize(
    "url",
    [
        "https://user:s3cret@auth.example.com/token",  # trufflehog:ignore
        "user:s3cret@auth.example.com/token",  # trufflehog:ignore
    ],
)
def test_url_host_never_echoes_credentials(url):
    assert "s3cret" not in url_host(url)
