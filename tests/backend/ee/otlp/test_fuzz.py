"""Malformed and unusual OTLP exports: every one ends in a clean answer.

Seeded random cases, so a failure reproduces. The request side must either
accept a payload or refuse it with 400/413/415, never raise; whatever it
accepts must survive the queue message and be storable by the worker. A 500 is
not retried by exporters and loses the batch; a worker error retries it
forever.
"""

import gzip
import json
import math
import random
from typing import Any, Iterator, List

import pytest
from fastapi import status
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue

from rhesis.backend.app.config.settings import get_trace_ingest_settings
from rhesis.backend.app.services.telemetry.ingest import IngestJob
from rhesis.backend.ee.otlp import router as otlp_router
from tests.backend.ee.otlp import fixtures as fx

SEED = 20261125
CASES = 300

GENAI_KEYS = [
    "gen_ai.operation.name",
    "gen_ai.agent.name",
    "gen_ai.conversation.id",
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.system_instructions",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.cache_read.input_tokens",
    "gen_ai.transfer.target.name",
    "gen_ai.request.model",
    "error.type",
    "rhesis.project_id",
    "deployment.environment.name",
]
OPERATIONS = [
    "chat",
    "invoke_agent",
    "invoke_workflow",
    "execute_tool",
    "create_agent",
    "plan",
    "embeddings",
    "retrieval",
    "search_memory",
    "",
    "invoke_",
    "chat chat",
]
STRINGS = [
    "",
    "x",
    "\x00",
    "nul\x00inside",
    "ünïcødé ✓",
    "😀" * 3,
    "a" * 200_000,
    "{",
    "[]",
    "null",
    '[{"role": "user", "parts": [{"type": "text", "content": "hi"}]}]',
    '[{"role": "user", "parts": "not a list"}]',
    '[{"role": 5, "parts": [{"type": "text"}]}]',
    '{"role": "assistant"}',
    "[" * 500,
]


def _value(rng: random.Random, depth: int = 0) -> AnyValue:
    kind = rng.choice(["str", "int", "double", "bool", "bytes", "array", "kvlist", "empty"])
    value = AnyValue()
    if kind == "str":
        value.string_value = rng.choice(STRINGS + OPERATIONS)
    elif kind == "int":
        value.int_value = rng.choice([0, -1, 1, 2**63 - 1, -(2**63), 1500])
    elif kind == "double":
        value.double_value = rng.choice([0.0, -0.5, 1e308, math.inf, -math.inf, math.nan])
    elif kind == "bool":
        value.bool_value = rng.random() < 0.5
    elif kind == "bytes":
        value.bytes_value = rng.randbytes(rng.randint(0, 40))
    elif kind == "array" and depth < 4:
        value.array_value.values.extend(_value(rng, depth + 1) for _ in range(rng.randint(0, 4)))
    elif kind == "kvlist" and depth < 4:
        value.kvlist_value.values.extend(
            KeyValue(key=rng.choice(GENAI_KEYS + ["k"]), value=_value(rng, depth + 1))
            for _ in range(rng.randint(0, 3))
        )
    return value


def _attributes(rng: random.Random, count: int) -> List[KeyValue]:
    attributes = []
    for _ in range(count):
        key = rng.choice(GENAI_KEYS + ["", "custom.key", "ai.agent.name", "rhesis.test.run_id"])
        if key == "gen_ai.operation.name" and rng.random() < 0.6:
            value = AnyValue(string_value=rng.choice(OPERATIONS))
        else:
            value = _value(rng)
        attributes.append(KeyValue(key=key, value=value))
    return attributes


def _id(rng: random.Random, size: int) -> bytes:
    return rng.choice(
        [rng.randbytes(size)] * 6
        + [b"", b"\x00" * size, rng.randbytes(size - 1), rng.randbytes(size + 1)]
    )


def _request(rng: random.Random) -> ExportTraceServiceRequest:
    """An export built field by field with odd but encodable values."""
    request = ExportTraceServiceRequest()
    trace_ids = [rng.randbytes(16) for _ in range(rng.randint(1, 3))]
    for _ in range(rng.randint(0, 3)):
        resource_spans = request.resource_spans.add()
        resource_spans.resource.attributes.extend(_attributes(rng, rng.randint(0, 4)))
        for _ in range(rng.randint(0, 2)):
            scope_spans = resource_spans.scope_spans.add()
            scope_spans.scope.name = rng.choice(["", "example.agents", "x" * 300])
            span_ids = [rng.randbytes(8) for _ in range(rng.randint(1, 6))]
            for span_id in span_ids:
                span = scope_spans.spans.add()
                span.trace_id = rng.choice(trace_ids) if rng.random() < 0.9 else _id(rng, 16)
                span.span_id = span_id if rng.random() < 0.9 else _id(rng, 8)
                if rng.random() < 0.7:
                    # Includes self-parenting and loops between siblings.
                    span.parent_span_id = rng.choice(span_ids + [_id(rng, 8)])
                span.name = rng.choice(STRINGS[:8] + [f"{rng.choice(OPERATIONS)} thing"])
                span.kind = rng.choice([0, 1, 2, 3, 4, 5, 99])
                start = rng.choice([0, 1, 1_700_000_000_000_000_000, 2**64 - 1])
                span.start_time_unix_nano = start
                span.end_time_unix_nano = rng.choice([0, start, max(start - 5, 0), 2**64 - 1])
                span.attributes.extend(_attributes(rng, rng.randint(0, 10)))
                for _ in range(rng.randint(0, 3)):
                    event = span.events.add()
                    event.name = rng.choice(["exception", "gen_ai.client.exception", "", "x"])
                    event.time_unix_nano = rng.choice([0, start, 2**64 - 1])
                    event.attributes.extend(_attributes(rng, rng.randint(0, 3)))
                for _ in range(rng.randint(0, 2)):
                    link = span.links.add()
                    link.trace_id = _id(rng, 16)
                    link.span_id = _id(rng, 8)
                span.status.code = rng.choice([0, 1, 2, 7])
                span.status.message = rng.choice(STRINGS[:6])
    return request


def _mutate_json(rng: random.Random, node: Any) -> Any:
    """Replace a random part of a decoded OTLP JSON payload with a wrong type."""
    replacements: List[Any] = [None, 1, -1, "x", "", [], {}, True, 1.5, "zz", [None]]
    if isinstance(node, dict) and node:
        key = rng.choice(list(node))
        if rng.random() < 0.3:
            node[key] = rng.choice(replacements)
        else:
            node[key] = _mutate_json(rng, node[key])
    elif isinstance(node, list) and node:
        index = rng.randrange(len(node))
        node[index] = _mutate_json(rng, node[index])
    elif rng.random() < 0.5:
        return rng.choice(replacements)
    return node


def _valid_body() -> bytes:
    return fx.protobuf_body(fx.research_run(http_root=True).spans)


def _cases() -> Iterator[tuple[str, bytes, str, str]]:
    """(label, body, content type, content encoding)"""
    rng = random.Random(SEED)
    valid = _valid_body()
    valid_json = json.loads(fx.json_body(fx.research_run().spans))
    for index in range(CASES):
        kind = index % 6
        if kind == 0:
            yield "random bytes", rng.randbytes(rng.randint(0, 400)), fx.PROTOBUF, ""
        elif kind == 1:
            body = bytearray(valid)
            for _ in range(rng.randint(1, 8)):
                body[rng.randrange(len(body))] = rng.randrange(256)
            body = body[: rng.randint(1, len(body))]
            yield "corrupted protobuf", bytes(body), fx.PROTOBUF, ""
        elif kind == 2:
            body = gzip.compress(rng.randbytes(rng.randint(0, 200)))
            body = body[: rng.randint(0, len(body))]
            yield "random gzip", body, rng.choice([fx.PROTOBUF, fx.JSON]), "gzip"
        elif kind == 3:
            payload = _mutate_json(rng, json.loads(json.dumps(valid_json)))
            yield "mutated JSON", json.dumps(payload).encode(), fx.JSON, ""
        else:
            body = _request(rng).SerializeToString()
            if rng.random() < 0.3:
                yield "generated, gzip", gzip.compress(body), fx.PROTOBUF, "gzip"
            else:
                yield "generated", body, fx.PROTOBUF, ""


def _accept(body: bytes, content_type: str, encoding: str):
    """The OTLP route's decode and translate, as run in its worker thread."""
    limits = get_trace_ingest_settings()
    raw, otlp_encoding = otlp_router._decode(body, content_type, encoding, limits)
    return otlp_router._translate(raw, otlp_encoding, limits)


CASE_LIST = list(_cases())


@pytest.mark.parametrize(
    "label,body,content_type,encoding",
    CASE_LIST,
    ids=[f"{i}-{case[0].replace(' ', '-')}" for i, case in enumerate(CASE_LIST)],
)
def test_decode_and_translate_accept_or_refuse_cleanly(label, body, content_type, encoding):
    try:
        translated = _accept(body, content_type, encoding)
    except otlp_router.OTLPBadRequest as exc:
        assert exc.status_code in (400, 413, 415), label
        return

    for span in translated.spans:
        assert span.trace_id and span.span_id
    # Whatever is accepted must survive the queue message unchanged in count.
    if translated.spans:
        job = IngestJob(translated.spans, "org", None, "project")
        for message in job.messages(get_trace_ingest_settings().max_message_bytes):
            json.dumps(message)
            assert IngestJob.from_message(message).spans


def test_the_corpus_reaches_translation():
    """Guards the generator: most generated exports must decode, or the test proves little."""
    decoded = 0
    spans = 0
    for _label, body, content_type, encoding in CASE_LIST:
        try:
            translated = _accept(body, content_type, encoding)
        except otlp_router.OTLPBadRequest:
            continue
        decoded += 1
        spans += len(translated.spans)
    assert decoded > CASES // 3
    assert spans > CASES


@pytest.mark.integration
def test_accepted_exports_are_stored_through_the_route(
    authenticated_client, test_db, db_project, inline_trace_ingest
):
    """Through the route and the worker's storage, on the test database."""
    rng = random.Random(SEED + 1)
    project = str(db_project.id)
    answers = []
    for _ in range(40):
        request = _request(rng)
        for resource_spans in request.resource_spans:
            kept = [a for a in resource_spans.resource.attributes if a.key != "rhesis.project_id"]
            del resource_spans.resource.attributes[:]
            resource_spans.resource.attributes.extend(kept)
            resource_spans.resource.attributes.append(
                KeyValue(key="rhesis.project_id", value=AnyValue(string_value=project))
            )
        body = request.SerializeToString()
        response = authenticated_client.post(
            "/telemetry/v1/traces",
            content=body,
            headers={"Content-Type": fx.PROTOBUF},
        )
        answers.append(response.status_code)
        # 503 here would mean the inline worker failed to store what was accepted.
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        ), response.content
    assert answers.count(status.HTTP_200_OK) > 10
    assert inline_trace_ingest, "nothing reached storage"
