"""Tests for the plain-language reasons given for failed outbound connections."""

import asyncio
import datetime
import ipaddress
import socket
import ssl
import threading

import httpx
import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

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
def silent_tls_server(tmp_path):
    """Completes the TLS handshake, then never answers. Yields (url, cert path)."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert, key_file = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key_file)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    held = []

    def accept():
        while True:
            try:
                conn, _ = sock.accept()
                held.append(context.wrap_socket(conn, server_side=True))
            except OSError:
                return

    threading.Thread(target=accept, daemon=True).start()
    yield f"https://127.0.0.1:{sock.getsockname()[1]}/", str(cert)
    sock.close()
    for conn in held:
        conn.close()


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

    @pytest.mark.asyncio
    async def test_httpx_read_timeout_over_tls(self, silent_tls_server):
        url, cert = silent_tls_server
        async with httpx.AsyncClient(
            timeout=0.5, verify=ssl.create_default_context(cafile=cert)
        ) as client:
            with pytest.raises(httpx.ReadTimeout) as exc_info:
                await client.post(url)
        assert describe_connection_error(exc_info.value) == (
            "it did not respond before the timeout"
        )

    def test_requests_read_timeout_over_tls(self, silent_tls_server):
        url, cert = silent_tls_server
        with pytest.raises(requests.ReadTimeout) as exc_info:
            requests.post(url, timeout=0.5, verify=cert)
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

    def test_read_timeout_over_tls_is_not_a_handshake_failure(self):
        # The chain httpx raises when a read over TLS times out.
        want_read = ssl.SSLWantReadError(2, "The operation did not complete (read)")
        cancelled = asyncio.CancelledError()
        cancelled.__context__ = want_read
        timeout = TimeoutError()
        timeout.__context__ = cancelled
        exc = _chained(httpx.ReadTimeout(""), timeout)
        assert describe_connection_error(exc) == "it did not respond before the timeout"

    def test_connect_timeout_during_tls_handshake(self):
        exc = _chained(httpx.ConnectTimeout(""), ssl.SSLWantWriteError(3, "write"))
        assert describe_connection_error(exc) == "the connection timed out"

    def test_handshake_failure(self):
        cause = ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] wrong version number")
        exc = _chained(httpx.ConnectError("x"), cause)
        assert describe_connection_error(exc) == "the TLS handshake failed"

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
