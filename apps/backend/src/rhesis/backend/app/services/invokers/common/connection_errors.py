"""Plain-language reasons for failed outbound connections.

httpx and requests both wrap the real cause (DNS, refused, TLS) a few levels
down the exception chain, and httpx's timeouts stringify to an empty string, so
``str(exc)`` alone often tells the user nothing.
"""

import socket
import ssl
from typing import Iterator, Optional
from urllib.parse import urlparse

import httpx
import requests

_INVALID_URL = (
    httpx.InvalidURL,
    httpx.UnsupportedProtocol,
    requests.exceptions.InvalidURL,
    requests.exceptions.MissingSchema,
    requests.exceptions.InvalidSchema,
)
_CONNECT_TIMEOUT = (httpx.ConnectTimeout, requests.exceptions.ConnectTimeout)
_TIMEOUT = (httpx.TimeoutException, requests.exceptions.Timeout, TimeoutError)


def _chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def url_host(url: Optional[str]) -> str:
    """The host of a URL for messages, or the URL itself when it has none."""
    if not url:
        return "the server"
    return urlparse(url).netloc or url


def describe_connection_error(exc: BaseException) -> str:
    """Why a request never got a response, as a short clause for the user."""
    chain = list(_chain(exc))
    if isinstance(exc, _INVALID_URL):
        return "the URL is not valid"
    for cause in chain:
        if isinstance(cause, ssl.SSLCertVerificationError):
            detail = cause.verify_message or "certificate verification failed"
            return f"its TLS certificate was rejected ({detail})"
        if isinstance(cause, ssl.SSLError):
            return "the TLS handshake failed"
        if isinstance(cause, socket.gaierror):
            return "the host name could not be resolved"
        if isinstance(cause, ConnectionRefusedError):
            return "the connection was refused"
    if isinstance(exc, _CONNECT_TIMEOUT):
        return "the connection timed out"
    if any(isinstance(cause, _TIMEOUT) for cause in chain):
        return "it did not respond before the timeout"
    for cause in chain:
        if isinstance(cause, OSError) and cause.strerror:
            return f"could not connect ({cause.strerror})"
    text = str(exc)
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__
