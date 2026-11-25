"""Answer every OTLP ingest failure the way OTLP/HTTP clients expect.

Errors on ``POST /telemetry/v1/traces`` can come from anywhere: auth and feature
dependencies, the quota backstop's global handler, FastAPI's validation handler.
They all produce the app's usual JSON. This middleware rewrites those into a
``google.rpc.Status`` in the request's encoding, and turns the backstop's 402
into 429 + ``Retry-After``: OTLP exporters drop a batch on 402 at once but retry
429 with backoff. Bodies the route already encoded pass through untouched.

Pure ASGI, so streaming and the request body are left alone.
"""

import json
from typing import Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rhesis.backend.ee.otlp.decode import OTLPEncoding, OTLPUnsupportedMediaType, encoding_for
from rhesis.backend.ee.otlp.responses import encode_status

OTLP_TRACES_PATH = "/telemetry/v1/traces"
_RETRYABLE = {429, 502, 503, 504}
_QUOTA_EXCEEDED = 402


def _header(scope: Scope, name: bytes) -> Optional[str]:
    for key, value in scope.get("headers") or []:
        if key.lower() == name:
            return value.decode("latin-1")
    return None


def _request_encoding(scope: Scope) -> OTLPEncoding:
    try:
        return encoding_for(_header(scope, b"content-type"))
    except OTLPUnsupportedMediaType:
        return OTLPEncoding.PROTOBUF


def _message(body: bytes) -> str:
    try:
        payload = json.loads(body)
    except ValueError:
        return body.decode("utf-8", "replace")
    if isinstance(payload, dict):
        detail = payload.get("message") or payload.get("detail") or payload
        return detail if isinstance(detail, str) else json.dumps(detail)
    return json.dumps(payload)


class OTLPErrorMiddleware:
    def __init__(self, app: ASGIApp, *, retry_after_seconds) -> None:
        self.app = app
        # A callable so a changed setting (and tests) take effect without a restart.
        self._retry_after_seconds = retry_after_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != OTLP_TRACES_PATH:
            await self.app(scope, receive, send)
            return

        encoding = _request_encoding(scope)
        start: Optional[Message] = None
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                content_type = dict(message.get("headers") or []).get(b"content-type", b"")
                if message["status"] >= 400 and content_type.startswith(b"application/json"):
                    start = message
                    return
                await send(message)
                return
            if start is None:
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if not message.get("more_body"):
                await self._send_status(send, start, b"".join(chunks), encoding)

        await self.app(scope, receive, capture)

    async def _send_status(
        self, send: Send, start: Message, body: bytes, encoding: OTLPEncoding
    ) -> None:
        status = start["status"]
        headers = [
            (k, v)
            for k, v in start.get("headers") or []
            if k.lower() not in (b"content-type", b"content-length")
        ]
        if status == _QUOTA_EXCEEDED:
            status = 429
        if status in _RETRYABLE and not any(k.lower() == b"retry-after" for k, _ in headers):
            headers.append((b"retry-after", str(self._retry_after_seconds()).encode()))
        content = encode_status(status, _message(body), encoding)
        headers += [
            (b"content-type", encoding.value.encode()),
            (b"content-length", str(len(content)).encode()),
        ]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": content})
