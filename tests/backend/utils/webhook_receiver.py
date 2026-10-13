"""A fake HTTPS receiver for outbound webhook tests.

Replaces DNS and the wire under ``SafeHttpClient`` and nothing else, so the
HTTPS check, the SSRF blocklist and the redirect policy all still run.
"""

import socket
from contextlib import contextmanager
from typing import Iterator, Optional
from unittest.mock import patch

import httpx

from rhesis.backend.app.utils import ssrf_http_client

PUBLIC_IP = "93.184.216.34"


class Received(list):
    """The requests received, in order, and the options each client was built with."""

    client_options: list[dict]


@contextmanager
def fake_receiver(
    status: int = 200,
    addresses: Optional[dict[str, str]] = None,
    location: Optional[str] = None,
) -> Iterator[Received]:
    """Answer every request with ``status``. Hostnames resolve to ``addresses``, else public."""
    received = Received()
    received.client_options = []

    def handle(request: httpx.Request) -> httpx.Response:
        received.append(request)
        headers = {"location": location} if location else {}
        return httpx.Response(status, headers=headers, text="ok" if status < 300 else "refused")

    def resolve(host, *_args, **_kwargs):
        ip = (addresses or {}).get(host, PUBLIC_IP)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    real_client = httpx.Client

    def client(**kwargs):
        received.client_options.append(kwargs)
        return real_client(transport=httpx.MockTransport(handle), **kwargs)

    with (
        patch.object(ssrf_http_client.socket, "getaddrinfo", side_effect=resolve),
        patch.object(ssrf_http_client.httpx, "Client", side_effect=client),
    ):
        yield received
