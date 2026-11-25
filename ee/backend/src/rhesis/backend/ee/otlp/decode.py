"""Decode OTLP/HTTP trace export requests (protobuf, JSON, gzip).

https://opentelemetry.io/docs/specs/otlp/#otlphttp
"""

import base64
import json
import zlib
from enum import Enum
from typing import Any, Optional

from google.protobuf import json_format
from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

_ID_FIELDS = ("traceId", "spanId", "parentSpanId", "trace_id", "span_id", "parent_span_id")


class OTLPEncoding(str, Enum):
    PROTOBUF = "application/x-protobuf"
    JSON = "application/json"


class OTLPDecodeError(ValueError):
    """The payload could not be decoded (400)."""


class OTLPPayloadTooLarge(ValueError):
    """The payload exceeds the size limits (413)."""


class OTLPUnsupportedMediaType(ValueError):
    """Neither protobuf nor JSON (415)."""


def encoding_for(content_type: Optional[str]) -> OTLPEncoding:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type in ("application/x-protobuf", "application/protobuf"):
        return OTLPEncoding.PROTOBUF
    if media_type == "application/json":
        return OTLPEncoding.JSON
    raise OTLPUnsupportedMediaType(
        f"Unsupported Content-Type {content_type!r}; use application/x-protobuf or application/json"
    )


def decompress(body: bytes, content_encoding: Optional[str], max_bytes: int) -> bytes:
    """Gunzip ``body``, refusing output over ``max_bytes`` (a gzip bomb guard)."""
    encoding = (content_encoding or "").strip().lower()
    if encoding in ("", "identity"):
        return body
    if encoding != "gzip":
        raise OTLPDecodeError(f"Unsupported Content-Encoding {content_encoding!r}; use gzip")
    # Stream with a cap instead of gzip.decompress, which would inflate a bomb
    # fully before we could check its size.
    inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    try:
        out = inflater.decompress(body, max_bytes + 1)
    except zlib.error as exc:
        raise OTLPDecodeError(f"Invalid gzip body: {exc}") from exc
    if len(out) > max_bytes or inflater.unconsumed_tail:
        raise OTLPPayloadTooLarge(f"Decompressed body exceeds {max_bytes} bytes")
    return out


def _hex_ids_to_base64(node: Any) -> Any:
    """OTLP JSON carries ids as hex; protobuf's JSON mapping expects base64 bytes."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _ID_FIELDS and isinstance(value, str):
                try:
                    node[key] = base64.b64encode(bytes.fromhex(value)).decode("ascii")
                except ValueError as exc:
                    raise OTLPDecodeError(f"{key} is not hex: {value!r}") from exc
            else:
                _hex_ids_to_base64(value)
    elif isinstance(node, list):
        for item in node:
            _hex_ids_to_base64(item)
    return node


def decode_request(
    body: bytes,
    content_type: Optional[str],
    content_encoding: Optional[str],
    max_decompressed_bytes: int,
) -> tuple[ExportTraceServiceRequest, OTLPEncoding]:
    """Parse an export request. Raises the OTLP* errors above.

    The wire size is capped before this, while the body is read.
    """
    encoding = encoding_for(content_type)
    raw = decompress(body, content_encoding, max_decompressed_bytes)
    return parse_request(raw, encoding), encoding


def parse_request(raw: bytes, encoding: OTLPEncoding) -> ExportTraceServiceRequest:
    """Parse a decompressed export request. Raises :class:`OTLPDecodeError`."""
    request = ExportTraceServiceRequest()
    if encoding is OTLPEncoding.PROTOBUF:
        try:
            request.ParseFromString(raw)
        except DecodeError as exc:
            raise OTLPDecodeError(f"Invalid protobuf payload: {exc}") from exc
        return request

    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise OTLPDecodeError(f"Invalid JSON payload: {exc}") from exc
    except RecursionError as exc:
        raise OTLPDecodeError("JSON payload is nested too deeply") from exc
    if not isinstance(payload, dict):
        raise OTLPDecodeError("JSON payload must be an object")
    try:
        # Receivers must ignore unknown fields (OTLP spec, JSON encoding).
        json_format.ParseDict(_hex_ids_to_base64(payload), request, ignore_unknown_fields=True)
    except json_format.ParseError as exc:
        raise OTLPDecodeError(f"Invalid OTLP JSON payload: {exc}") from exc
    except RecursionError as exc:
        raise OTLPDecodeError("JSON payload is nested too deeply") from exc
    return request


__all__ = [
    "OTLPDecodeError",
    "OTLPEncoding",
    "OTLPPayloadTooLarge",
    "OTLPUnsupportedMediaType",
    "decode_request",
    "decompress",
    "encoding_for",
    "parse_request",
]
