"""OTLP/HTTP responses: success with ``partial_success``, failures as ``google.rpc.Status``.

https://opentelemetry.io/docs/specs/otlp/#otlphttp-response
"""

from typing import Optional

from fastapi import Response
from google.protobuf import json_format
from google.protobuf.message import Message
from google.rpc import code_pb2, status_pb2
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTracePartialSuccess,
    ExportTraceServiceResponse,
)

from rhesis.backend.ee.otlp.decode import OTLPEncoding

_GRPC_CODE_FOR_HTTP = {
    400: code_pb2.INVALID_ARGUMENT,
    401: code_pb2.UNAUTHENTICATED,
    403: code_pb2.PERMISSION_DENIED,
    404: code_pb2.NOT_FOUND,
    413: code_pb2.RESOURCE_EXHAUSTED,
    415: code_pb2.INVALID_ARGUMENT,
    422: code_pb2.INVALID_ARGUMENT,
    429: code_pb2.RESOURCE_EXHAUSTED,
    503: code_pb2.UNAVAILABLE,
}


def _encode(message: Message, encoding: OTLPEncoding) -> bytes:
    if encoding is OTLPEncoding.JSON:
        return json_format.MessageToJson(message, indent=None).encode("utf-8")
    return message.SerializeToString()


def export_response(
    encoding: OTLPEncoding, rejected_spans: int = 0, error_message: str = ""
) -> Response:
    """200 with ``partial_success`` set only when spans were dropped, as the spec asks."""
    message = ExportTraceServiceResponse()
    if rejected_spans or error_message:
        message.partial_success.CopyFrom(
            ExportTracePartialSuccess(rejected_spans=rejected_spans, error_message=error_message)
        )
    return Response(content=_encode(message, encoding), media_type=encoding.value)


def encode_status(status_code: int, message: str, encoding: OTLPEncoding) -> bytes:
    """A ``google.rpc.Status`` for an HTTP status, in the request's encoding."""
    status = status_pb2.Status(
        code=_GRPC_CODE_FOR_HTTP.get(status_code, code_pb2.UNKNOWN), message=message
    )
    return _encode(status, encoding)


def error_response(
    status_code: int,
    message: str,
    encoding: OTLPEncoding,
    retry_after: Optional[int | str] = None,
) -> Response:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return Response(
        content=encode_status(status_code, message, encoding),
        status_code=status_code,
        media_type=encoding.value,
        headers=headers,
    )
